"""Unit-level service contracts use real SQLite and real files.

Each test catches a concrete broken branch: publication leaks, wrong deadline
comparison, missing material, duplicate rows, cross-owner access, or audit drift.
"""
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import sqlite3
import unittest

from scholarship.domain import AppError, Store

NOW = datetime(2026, 10, 19, 8, 0, tzinfo=timezone.utc)
PDF = b"%PDF-1.4\n% teaching example\n%%EOF\n"


class RulesTest(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[1] / ".test-tmp"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.now = NOW
        self.store = Store(self.root / "test.sqlite3", self.root / "uploads", clock=lambda: self.now)
        self.store.seed_demo()

    def error(self, status, code, callback):
        with self.assertRaises(AppError) as caught:
            callback()
        self.assertEqual(status, caught.exception.status)
        self.assertEqual(code, caught.exception.code)
        return caught.exception

    def materials(self, actor="student1", project="open"):
        result = []
        for key in ("transcript", "proof"):
            item = self.store.upload(actor, project, key, key + ".pdf", base64.b64encode(PDF).decode())
            self.assertIn("id", item, "真实上传必须返回附件编号")
            result.append(item["id"])
        return result

    def submit(self, actor="student1", project="open", ids=None):
        item = self.store.submit(actor, project, {"phone":"13800000000", "application_reason":"用于完成学业"}, ids if ids is not None else self.materials(actor, project))
        self.assertIn("id", item, "完整申请必须生成唯一编号")
        return item

    def test_US01_only_published_projects_are_listed(self):
        rows = self.store.list_projects("student1")
        self.assertEqual({"open", "future", "closed"}, {row["id"] for row in rows})

    def test_US01_unpublished_detail_is_not_returned(self):
        self.error(404, "NOT_FOUND", lambda: self.store.get_project("student1", "draft"))

    def test_US01_detail_contains_conditions_materials_and_window(self):
        item = self.store.get_project("student1", "open")
        self.assertTrue(item.get("conditions"))
        self.assertEqual(["transcript", "proof"], [m["key"] for m in item["required_materials"]])
        self.assertEqual("开放中", item["window_state"])
        self.assertTrue(item["can_apply"])
        self.assertLess(item["open_at"], item["deadline"])

    def test_US01_future_and_closed_remain_readable_but_disabled(self):
        for key, state in (("future", "未开始"), ("closed", "申请已结束")):
            with self.subTest(project=key):
                p = self.store.get_project("student1", key)
                self.assertEqual(state, p.get("window_state"))
                self.assertFalse(p["can_apply"])

    def test_unknown_user_and_wrong_password_are_rejected(self):
        self.error(401, "AUTH_REQUIRED", lambda: self.store.get_user("nobody"))
        self.error(401, "BAD_CREDENTIALS", lambda: self.store.authenticate("student1", "wrong"))

    def test_demo_login_returns_role_without_password_hash(self):
        user = self.store.authenticate("student1", "demo123")
        self.assertEqual("student", user.get("role"))
        self.assertNotIn("password_hash", user)

    def test_upload_stores_real_bytes_with_digest_and_safe_path(self):
        result = self.store.upload("student1", "open", "proof", "../../证明.pdf", base64.b64encode(PDF).decode())
        self.assertIn("id", result)
        self.assertEqual("证明.pdf", result["filename"])
        attachment = self.store.get_attachment("student1", result["id"])
        path = Path(attachment["path"])
        self.assertTrue(path.resolve().is_relative_to((self.root / "uploads").resolve()))
        self.assertEqual(PDF, path.read_bytes())
        self.assertEqual(len(PDF), result["size"])
        self.assertEqual(64, len(result["sha256"]))

    def test_upload_rejects_bad_base64_extension_magic_empty_and_size(self):
        cases = [("a.pdf", "!", "INVALID_FILE"), ("a.exe", base64.b64encode(PDF).decode(), "FILE_TYPE"), ("a.pdf", base64.b64encode(b"fake").decode(), "FILE_TYPE"), ("a.pdf", "", "INVALID_FILE"), ("a.pdf", base64.b64encode(b"%PDF-" + b"x" * (2 * 1024 * 1024)).decode(), "FILE_TOO_LARGE")]
        for filename, data, code in cases:
            with self.subTest(code=code):
                self.error(400, code, lambda: self.store.upload("student1", "open", "proof", filename, data))

    def test_upload_rejects_unknown_material_and_counselor(self):
        data = base64.b64encode(PDF).decode()
        self.error(400, "UNKNOWN_MATERIAL", lambda: self.store.upload("student1", "open", "other", "a.pdf", data))
        self.error(403, "FORBIDDEN", lambda: self.store.upload("counselor1", "open", "proof", "a.pdf", data))

    def test_US02_complete_submission_has_status_time_and_two_materials(self):
        a = self.submit()
        self.assertEqual("待辅导员审核", a["status"])
        self.assertEqual("2026-10-19T08:00:00+00:00", a["submitted_at"])
        self.assertEqual(2, len(a["attachments"]))
        self.assertEqual(1, len(self.store.list_applications("student1")))

    def test_US02_missing_fields_and_materials_report_each_and_create_no_record(self):
        error = self.error(400, "INCOMPLETE", lambda: self.store.submit("student1", "open", {}, []))
        self.assertEqual({"联系电话", "申请理由", "成绩单", "证明材料"}, set(error.details))
        self.assertEqual([], self.store.list_applications("student1"))

    def test_US02_whitespace_fields_are_missing(self):
        error = self.error(400, "INCOMPLETE", lambda: self.store.submit("student1", "open", {"phone":" ", "application_reason":"\t"}, self.materials()))
        self.assertIn("联系电话", error.details)
        self.assertIn("申请理由", error.details)

    def test_US02_each_single_missing_field_or_material_is_blocked(self):
        ids=self.materials()
        complete={"phone":"13800000000","application_reason":"支持学业"}
        cases=[({"application_reason":"支持学业"},ids,"联系电话"),({"phone":"13800000000"},ids,"申请理由"),(complete,[ids[1]],"成绩单"),(complete,[ids[0]],"证明材料")]
        for fields,files,missing in cases:
            with self.subTest(missing=missing):
                e=self.error(400,"INCOMPLETE",lambda:self.store.submit("student1","open",fields,files))
                self.assertEqual([missing],e.details)
                self.assertEqual([],self.store.list_applications("student1"))

    def test_US02_rejects_before_open_and_exact_deadline(self):
        ids = self.materials()
        project = self.store.get_project("student1", "open")
        for moment in (datetime.fromisoformat(project["open_at"]) - timedelta(microseconds=1), datetime.fromisoformat(project["deadline"]), datetime.fromisoformat(project["deadline"]) + timedelta(seconds=1)):
            self.now = moment
            self.error(409, "WINDOW_CLOSED", lambda: self.store.submit("student1", "open", {"phone":"13800000000", "application_reason":"reason"}, ids))
            self.assertEqual([], self.store.list_applications("student1"))

    def test_US02_accepts_exact_open_boundary(self):
        ids = self.materials()
        p = self.store.get_project("student1", "open")
        self.now = datetime.fromisoformat(p["open_at"])
        self.assertEqual("待辅导员审核", self.submit(ids=ids)["status"])

    def test_US02_rechecks_deadline_at_transaction_not_preflight(self):
        ids=self.materials()
        deadline=datetime.fromisoformat(self.store.get_project("student1","open")["deadline"])
        readings=iter([NOW,deadline,deadline])
        self.store.clock=lambda:next(readings,deadline)
        self.error(409,"WINDOW_CLOSED",lambda:self.store.submit("student1","open",{"phone":"138","application_reason":"x"},ids))
        self.assertEqual([],self.store.list_applications("student1"))

    def test_US02_duplicate_returns_original_even_after_deadline(self):
        a = self.submit()
        self.now += timedelta(days=30)
        b = self.store.submit("student1", "open", {}, [])
        self.assertEqual(a["id"], b.get("id"))
        self.assertTrue(b["duplicate"])
        self.assertEqual(1, len(self.store.list_applications("student1")))

    def test_US02_concurrent_duplicate_has_one_record(self):
        ids = self.materials()
        with ThreadPoolExecutor(max_workers=6) as pool:
            rows = list(pool.map(lambda _: self.store.submit("student1", "open", {"phone":"13800000000", "application_reason":"reason"}, ids), range(6)))
        self.assertEqual(1, len({r.get("id") for r in rows}))
        self.assertEqual(1, len(self.store.list_applications("student1")))

    def test_US02_impersonation_and_other_student_material_are_denied(self):
        ids = self.materials("student2")
        self.error(403, "FORBIDDEN", lambda: self.store.submit("student1", "open", {"phone":"138", "application_reason":"x"}, ids))
        self.error(403, "FORBIDDEN", lambda: self.store.submit("student1", "open", {}, [], target_student_id="student2"))
        self.assertEqual([], self.store.list_applications("student1"))

    def test_US02_cross_project_or_unknown_attachment_is_denied(self):
        ids = self.materials(project="future")
        self.error(400, "WRONG_PROJECT", lambda: self.store.submit("student1", "open", {"phone":"138", "application_reason":"x"}, ids))
        self.error(404, "NOT_FOUND", lambda: self.store.submit("student1", "open", {"phone":"138", "application_reason":"x"}, ["missing"]))

    def test_US02_other_student_cannot_read_or_modify_application_or_file(self):
        a = self.submit()
        self.error(403, "FORBIDDEN", lambda: self.store.get_application("student2", a["id"]))
        self.error(403, "FORBIDDEN", lambda: self.store.modify_application("student2", a["id"], {}))
        self.error(403, "FORBIDDEN", lambda: self.store.get_attachment("student2", a["attachments"][0]["id"]))
        self.error(409, "IMMUTABLE", lambda: self.store.modify_application("student1", a["id"], {}))
        self.assertEqual("待辅导员审核", self.store.get_application("student1", a["id"])["status"])

    def test_US03_approve_moves_to_college_and_records_audit(self):
        a = self.submit()
        result = self.store.review("counselor1", a["id"], "approve", "材料完整")
        self.assertEqual("待学院复核", result.get("status"))
        log = self.store.get_audit("student1", a["id"])
        self.assertEqual(1, len(log))
        self.assertEqual("counselor1", log[0]["reviewer_id"])
        self.assertEqual("材料完整", log[0]["opinion"])
        self.assertEqual("approve", log[0]["decision"])
        self.assertEqual("2026-10-19T08:00:00+00:00", log[0]["reviewed_at"])

    def test_US03_reject_reason_is_visible_to_owner_and_terminal(self):
        a = self.submit()
        self.store.review("counselor1", a["id"], "reject", "证明材料不符合通知")
        result = self.store.get_application("student1", a["id"])
        self.assertEqual("已驳回", result["status"])
        self.assertEqual("证明材料不符合通知", result["rejection_reason"])
        self.error(409, "ALREADY_REVIEWED", lambda: self.store.review("counselor1", a["id"], "approve", "again"))

    def test_US03_blank_rejection_keeps_status_and_no_audit(self):
        a = self.submit()
        self.error(400, "REASON_REQUIRED", lambda: self.store.review("counselor1", a["id"], "reject", " \t"))
        self.assertEqual("待辅导员审核", self.store.get_application("student1", a["id"])["status"])
        self.assertEqual([], self.store.get_audit("student1", a["id"]))

    def test_US03_counselor_scope_restricts_list_view_material_and_review(self):
        a = self.submit("student3")
        self.assertEqual([], self.store.list_applications("counselor1"))
        self.error(403, "FORBIDDEN", lambda: self.store.get_application("counselor1", a["id"]))
        self.error(403, "FORBIDDEN", lambda: self.store.get_attachment("counselor1", a["attachments"][0]["id"]))
        self.error(403, "FORBIDDEN", lambda: self.store.review("counselor1", a["id"], "approve", "x"))
        self.assertEqual(1, len(self.store.list_applications("counselor2")))

    def test_US03_student_cannot_review_and_invalid_decision_is_rejected(self):
        a = self.submit()
        self.error(403, "FORBIDDEN", lambda: self.store.review("student1", a["id"], "approve", "x"))
        self.error(400, "INVALID_DECISION", lambda: self.store.review("counselor1", a["id"], "publish", "x"))

    def test_US03_repeat_approval_does_not_add_second_log(self):
        a = self.submit()
        self.store.review("counselor1", a["id"], "approve", "ok")
        error = self.error(409, "ALREADY_REVIEWED", lambda: self.store.review("counselor1", a["id"], "reject", "again"))
        self.assertEqual("待学院复核", error.current_status)
        self.assertEqual(1, len(self.store.get_audit("student1", a["id"])))

    def test_US03_concurrent_review_only_one_wins_and_one_audit(self):
        a = self.submit()
        def attempt(decision):
            try:
                return self.store.review("counselor1", a["id"], decision, "并发测试")["status"]
            except AppError as e:
                return e.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, ["approve", "reject"]))
        self.assertEqual(1, results.count("ALREADY_REVIEWED"))
        logs=self.store.get_audit("student1", a["id"])
        self.assertEqual(1,len(logs))
        final=self.store.get_application("student1",a["id"])["status"]
        self.assertEqual("待学院复核" if logs[0]["decision"]=="approve" else "已驳回",final)

    def test_US03_audit_insert_failure_rolls_back_status_change(self):
        a=self.submit()
        with self.store.connection() as con:
            con.executescript("CREATE TRIGGER fail_audit BEFORE INSERT ON reviews BEGIN SELECT RAISE(ABORT,'injected audit failure'); END;")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.review("counselor1",a["id"],"approve","完整")
        self.assertEqual("待辅导员审核",self.store.get_application("student1",a["id"])["status"])
        self.assertEqual([],self.store.get_audit("student1",a["id"]))

    def test_unauthorized_operations_preserve_all_fields_bytes_and_audit(self):
        a=self.submit()
        original=self.store.get_application("student1",a["id"])
        material=self.store.get_attachment("student1",a["attachments"][0]["id"])
        before=Path(material["path"]).read_bytes()
        for actor in ("student2","counselor2"):
            self.error(403,"FORBIDDEN",lambda:self.store.modify_application(actor,a["id"],{"phone":"changed"}))
            self.error(403,"FORBIDDEN",lambda:self.store.review(actor,a["id"],"reject","changed"))
            self.error(403,"FORBIDDEN",lambda:self.store.get_attachment(actor,material["id"]))
        self.assertEqual(original,self.store.get_application("student1",a["id"]))
        self.assertEqual(before,Path(material["path"]).read_bytes())
        self.assertEqual([],self.store.get_audit("student1",a["id"]))

    def test_seed_is_idempotent_and_data_survives_reopen(self):
        a = self.submit()
        reopened = Store(self.root / "test.sqlite3", self.root / "uploads", clock=lambda: self.now)
        reopened.seed_demo()
        self.assertEqual(a["id"], reopened.list_applications("student1")[0]["id"])
        self.assertEqual(3, len(reopened.list_projects("student1")))


if __name__ == "__main__":
    unittest.main()
