"""Integration: real threaded HTTP server, cookies, SQLite and on-disk files."""
import base64
from datetime import datetime,timedelta
from http.client import HTTPConnection
from http.cookiejar import CookieJar
import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPCookieProcessor, ProxyHandler

from scholarship.domain import Store
from scholarship.server import create_server
from tests.test_unit import NOW, PDF


class HttpTest(unittest.TestCase):
    def setUp(self):
        scratch=Path(__file__).resolve().parents[1]/".test-tmp"
        scratch.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=scratch)
        root=Path(self.temp.name)
        self.now=NOW
        self.store=Store(root/"db.sqlite3",root/"uploads",clock=lambda:self.now)
        self.store.seed_demo()
        self.server=create_server(self.store)
        self.thread=Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.base="http://127.0.0.1:"+str(self.server.server_address[1])
        self.client=build_opener(ProxyHandler({}),HTTPCookieProcessor(CookieJar()))
        self.csrf=""
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self,method,path,data=None,headers=None,raw=None):
        h={"Content-Type":"application/json","X-CSRF-Token":self.csrf}
        h.update(headers or {})
        payload=raw if raw is not None else (json.dumps(data or {}).encode() if method!="GET" else None)
        req=Request(self.base+path,data=payload,headers=h,method=method)
        try:
            response=self.client.open(req,timeout=5)
        except HTTPError as error:
            response=error
        with response:
            body=response.read()
            decoded=json.loads(body) if "application/json" in response.headers.get("Content-Type","") else body
            return response.status,decoded,dict(response.headers)

    def login(self,user="student1"):
        status,result,_=self.request("POST","/api/login",{"username":user,"password":"demo123"})
        self.assertEqual(200,status,result)
        self.csrf=result["data"]["csrf_token"]

    def submit(self,user="student1"):
        self.login(user)
        ids=[]
        for key in ("transcript","proof"):
            status,result,_=self.request("POST","/api/uploads",{"project_id":"open","material_key":key,"filename":key+".pdf","content_base64":base64.b64encode(PDF).decode()})
            self.assertEqual(201,status,result)
            ids.append(result["data"]["id"])
        status,result,_=self.request("POST","/api/applications",{"project_id":"open","fields":{"phone":"13800000000","application_reason":"真实HTTP演示"},"attachment_ids":ids})
        self.assertEqual(201,status,result)
        return result["data"]

    def test_real_student_upload_submit_counselor_approve_flow(self):
        self.login()
        self.assertEqual(3,len(self.request("GET","/api/projects")[1]["data"]))
        a=self.submit()
        s,body,headers=self.request("GET","/api/attachments/"+a["attachments"][0]["id"])
        self.assertEqual((200,PDF),(s,body))
        self.assertIn("nosniff",headers["X-Content-Type-Options"])
        self.login("counselor1")
        s,result,_=self.request("POST","/api/applications/"+a["id"]+"/review",{"decision":"approve","opinion":"材料齐全"})
        self.assertEqual(200,s,result)
        self.assertEqual("待学院复核",result["data"]["status"])
        self.login()
        result=self.request("GET","/api/applications/"+a["id"]+"/audit")[1]["data"]
        self.assertEqual("counselor1",result[0]["reviewer_id"])

    def test_real_rejection_visible_and_repeat_blocked(self):
        a=self.submit()
        self.login("counselor1")
        path="/api/applications/"+a["id"]+"/review"
        self.assertEqual(400,self.request("POST",path,{"decision":"reject","opinion":"  "})[0])
        self.assertEqual(200,self.request("POST",path,{"decision":"reject","opinion":"证明不完整"})[0])
        self.assertEqual(409,self.request("POST",path,{"decision":"approve","opinion":"again"})[0])
        self.login()
        result=self.request("GET","/api/applications/"+a["id"])[1]["data"]
        self.assertEqual("已驳回",result["status"])
        self.assertEqual("证明不完整",result["rejection_reason"])

    def test_real_horizontal_access_and_out_of_scope_counselor_are_blocked(self):
        a=self.submit()
        self.login("student2")
        self.assertEqual(403,self.request("GET","/api/applications/"+a["id"])[0])
        self.assertEqual(403,self.request("PATCH","/api/applications/"+a["id"],{"fields":{}})[0])
        self.assertEqual(403,self.request("GET","/api/attachments/"+a["attachments"][0]["id"])[0])
        self.login("counselor2")
        self.assertEqual([],self.request("GET","/api/applications")[1]["data"])
        self.assertEqual(403,self.request("POST","/api/applications/"+a["id"]+"/review",{"decision":"approve","opinion":"x"})[0])

    def test_real_http_duplicate_keeps_one_record(self):
        a=self.submit()
        s,result,_=self.request("POST","/api/applications",{"project_id":"open"})
        self.assertEqual(200,s,result)
        self.assertEqual(a["id"],result["data"]["id"])
        self.assertEqual(1,len(self.request("GET","/api/applications")[1]["data"]))

    def test_real_unauthenticated_csrf_unpublished_and_malformed_payload(self):
        self.assertEqual(401,self.request("GET","/api/projects")[0])
        self.login()
        self.assertEqual(404,self.request("GET","/api/projects/draft")[0])
        self.assertEqual(403,self.request("POST","/api/applications",headers={"X-CSRF-Token":"bad"})[0])
        self.assertEqual(400,self.request("POST","/api/uploads",raw=b"{")[0])

    def test_real_http_before_open_and_exact_deadline_do_not_create_application(self):
        self.login()
        p=self.request("GET","/api/projects/open")[1]["data"]
        for moment in (datetime.fromisoformat(p["open_at"])-timedelta(microseconds=1),datetime.fromisoformat(p["deadline"])):
            self.now=moment
            status,body,_=self.request("POST","/api/applications",{"project_id":"open","fields":{"phone":"138","application_reason":"test"},"attachment_ids":[]})
            self.assertEqual(409,status,body)
            self.assertEqual("WINDOW_CLOSED",body["error"]["code"])
            self.assertEqual([],self.request("GET","/api/applications")[1]["data"])

    def test_real_http_non_ascii_csrf_header_returns_json_403(self):
        self.login()
        status,body,_=self.request("POST","/api/uploads",headers={"X-CSRF-Token":"é"})
        self.assertEqual(403,status,body)
        self.assertEqual("CSRF_REQUIRED",body["error"]["code"])

    def test_http_json_body_size_and_negative_content_length_are_rejected(self):
        self.login()
        # Send only the oversized declaration. A correct early refusal can close
        # while a high-level client is still sending its multi-megabyte body.
        connection=HTTPConnection("127.0.0.1",self.server.server_address[1],timeout=5)
        try:
            connection.putrequest("POST","/api/uploads")
            connection.putheader("Content-Length",str(3*1024*1024+1))
            connection.endheaders()
            response=connection.getresponse()
            self.assertEqual(413,response.status)
            self.assertEqual("BODY_TOO_LARGE",json.loads(response.read())["error"]["code"])
        finally:
            connection.close()
        self.assertEqual(400,self.request("POST","/api/uploads",raw=b"",headers={"Content-Length":"-1"})[0])

if __name__=="__main__":
    unittest.main()
