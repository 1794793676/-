"""Unit contracts call the production dispatcher directly, without sockets."""
import base64
import json
from pathlib import Path
import tempfile
import unittest

from scholarship.domain import Store
from scholarship.server import Application
from tests.test_unit import NOW, PDF


class RouteTest(unittest.TestCase):
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

    def call(self, method, path, data=None, headers=None, raw=None):
        h = {"Host":"localhost:8080", "Content-Type":"application/json", "Cookie":self.cookie, "X-CSRF-Token":self.csrf}
        h.update(headers or {})
        body = json.dumps(data or {}).encode() if raw is None else raw
        return self.app.dispatch(method, path, h, body)

    def data(self, response, status=200):
        self.assertEqual(status, response.status, response.body)
        return json.loads(response.body)["data"]

    def login(self, user="student1"):
        r = self.call("POST", "/api/login", {"username":user,"password":"demo123"})
        d = self.data(r)
        self.cookie = r.headers["Set-Cookie"].split(";", 1)[0]
        self.csrf = d["csrf_token"]
        return r

    def materials(self):
        ids=[]
        for key in ("transcript", "proof"):
            d=self.data(self.call("POST", "/api/uploads", {"project_id":"open", "material_key":key,"filename":key+".pdf", "content_base64":base64.b64encode(PDF).decode()}),201)
            ids.append(d["id"])
        return ids

    def submit(self):
        return self.data(self.call("POST", "/api/applications", {"project_id":"open","fields":{"phone":"13800000000","application_reason":"学业支持"},"attachment_ids":self.materials()}),201)

    def test_route_requires_authenticated_session_not_actor_header(self):
        r=self.call("GET","/api/projects",headers={"X-User":"student1"})
        self.assertEqual(401,r.status)
        self.assertEqual("AUTH_REQUIRED",json.loads(r.body)["error"]["code"])

    def test_login_cookie_is_httponly_samesite_and_session_has_csrf(self):
        r=self.login()
        self.assertIn("HttpOnly",r.headers["Set-Cookie"])
        self.assertIn("SameSite=Strict",r.headers["Set-Cookie"])
        self.assertGreater(len(self.csrf),20)
        self.assertEqual("student1",self.data(self.call("GET","/api/session"))["user"]["id"])

    def test_login_failure_bad_json_wrong_shape_and_bad_host(self):
        for path,raw,headers,status in [("/api/login",b"{",{},400),("/api/login",b"[]",{},400),("/api/login",b"{}",{"Host":"evil.test"},403)]:
            with self.subTest(path=path,raw=raw,headers=headers):
                self.assertEqual(status,self.call("POST",path,raw=raw,headers=headers).status)
        self.assertEqual(401,self.call("POST","/api/login",{"username":"student1","password":"wrong"}).status)

    def test_cross_origin_login_and_authenticated_mutation_are_rejected(self):
        self.assertEqual(403,self.call("POST","/api/login",headers={"Origin":"https://evil.test"}).status)
        self.login()
        self.assertEqual(403,self.call("POST","/api/applications",headers={"Origin":"https://evil.test"}).status)
        self.assertEqual(403,self.call("POST","/api/applications",headers={"Sec-Fetch-Site":"cross-site"}).status)

    def test_csrf_missing_and_invalid_rejected(self):
        self.login()
        for token in ("", "bad"):
            self.assertEqual(403,self.call("POST","/api/uploads",headers={"X-CSRF-Token":token}).status)

    def test_csrf_non_ascii_header_returns_403_without_escaping_dispatch(self):
        self.login()
        try:
            result=self.call("POST","/api/uploads",headers={"X-CSRF-Token":"é"})
        except TypeError as error:
            self.fail("非法CSRF头必须返回403，不应抛出TypeError："+str(error))
        self.assertEqual(403,result.status)
        self.assertEqual("CSRF_REQUIRED",json.loads(result.body)["error"]["code"])

    def test_session_expiry_and_logout_invalidate_server_session(self):
        self.login()
        self.time += 3601
        self.assertEqual(401,self.call("GET","/api/projects").status)
        self.login()
        self.data(self.call("POST","/api/logout"))
        self.assertEqual(401,self.call("GET","/api/session").status)

    def test_published_project_routes_and_unpublished_404(self):
        self.login()
        self.assertEqual(3,len(self.data(self.call("GET","/api/projects"))))
        self.assertEqual("开放中",self.data(self.call("GET","/api/projects/open"))["window_state"])
        self.assertEqual(404,self.call("GET","/api/projects/draft").status)

    def test_submission_duplicate_detail_audit_and_immutable_routes(self):
        self.login()
        a=self.submit()
        self.assertEqual(a["id"],self.data(self.call("POST","/api/applications",{"project_id":"open"}))["id"])
        self.assertEqual(a["id"],self.data(self.call("GET","/api/applications/"+a["id"]))["id"])
        self.assertEqual([],self.data(self.call("GET","/api/applications/"+a["id"]+"/audit")))
        self.assertEqual(1,len(self.data(self.call("GET","/api/applications"))))
        self.assertEqual(409,self.call("PATCH","/api/applications/"+a["id"],{"fields":{}}).status)

    def test_counselor_review_and_repeat_error_preserve_current_status(self):
        self.login()
        a=self.submit()
        self.login("counselor1")
        result=self.data(self.call("POST","/api/applications/"+a["id"]+"/review",{"decision":"approve","opinion":"完整"}))
        self.assertEqual("待学院复核",result["status"])
        r=self.call("POST","/api/applications/"+a["id"]+"/review",{"decision":"approve","opinion":"再次"})
        self.assertEqual(409,r.status)
        self.assertEqual("待学院复核",json.loads(r.body)["error"]["current_status"])

    def test_file_download_uses_permission_and_attachment_disposition(self):
        self.login()
        a=self.submit()
        path="/api/attachments/"+a["attachments"][0]["id"]
        r=self.call("GET",path)
        self.assertEqual(200,r.status)
        self.assertEqual(PDF,r.body)
        self.assertIn("attachment",r.headers["Content-Disposition"])
        self.login("student2")
        self.assertEqual(403,self.call("GET",path).status)

    def test_missing_fields_are_json_error_details(self):
        self.login()
        r=self.call("POST","/api/applications",{"project_id":"open"})
        self.assertEqual(400,r.status)
        self.assertEqual(4,len(json.loads(r.body)["error"]["details"]))

    def test_static_shell_has_no_private_seed_data_and_paths_are_whitelisted(self):
        r=self.call("GET","/")
        self.assertEqual(200,r.status)
        self.assertIn("高校奖助学金".encode(),r.body)
        self.assertNotIn(b"13800000000",r.body)
        for path in ("/app.js","/style.css"):
            self.assertEqual(200,self.call("GET",path).status)
        self.assertEqual(404,self.call("GET","/../domain.py").status)
        self.login()
        self.assertEqual(404,self.call("GET","/api/unknown").status)

    def test_unsupported_content_type_and_malformed_fields_fail_safely(self):
        self.login()
        self.assertEqual(415,self.call("POST","/api/applications",headers={"Content-Type":"text/plain"}).status)
        self.assertEqual(400,self.call("POST","/api/applications",{"project_id":"open","fields":[]}).status)
        self.assertEqual(400,self.call("POST","/api/uploads",{"filename":[]} ).status)

if __name__ == "__main__":
    unittest.main()
