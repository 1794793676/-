"""US04 学院复核：路由层契约与真实 HTTP 链路。

RouteTest 直接调生产 dispatcher；HttpTest 起真实 ThreadingHTTPServer，
走 CookieJar / CSRF / SQLite / 磁盘附件，验证端到端状态与审计。
"""
import base64
from http.cookiejar import CookieJar
import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPCookieProcessor, ProxyHandler

from scholarship.domain import Store
from scholarship.server import Application, create_server
from tests.test_unit import NOW, PDF

REVIEW_PATH = "/api/applications/{}/college-review"


class CollegeReviewRouteTest(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[1] / ".test-tmp"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.store = Store(root / "db.sqlite3", root / "uploads", clock=lambda: NOW)
        self.store.seed_demo()
        self.time = 1000
        self.app = Application(self.store, session_clock=lambda: self.time)
        self.cookie, self.csrf = "", ""

    def call(self, method, path, data=None, headers=None):
        h = {"Host": "localhost:8080", "Content-Type": "application/json",
             "Cookie": self.cookie, "X-CSRF-Token": self.csrf}
        h.update(headers or {})
        return self.app.dispatch(method, path, h, json.dumps(data or {}).encode())

    def data(self, response, status=200):
        self.assertEqual(status, response.status, response.body)
        return json.loads(response.body)["data"]

    def code(self, response, status):
        self.assertEqual(status, response.status, response.body)
        return json.loads(response.body)["error"]

    def login(self, user="student1"):
        response = self.call("POST", "/api/login", {"username": user, "password": "demo123"})
        self.cookie = response.headers["Set-Cookie"].split(";", 1)[0]
        self.csrf = self.data(response)["csrf_token"]

    def materials(self):
        ids = []
        for key in ("transcript", "proof"):
            item = self.data(self.call("POST", "/api/uploads", {
                "project_id": "open", "material_key": key, "filename": key + ".pdf",
                "content_base64": base64.b64encode(PDF).decode()}), 201)
            ids.append(item["id"])
        return ids

    def submit(self, user="student1"):
        self.login(user)
        return self.data(self.call("POST", "/api/applications", {
            "project_id": "open", "fields": {"phone": "13800000000", "application_reason": "学业支持"},
            "attachment_ids": self.materials()}), 201)

    def to_college(self, student="student1", counselor="counselor1"):
        application_id = self.submit(student)["id"]
        self.login(counselor)
        self.data(self.call("POST", "/api/applications/" + application_id + "/review",
                            {"decision": "approve", "opinion": "材料齐全"}))
        return application_id

    def test_college_review_requires_session_and_csrf(self):
        application_id = self.to_college()
        path = REVIEW_PATH.format(application_id)
        self.assertEqual("AUTH_REQUIRED", self.code(self.app.dispatch("POST", path, {"Host": "localhost:8080"}), 401)["code"])
        self.login("college1")
        self.assertEqual("CSRF_REQUIRED", self.code(self.call("POST", path,
                        {"decision": "approve", "opinion": "x"}, {"X-CSRF-Token": "bad"}), 403)["code"])

    def test_only_college_reviewer_can_call_endpoint(self):
        application_id = self.to_college()
        path = REVIEW_PATH.format(application_id)
        for actor in ("student1", "counselor1"):
            with self.subTest(actor=actor):
                self.login(actor)
                self.assertEqual("FORBIDDEN", self.code(self.call("POST", path,
                                {"decision": "approve", "opinion": "x"}), 403)["code"])
        self.login("student1")
        self.assertEqual("待学院复核", self.data(self.call("GET", "/api/applications/" + application_id))["status"])

    def test_cross_college_is_forbidden_and_status_unchanged(self):
        application_id = self.to_college()
        path = REVIEW_PATH.format(application_id)
        self.login("college2")
        self.assertEqual("FORBIDDEN", self.code(self.call("POST", path,
                        {"decision": "approve", "opinion": "x"}), 403)["code"])
        self.assertEqual("FORBIDDEN", self.code(self.call("GET", "/api/applications/" + application_id), 403)["code"])
        self.assertEqual("FORBIDDEN", self.code(self.call("GET", "/api/applications/" + application_id + "/audit"), 403)["code"])
        self.login("student1")
        self.assertEqual("待学院复核", self.data(self.call("GET", "/api/applications/" + application_id))["status"])

    def test_approve_returns_pending_publicity_and_audit_record(self):
        application_id = self.to_college()
        self.login("college1")
        result = self.data(self.call("POST", REVIEW_PATH.format(application_id),
                                     {"decision": "approve", "opinion": "学院同意"}))
        self.assertEqual("待公示", result["status"])
        self.assertEqual("", result["rejection_reason"])
        self.assertIn("attachments", result)
        logs = self.data(self.call("GET", "/api/applications/" + application_id + "/audit"))
        self.assertEqual(2, len(logs))
        entry = [log for log in logs if log["reviewer_id"] == "college1"]
        self.assertEqual(1, len(entry))
        self.assertEqual("approve", entry[0]["decision"])
        self.assertEqual("学院同意", entry[0]["opinion"])
        self.assertTrue(entry[0]["reviewed_at"])

    def test_blank_rejection_and_repeat_review_are_rejected(self):
        application_id = self.to_college()
        path = REVIEW_PATH.format(application_id)
        self.login("college1")
        self.assertEqual("REASON_REQUIRED", self.code(self.call("POST", path,
                        {"decision": "reject", "opinion": " \t "}), 400)["code"])
        result = self.data(self.call("POST", path, {"decision": "reject", "opinion": "材料不全"}))
        self.assertEqual("已驳回", result["status"])
        self.assertEqual("材料不全", result["rejection_reason"])
        error = self.code(self.call("POST", path, {"decision": "approve", "opinion": "again"}), 409)
        self.assertEqual("ALREADY_REVIEWED", error["code"])
        self.assertEqual("已驳回", error["current_status"])
        self.assertEqual(2, len(self.data(self.call("GET", "/api/applications/" + application_id + "/audit"))))

    def test_invalid_state_exposes_current_status_and_invalid_decision_is_rejected(self):
        # 用另一名学生构造「待辅导员审核」分支，避免与下面 to_college 的 student1 申请重复。
        fresh = self.submit("student2")["id"]
        self.login("college1")
        error = self.code(self.call("POST", REVIEW_PATH.format(fresh),
                                    {"decision": "approve", "opinion": "x"}), 409)
        self.assertEqual("ALREADY_REVIEWED", error["code"])
        self.assertEqual("待辅导员审核", error["current_status"])
        application_id = self.to_college()
        self.login("college1")
        self.assertEqual("INVALID_DECISION", self.code(self.call("POST", REVIEW_PATH.format(application_id),
                        {"decision": "publish", "opinion": "x"}), 400)["code"])
        self.assertEqual("INVALID_DECISION", self.code(self.call("POST", REVIEW_PATH.format(application_id),
                        {}), 400)["code"])

    def test_list_and_detail_are_scoped_to_reviewer_college(self):
        first = self.to_college("student1", "counselor1")
        third = self.to_college("student3", "counselor2")
        self.login("college1")
        self.assertEqual([first], [a["id"] for a in self.data(self.call("GET", "/api/applications"))])
        self.assertEqual("待学院复核", self.data(self.call("GET", "/api/applications/" + first))["status"])
        self.login("college2")
        self.assertEqual([third], [a["id"] for a in self.data(self.call("GET", "/api/applications"))])

    def test_counselor_endpoint_contract_is_unchanged(self):
        application_id = self.submit()["id"]
        self.login("counselor1")
        result = self.data(self.call("POST", "/api/applications/" + application_id + "/review",
                                     {"decision": "approve", "opinion": "完整"}))
        self.assertEqual("待学院复核", result["status"])
        self.login("college1")
        self.assertEqual("FORBIDDEN", self.code(self.call("POST", "/api/applications/" + application_id + "/review",
                        {"decision": "approve", "opinion": "x"}), 403)["code"])


class CollegeReviewHttpTest(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[1] / ".test-tmp"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        root = Path(self.temp.name)
        self.now = NOW
        self.store = Store(root / "db.sqlite3", root / "uploads", clock=lambda: self.now)
        self.store.seed_demo()
        self.server = create_server(self.store)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:" + str(self.server.server_address[1])
        self.client = build_opener(ProxyHandler({}), HTTPCookieProcessor(CookieJar()))
        self.csrf = ""
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, method, path, data=None, headers=None):
        h = {"Content-Type": "application/json", "X-CSRF-Token": self.csrf}
        h.update(headers or {})
        payload = json.dumps(data or {}).encode() if method != "GET" else None
        req = Request(self.base + path, data=payload, headers=h, method=method)
        try:
            response = self.client.open(req, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            body = response.read()
            decoded = json.loads(body) if "application/json" in response.headers.get("Content-Type", "") else body
            return response.status, decoded

    def login(self, user="student1"):
        status, result = self.request("POST", "/api/login", {"username": user, "password": "demo123"})
        self.assertEqual(200, status, result)
        self.csrf = result["data"]["csrf_token"]

    def to_college(self, student="student1", counselor="counselor1"):
        self.login(student)
        ids = []
        for key in ("transcript", "proof"):
            status, result = self.request("POST", "/api/uploads", {
                "project_id": "open", "material_key": key, "filename": key + ".pdf",
                "content_base64": base64.b64encode(PDF).decode()})
            self.assertEqual(201, status, result)
            ids.append(result["data"]["id"])
        status, result = self.request("POST", "/api/applications", {
            "project_id": "open", "fields": {"phone": "13800000000", "application_reason": "真实HTTP演示"},
            "attachment_ids": ids})
        self.assertEqual(201, status, result)
        application_id = result["data"]["id"]
        self.login(counselor)
        status, result = self.request("POST", "/api/applications/" + application_id + "/review",
                                      {"decision": "approve", "opinion": "材料齐全"})
        self.assertEqual(200, status, result)
        self.assertEqual("待学院复核", result["data"]["status"])
        return application_id

    def test_real_http_full_chain_student_counselor_college(self):
        application_id = self.to_college()
        self.login("college1")
        status, result = self.request("POST", REVIEW_PATH.format(application_id),
                                      {"decision": "approve", "opinion": "学院复核通过"})
        self.assertEqual(200, status, result)
        self.assertEqual("待公示", result["data"]["status"])
        status, result = self.request("GET", "/api/applications/" + application_id + "/audit")
        self.assertEqual(200, status, result)
        self.assertEqual({"counselor1", "college1"}, {log["reviewer_id"] for log in result["data"]})
        self.login("student1")
        status, result = self.request("GET", "/api/applications/" + application_id)
        self.assertEqual("待公示", result["data"]["status"])

    def test_real_http_cross_college_and_wrong_role_are_denied(self):
        application_id = self.to_college()
        path = REVIEW_PATH.format(application_id)
        self.login("college2")
        self.assertEqual(403, self.request("POST", path, {"decision": "approve", "opinion": "x"})[0])
        self.assertEqual(403, self.request("GET", "/api/applications/" + application_id)[0])
        self.login("student1")
        self.assertEqual(403, self.request("POST", path, {"decision": "approve", "opinion": "x"})[0])
        self.assertEqual("待学院复核", self.request("GET", "/api/applications/" + application_id)[1]["data"]["status"])

    def test_real_http_blank_reason_repeat_and_csrf(self):
        application_id = self.to_college()
        path = REVIEW_PATH.format(application_id)
        status, _ = self.request("POST", path, {"decision": "reject", "opinion": " "},
                                 {"X-CSRF-Token": "bad"})
        self.assertEqual(403, status)
        self.login("college1")
        self.assertEqual(400, self.request("POST", path, {"decision": "reject", "opinion": " "})[0])
        status, result = self.request("POST", path, {"decision": "reject", "opinion": "材料不全"})
        self.assertEqual(200, status, result)
        self.assertEqual("已驳回", result["data"]["status"])
        status, result = self.request("POST", path, {"decision": "approve", "opinion": "again"})
        self.assertEqual(409, status, result)
        self.assertEqual("已驳回", result["error"]["current_status"])
        self.assertEqual(2, len(self.request("GET", "/api/applications/" + application_id + "/audit")[1]["data"]))

    def test_real_http_unknown_endpoint_and_csrf_are_still_guarded(self):
        application_id = self.to_college()
        self.login("college1")
        self.assertEqual(404, self.request("GET", "/api/applications/" + application_id + "/publish")[0])
        self.assertEqual(403, self.request("POST", REVIEW_PATH.format(application_id),
                                          {"decision": "approve", "opinion": "x"},
                                          {"X-CSRF-Token": "bad"})[0])
        self.assertEqual("待学院复核",
                         self.request("GET", "/api/applications/" + application_id)[1]["data"]["status"])


if __name__ == "__main__":
    unittest.main()
