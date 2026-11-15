"""US04 学院复核：领域规则、学院范围、审计原子性与数据迁移。

每个用例都对应对接文档点名的验收分支：跨学院、非法状态、空驳回理由、
重复审核、审计原子性，以及审核人 / 时间 / 意见留痕。
"""
import base64
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import tempfile
import unittest

from scholarship.domain import AppError, Store
from tests.test_unit import NOW, PDF


class CollegeReviewRulesTest(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[1] / ".test-tmp"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "test.sqlite3", self.root / "uploads", clock=lambda: NOW)
        self.store.seed_demo()

    def error(self, status, code, callback):
        with self.assertRaises(AppError) as caught:
            callback()
        self.assertEqual(status, caught.exception.status)
        self.assertEqual(code, caught.exception.code)
        return caught.exception

    def submit(self, student="student1"):
        ids = [self.store.upload(student, "open", key, key + ".pdf",
                                 base64.b64encode(PDF).decode())["id"]
               for key in ("transcript", "proof")]
        return self.store.submit(student, "open",
                                 {"phone": "13800000000", "application_reason": "学业支持"}, ids)

    def pending(self, student="student1", counselor="counselor1"):
        application_id = self.submit(student)["id"]
        self.store.review(counselor, application_id, "approve", "材料齐全")
        return application_id

    def test_migration_is_idempotent_and_preserves_legacy_teaching_data(self):
        for _ in range(3):
            self.store.migrate_college_review()
        with self.store.connection() as con:
            rows = con.execute("SELECT id,role,college FROM users WHERE role='college_reviewer' ORDER BY id").fetchall()
            indexes = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        self.assertEqual(2, len(rows))
        self.assertEqual({"college1", "college2"}, {r["id"] for r in rows})
        self.assertEqual({"计算机学院", "文学院"}, {r["college"] for r in rows})
        self.assertIn("application_status", indexes)
        original = self.submit()["id"]
        reopened = Store(self.root / "test.sqlite3", self.root / "uploads", clock=lambda: NOW)
        reopened.seed_demo()
        self.assertEqual(original, reopened.list_applications("student1")[0]["id"])
        self.assertEqual(3, len(reopened.list_projects("student1")))
        self.assertEqual("college_reviewer", reopened.get_user("college1")["role"])

    def test_college_reviewer_list_is_scoped_to_own_college(self):
        first = self.pending("student1", "counselor1")
        third = self.pending("student3", "counselor2")
        self.assertEqual([first], [a["id"] for a in self.store.list_applications("college1")])
        self.assertEqual([third], [a["id"] for a in self.store.list_applications("college2")])

    def test_cross_college_detail_audit_material_and_review_are_denied(self):
        application_id = self.pending()
        self.error(403, "FORBIDDEN", lambda: self.store.get_application("college2", application_id))
        self.error(403, "FORBIDDEN", lambda: self.store.get_audit("college2", application_id))
        self.error(403, "FORBIDDEN", lambda: self.store.college_review("college2", application_id, "approve", "x"))
        detail = self.store.get_application("college1", application_id)
        self.assertEqual("待学院复核", detail["status"])
        self.assertNotIn("college", detail)
        self.assertEqual(1, len(self.store.get_audit("college1", application_id)))
        attachment = self.store.get_attachment("college1", detail["attachments"][0]["id"])
        self.assertEqual(PDF, Path(attachment["path"]).read_bytes())
        self.error(403, "FORBIDDEN", lambda: self.store.get_attachment("college2", detail["attachments"][0]["id"]))

    def test_approve_moves_to_pending_publicity_and_appends_audit(self):
        application_id = self.pending()
        result = self.store.college_review("college1", application_id, "approve", "学院同意")
        self.assertEqual("待公示", result["status"])
        self.assertEqual("", result["rejection_reason"])
        logs = self.store.get_audit("student1", application_id)
        self.assertEqual(2, len(logs))
        # 测试时钟固定，两条记录 reviewed_at 相同，按 reviewer_id 定位而非位置。
        entry = [log for log in logs if log["reviewer_id"] == "college1"]
        self.assertEqual(1, len(entry))
        self.assertEqual("approve", entry[0]["decision"])
        self.assertEqual("学院同意", entry[0]["opinion"])
        self.assertEqual("2026-10-19T08:00:00+00:00", entry[0]["reviewed_at"])

    def test_reject_requires_nonblank_reason_and_is_terminal(self):
        application_id = self.pending()
        for blank in ("", " \t"):
            with self.subTest(blank=repr(blank)):
                self.error(400, "REASON_REQUIRED",
                           lambda value=blank: self.store.college_review("college1", application_id, "reject", value))
        self.assertEqual("待学院复核", self.store.get_application("student1", application_id)["status"])
        self.assertEqual(1, len(self.store.get_audit("student1", application_id)))
        result = self.store.college_review("college1", application_id, "reject", "学院复核不通过")
        self.assertEqual("已驳回", result["status"])
        self.assertEqual("学院复核不通过", result["rejection_reason"])
        self.assertEqual("学院复核不通过",
                         self.store.get_application("student1", application_id)["rejection_reason"])
        self.assertEqual(2, len(self.store.get_audit("student1", application_id)))

    def test_invalid_state_and_repeat_review_expose_current_status(self):
        fresh = self.submit()["id"]
        early = self.error(409, "ALREADY_REVIEWED",
                           lambda: self.store.college_review("college1", fresh, "approve", "x"))
        self.assertEqual("待辅导员审核", early.current_status)
        application_id = self.pending()
        self.store.college_review("college1", application_id, "approve", "同意")
        repeated = self.error(409, "ALREADY_REVIEWED",
                              lambda: self.store.college_review("college1", application_id, "reject", "again"))
        self.assertEqual("待公示", repeated.current_status)
        self.assertEqual(2, len(self.store.get_audit("student1", application_id)))

    def test_roles_are_isolated_between_counselor_and_college_endpoints(self):
        application_id = self.pending()
        for actor in ("student1", "counselor1", "college2"):
            with self.subTest(actor=actor):
                self.error(403, "FORBIDDEN",
                           lambda who=actor: self.store.college_review(who, application_id, "approve", "x"))
        self.error(403, "FORBIDDEN", lambda: self.store.review("college1", application_id, "approve", "x"))
        self.error(403, "FORBIDDEN", lambda: self.store.upload(
            "college1", "open", "proof", "a.pdf", base64.b64encode(PDF).decode()))
        self.error(403, "FORBIDDEN", lambda: self.store.submit("college1", "open", {}, []))

    def test_invalid_decision_does_not_change_status_or_audit(self):
        application_id = self.pending()
        self.error(400, "INVALID_DECISION",
                   lambda: self.store.college_review("college1", application_id, "publish", "x"))
        self.assertEqual("待学院复核", self.store.get_application("student1", application_id)["status"])
        self.assertEqual(1, len(self.store.get_audit("student1", application_id)))

    def test_audit_insert_failure_rolls_back_status_change(self):
        application_id = self.pending()
        with self.store.connection() as con:
            con.executescript("CREATE TRIGGER fail_college_audit BEFORE INSERT ON reviews "
                              "BEGIN SELECT RAISE(ABORT,'injected audit failure'); END;")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.college_review("college1", application_id, "approve", "完整")
        self.assertEqual("待学院复核", self.store.get_application("student1", application_id)["status"])
        self.assertEqual(1, len(self.store.get_audit("student1", application_id)))

    def test_concurrent_college_review_only_one_wins_and_one_audit(self):
        application_id = self.pending()

        def attempt(decision):
            try:
                return self.store.college_review("college1", application_id, decision, "并发测试")["status"]
            except AppError as error:
                return error.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, ["approve", "reject"]))
        self.assertEqual(1, results.count("ALREADY_REVIEWED"))
        logs = self.store.get_audit("student1", application_id)
        self.assertEqual(2, len(logs))
        college_log = [log for log in logs if log["reviewer_id"] == "college1"]
        self.assertEqual(1, len(college_log))
        expected = "待公示" if college_log[0]["decision"] == "approve" else "已驳回"
        self.assertEqual(expected, self.store.get_application("student1", application_id)["status"])


if __name__ == "__main__":
    unittest.main()
