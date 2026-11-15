"""Local teaching HTTP application with server-side sessions and CSRF checks."""
import argparse
from dataclasses import dataclass, field
from http.cookies import SimpleCookie, CookieError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
from threading import Lock
import time
from urllib.parse import quote, unquote, urlsplit

from .domain import AppError, Store

MAX_BODY = 3 * 1024 * 1024
STATIC = Path(__file__).resolve().parent / "static"
SECURITY_HEADERS = {
    "Cache-Control":"no-store",
    "X-Content-Type-Options":"nosniff",
    "X-Frame-Options":"DENY",
    "Referrer-Policy":"no-referrer",
    "Content-Security-Policy":"default-src 'self'; script-src 'self'; style-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
}


@dataclass
class Response:
    status: int
    body: bytes
    headers: dict = field(default_factory=dict)


class Application:
    def __init__(self, store, session_clock=None):
        self.store = store
        self.clock = session_clock or time.time
        self.sessions = {}
        self.lock = Lock()

    @staticmethod
    def json_response(status, data=None, error=None, headers=None):
        payload = {"ok":error is None}
        payload["data" if error is None else "error"] = data if error is None else error
        return Response(status,json.dumps(payload,ensure_ascii=False).encode("utf-8"),{"Content-Type":"application/json; charset=utf-8",**(headers or {})})

    @staticmethod
    def _sid(headers):
        cookie = SimpleCookie()
        try:
            cookie.load(headers.get("cookie",""))
        except CookieError:
            return ""
        return cookie["sid"].value if "sid" in cookie else ""

    def _session(self, headers):
        sid=self._sid(headers)
        with self.lock:
            session=self.sessions.get(sid)
            if session is None or session["expires_at"]<=self.clock():
                self.sessions.pop(sid,None)
                raise AppError(401,"AUTH_REQUIRED","会话不存在或已过期，请重新登录")
            return dict(session)

    @staticmethod
    def _body(headers, body):
        if not headers.get("content-type","").lower().startswith("application/json"):
            raise AppError(415,"JSON_REQUIRED","请使用JSON请求")
        if len(body)>MAX_BODY:
            raise AppError(413,"BODY_TOO_LARGE","请求体超过3 MiB限制")
        try:
            data=json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError,json.JSONDecodeError):
            raise AppError(400,"INVALID_JSON","JSON请求格式不正确") from None
        if not isinstance(data,dict):
            raise AppError(400,"INVALID_JSON","JSON必须为对象")
        return data

    def dispatch(self, method, path, headers=None, body=b""):
        headers={k.lower():v for k,v in (headers or {}).items()}
        try:
            host=headers.get("host", "localhost")
            try:
                hostname=urlsplit("//"+host).hostname
            except ValueError:
                hostname=None
            if hostname not in ("localhost","127.0.0.1","::1"):
                raise AppError(403,"INVALID_HOST","仅允许通过本机地址访问教学服务")
            if method not in ("GET","HEAD"):
                if headers.get("sec-fetch-site")=="cross-site" or (headers.get("origin") and headers["origin"]!="http://"+host):
                    raise AppError(403,"BAD_ORIGIN","跨站请求被拒绝")
            route=unquote(urlsplit(path).path)
            response=self._dispatch(method,route,headers,body)
        except AppError as error:
            response=self.json_response(error.status,error={"code":error.code,"message":error.message,"details":error.details,"current_status":error.current_status})
        response.headers={**SECURITY_HEADERS,**response.headers}
        return response

    def _dispatch(self, method, route, headers, body):
        static={"/":("index.html","text/html; charset=utf-8"),"/app.js":("app.js","text/javascript; charset=utf-8"),"/style.css":("style.css","text/css; charset=utf-8")}
        if method=="GET" and route in static:
            filename,content_type=static[route]
            return Response(200,(STATIC/filename).read_bytes(),{"Content-Type":content_type})
        if route=="/api/login" and method=="POST":
            data=self._body(headers,body)
            user=self.store.authenticate(data.get("username"),data.get("password"))
            sid,csrf=secrets.token_urlsafe(32),secrets.token_urlsafe(32)
            with self.lock:
                self.sessions.pop(self._sid(headers),None)
                self.sessions[sid]={"user_id":user["id"],"csrf_token":csrf,"expires_at":self.clock()+3600}
            return self.json_response(200,{"user":user,"csrf_token":csrf},headers={"Set-Cookie":"sid="+sid+"; Path=/; HttpOnly; SameSite=Strict; Max-Age=3600"})
        if not route.startswith("/api/"):
            raise AppError(404,"NOT_FOUND","页面不存在")
        session=self._session(headers)
        actor=session["user_id"]
        if method not in ("GET","HEAD"):
            submitted_token=headers.get("x-csrf-token","")
            if not submitted_token.isascii() or not secrets.compare_digest(submitted_token,session["csrf_token"]):
                raise AppError(403,"CSRF_REQUIRED","安全校验失败，请刷新会话")
        if route=="/api/session" and method=="GET":
            return self.json_response(200,{"user":self.store.get_user(actor),"csrf_token":session["csrf_token"]})
        if route=="/api/logout" and method=="POST":
            with self.lock:
                self.sessions.pop(self._sid(headers),None)
            return self.json_response(200,{"logged_out":True},headers={"Set-Cookie":"sid=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"})
        if route=="/api/projects" and method=="GET":
            return self.json_response(200,self.store.list_projects(actor))
        parts=route.strip("/").split("/")
        if len(parts)==3 and parts[:2]==["api","projects"] and method=="GET":
            return self.json_response(200,self.store.get_project(actor,parts[2]))
        if route=="/api/uploads" and method=="POST":
            data=self._body(headers,body)
            for key in ("project_id","material_key","filename","content_base64"):
                if not isinstance(data.get(key),str):
                    raise AppError(400,"INVALID_INPUT","附件字段格式不正确")
            return self.json_response(201,self.store.upload(actor,data["project_id"],data["material_key"],data["filename"],data["content_base64"]))
        if len(parts)==3 and parts[:2]==["api","attachments"] and method=="GET":
            item=self.store.get_attachment(actor,parts[2])
            return Response(200,Path(item["path"]).read_bytes(),{"Content-Type":item["content_type"],"Content-Disposition":"attachment; filename*=UTF-8''"+quote(item["filename"])})
        if route=="/api/publications/pending" and method=="GET":
            return self.json_response(200,self.store.pending_batches(actor))
        if route=="/api/publications" and method=="GET":
            return self.json_response(200,self.store.list_publications(actor))
        if route=="/api/publications" and method=="POST":
            data=self._body(headers,body)
            result=self.store.publish_batch(actor,data.get("project_id"),data.get("batch"),
                                           data.get("start_at"),data.get("end_at"),data.get("proposed_level"))
            return self.json_response(201,result)
        if len(parts)==3 and parts[:2]==["api","publications"] and method=="GET":
            return self.json_response(200,self.store.get_publication(actor,parts[2]))
        if len(parts)==4 and parts[:2]==["api","publications"] and parts[3]=="items" and method=="GET":
            return self.json_response(200,self.store.publication_items_for_office(actor,parts[2]))
        if len(parts)==4 and parts[:2]==["api","publications"] and parts[3]=="results" and method=="GET":
            return self.json_response(200,self.store.list_publication_results(actor,parts[2]))
        if len(parts)==4 and parts[:2]==["api","publications"] and parts[3]=="finalize" and method=="POST":
            data=self._body(headers,body)
            return self.json_response(200,self.store.finalize_batch(actor,parts[2],data.get("decisions"),data.get("objection_handled")))
        if route=="/api/results/me" and method=="GET":
            return self.json_response(200,self.store.get_my_results(actor))
        if route=="/api/applications":
            if method=="GET":
                return self.json_response(200,self.store.list_applications(actor))
            if method=="POST":
                data=self._body(headers,body)
                if not isinstance(data.get("project_id"),str):
                    raise AppError(400,"INVALID_INPUT","请选择通知项目")
                result=self.store.submit(actor,data["project_id"],data.get("fields",{}),data.get("attachment_ids",[]),data.get("student_id"))
                return self.json_response(200 if result["duplicate"] else 201,result)
        if len(parts)>=3 and parts[:2]==["api","applications"]:
            app_id=parts[2]
            if len(parts)==3 and method=="GET":
                return self.json_response(200,self.store.get_application(actor,app_id))
            if len(parts)==3 and method=="PATCH":
                data=self._body(headers,body)
                self.store.modify_application(actor,app_id,data.get("fields",{}))
            if len(parts)==4 and parts[3]=="audit" and method=="GET":
                return self.json_response(200,self.store.get_audit(actor,app_id))
            if len(parts)==4 and parts[3]=="review" and method=="POST":
                data=self._body(headers,body)
                return self.json_response(200,self.store.review(actor,app_id,data.get("decision"),data.get("opinion","")))
            if len(parts)==4 and parts[3]=="college-review" and method=="POST":
                data=self._body(headers,body)
                return self.json_response(200,self.store.college_review(actor,app_id,data.get("decision"),data.get("opinion","")))
            if len(parts)==4 and parts[3]=="result" and method=="GET":
                return self.json_response(200,self.store.get_application_result(actor,app_id))
        raise AppError(404,"NOT_FOUND","接口不存在")


def create_server(store, host="127.0.0.1", port=0):
    app=Application(store)
    class Handler(BaseHTTPRequestHandler):
        def handle_request(self):
            try:
                length=int(self.headers.get("Content-Length","0"))
                if length<0:
                    raise AppError(400,"INVALID_LENGTH","请求长度无效")
                if length>MAX_BODY:
                    raise AppError(413,"BODY_TOO_LARGE","请求体超过3 MiB限制")
                if self.headers.get("Transfer-Encoding"):
                    raise AppError(400,"INVALID_LENGTH","不支持分块请求")
                self.connection.settimeout(10)
                body=self.rfile.read(length) if length else b""
                result=app.dispatch(self.command,self.path,dict(self.headers),body)
            except ValueError:
                result=app.json_response(400,error={"code":"INVALID_LENGTH","message":"请求长度无效"})
            except AppError as error:
                result=app.json_response(error.status,error={"code":error.code,"message":error.message})
            self.send_response(result.status)
            for name,value in {**SECURITY_HEADERS,**result.headers}.items():
                self.send_header(name,value)
            self.send_header("Content-Length",str(len(result.body)))
            self.end_headers()
            self.wfile.write(result.body)
        do_GET=do_POST=do_PATCH=handle_request
        def log_message(self, format, *args):
            pass
    server=ThreadingHTTPServer((host,port),Handler)
    server.daemon_threads=True
    return server


def main():  # pragma: no cover -- CLI composition; production behavior tested below it.
    parser=argparse.ArgumentParser(description="奖助学金US01–06本地教学演示")
    parser.add_argument("--port",type=int,default=8080)
    parser.add_argument("--data-dir",default="runtime")
    args=parser.parse_args()
    root=Path(args.data_dir)
    store=Store(root/"scholarship.sqlite3",root/"uploads")
    store.seed_demo()
    server=create_server(store,port=args.port)
    print(f"教学演示：http://127.0.0.1:{server.server_address[1]}  密码demo123",flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__=="__main__":  # pragma: no cover
    main()
