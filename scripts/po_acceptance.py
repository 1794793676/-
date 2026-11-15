"""Developer-provided, independently runnable PO replay tool.

Starts a real isolated server; performs 18 observable acceptance checks over HTTP.
It does not declare a human PO decision. A PO must inspect its evidence.
"""
import argparse
import base64
from datetime import datetime,timedelta,timezone
import hashlib
from http.client import HTTPConnection
import json
from pathlib import Path
import sys
import tempfile
from threading import Thread

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scholarship.domain import Store
from scholarship.server import create_server

PDF=b"%PDF-1.4\n% PO teaching fixture\n%%EOF\n"
FIELDS={"phone":"13800000000","application_reason":"教学申请：支持完成学业"}


def require(condition,message):
    if not condition:
        raise AssertionError(message)


class Client:
    """http.client always connects directly to the local server, ignoring proxies."""
    def __init__(self,port):
        self.port,self.cookie,self.csrf=port,"",""

    def call(self,method,path,data=None,headers=None):
        h={"Content-Type":"application/json","Cookie":self.cookie,"X-CSRF-Token":self.csrf}
        h.update(headers or {})
        connection=HTTPConnection("127.0.0.1",self.port,timeout=5)
        try:
            connection.request(method,path,body=json.dumps(data or {}).encode() if method!="GET" else None,headers=h)
            response=connection.getresponse()
            body=response.read()
            if response.getheader("Set-Cookie"):
                self.cookie=response.getheader("Set-Cookie").split(";",1)[0]
            value=json.loads(body) if "application/json" in response.getheader("Content-Type","") else body
            return response.status,value
        finally:
            connection.close()

    def login(self,username):
        status,value=self.call("POST","/api/login",{"username":username,"password":"demo123"})
        require(status==200,"演示登录失败")
        self.csrf=value["data"]["csrf_token"]
        return value["data"]

    def materials(self):
        ids=[]
        for key in ("transcript","proof"):
            status,value=self.call("POST","/api/uploads",{"project_id":"open","material_key":key,"filename":key+".pdf","content_base64":base64.b64encode(PDF).decode()})
            require(status==201,"真实上传失败")
            ids.append(value["data"]["id"])
        return ids


def run():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",help="保存实际观测结果的JSON路径")
    args=parser.parse_args()
    scratch=Path(__file__).resolve().parents[1]/".test-tmp"
    scratch.mkdir(exist_ok=True)
    results=[]
    with tempfile.TemporaryDirectory(dir=scratch) as directory:
        root=Path(directory)
        baseline=datetime(2026,10,19,8,0,tzinfo=timezone.utc)
        clock={"now":baseline}
        store=Store(root/"demo.sqlite3",root/"uploads",clock=lambda:clock["now"])
        store.seed_demo()
        server=create_server(store)
        thread=Thread(target=server.serve_forever,daemon=True)
        thread.start()
        port=server.server_address[1]
        student=Client(port)
        other=Client(port)
        counselor=Client(port)
        state={}

        def check(number,story,title,callback):
            try:
                observation=callback()
                results.append({"case":number,"story":story,"title":title,"passed":True,"observed":observation})
                print(f"PASS {number:02d} {story} {title}",flush=True)
            except Exception as error:
                results.append({"case":number,"story":story,"title":title,"passed":False,"observed":str(error)})
                print(f"FAIL {number:02d} {story} {title}: {error}",flush=True)

        def anonymous():
            s,v=student.call("GET","/api/projects")
            require(s==401 and v["error"]["code"]=="AUTH_REQUIRED","匿名请求未被拒绝")
            return {"http_status":s}

        def login():
            user=student.login("student1")["user"]
            require(user["id"]=="student1" and user["role"]=="student","会话身份错误")
            return {"user_id":user["id"],"role":user["role"]}

        def notices():
            s,v=student.call("GET","/api/projects")
            require(s==200 and {p["id"] for p in v["data"]}=={"open","future","closed"},"通知列表泄露未发布或遗漏已发布")
            s,v=student.call("GET","/api/projects/open")
            p=v["data"]
            require(s==200 and p["conditions"] and len(p["required_fields"])==2 and len(p["required_materials"])==2 and p["open_at"]<p["deadline"],"通知信息不完整")
            state["project"]=p
            return {"published_count":3,"fields":p["required_fields"],"materials":p["required_materials"]}

        def hidden_closed():
            a,_=student.call("GET","/api/projects/draft")
            b,v=student.call("GET","/api/projects/closed")
            require(a==404 and b==200 and v["data"]["window_state"]=="申请已结束" and not v["data"]["can_apply"],"未发布隐藏/截止状态错误")
            return {"unpublished_status":a,"closed_readable_status":b,"can_apply":False}

        def missing():
            ids=student.materials()
            state["ids"]=ids
            seen=[]
            for fields,files,label in [({"application_reason":"x"},ids,"联系电话"),({"phone":"138"},ids,"申请理由"),(FIELDS,[ids[1]],"成绩单"),(FIELDS,[ids[0]],"证明材料")]:
                s,v=student.call("POST","/api/applications",{"project_id":"open","fields":fields,"attachment_ids":files})
                require(s==400 and v["error"]["details"]==[label],"逐项缺失未阻止："+label)
                seen.append(label)
            _,v=student.call("GET","/api/applications")
            require(v["data"]==[],"不完整申请产生了记录")
            return {"individually_blocked":seen,"application_count":0}

        def real_file():
            s,v=student.call("GET","/api/attachments/"+state["ids"][0])
            require(s==200 and v==PDF,"附件下载不是原始文件字节")
            return {"http_status":s,"bytes":len(v),"sha256":hashlib.sha256(v).hexdigest()}

        def submit():
            s,v=student.call("POST","/api/applications",{"project_id":"open","fields":FIELDS,"attachment_ids":state["ids"]})
            a=v["data"]
            require(s==201 and a["id"].startswith("APP-") and a["status"]=="待辅导员审核" and a["submitted_at"]=="2026-10-19T08:00:00+00:00","提交结果错误")
            state["application"]=a
            return {"http_status":s,"id":a["id"],"status":a["status"],"submitted_at":a["submitted_at"]}

        def duplicate():
            s,v=student.call("POST","/api/applications",{"project_id":"open"})
            _,rows=student.call("GET","/api/applications")
            require(s==200 and v["data"]["id"]==state["application"]["id"] and len(rows["data"])==1,"重复提交生成了新申请")
            return {"http_status":s,"application_count":len(rows["data"])}

        def cross_owner():
            other.login("student2")
            aid=state["application"]["id"]
            statuses=[other.call("GET","/api/applications/"+aid)[0],other.call("PATCH","/api/applications/"+aid,{"fields":{"phone":"changed"}})[0],other.call("GET","/api/attachments/"+state["ids"][0])[0],student.call("POST","/api/applications",{"project_id":"open","student_id":"student2"})[0]]
            require(statuses==[403,403,403,403],"他人申请/材料或代提交未拒绝")
            _,v=student.call("GET","/api/applications/"+aid)
            require(v["data"]["fields"]==FIELDS,"越权改变了字段")
            return {"statuses":statuses,"fields_unchanged":True}

        def window():
            observed=[]
            try:
                for moment in (datetime.fromisoformat(state["project"]["open_at"])-timedelta(microseconds=1),datetime.fromisoformat(state["project"]["deadline"])):
                    clock["now"]=moment
                    s,v=other.call("POST","/api/applications",{"project_id":"open","fields":FIELDS,"attachment_ids":[]})
                    require(s==409 and v["error"]["code"]=="WINDOW_CLOSED","开放前/截止时刻未拒绝")
                    observed.append({"system_time":moment.isoformat(),"http_status":s})
                _,v=other.call("GET","/api/applications")
                require(v["data"]==[],"时间拒绝后仍生成申请")
                return observed
            finally:
                clock["now"]=baseline

        def scope():
            counselor.login("counselor2")
            aid=state["application"]["id"]
            _,v=counselor.call("GET","/api/applications")
            require(v["data"]==[],"跨范围列表泄露")
            statuses=[counselor.call("GET","/api/applications/"+aid)[0],counselor.call("GET","/api/attachments/"+state["ids"][0])[0],counselor.call("POST","/api/applications/"+aid+"/review",{"decision":"approve","opinion":"x"})[0]]
            require(statuses==[403,403,403],"跨范围查看/审核未拒绝")
            return {"statuses":statuses,"visible_applications":0}

        def approve():
            counselor.login("counselor1")
            aid=state["application"]["id"]
            s,v=counselor.call("POST","/api/applications/"+aid+"/review",{"decision":"approve","opinion":"材料完整"})
            _,log=student.call("GET","/api/applications/"+aid+"/audit")
            require(s==200 and v["data"]["status"]=="待学院复核" and len(log["data"])==1 and log["data"][0]["reviewer_id"]=="counselor1" and log["data"][0]["opinion"]=="材料完整" and log["data"][0]["reviewed_at"]=="2026-10-19T08:00:00+00:00","通过未原子记录完整审计")
            return {"status":v["data"]["status"],"review":log["data"][0]}

        def repeated_review():
            aid=state["application"]["id"]
            s,v=counselor.call("POST","/api/applications/"+aid+"/review",{"decision":"reject","opinion":"again"})
            _,log=student.call("GET","/api/applications/"+aid+"/audit")
            require(s==409 and v["error"]["current_status"]=="待学院复核" and len(log["data"])==1,"重复审核改变状态/增加日志")
            return {"http_status":s,"current_status":v["error"]["current_status"],"review_count":1}

        def blank_reject():
            ids=other.materials()
            s,v=other.call("POST","/api/applications",{"project_id":"open","fields":FIELDS,"attachment_ids":ids})
            require(s==201,"第二学生申请准备失败")
            state["second"]=v["data"]
            aid=v["data"]["id"]
            s,v=counselor.call("POST","/api/applications/"+aid+"/review",{"decision":"reject","opinion":" \t"})
            _,a=other.call("GET","/api/applications/"+aid)
            _,logs=other.call("GET","/api/applications/"+aid+"/audit")
            require(s==400 and a["data"]["status"]=="待辅导员审核" and logs["data"]==[],"空驳回改变了申请")
            return {"http_status":s,"status":a["data"]["status"],"review_count":0}

        def reject():
            aid=state["second"]["id"]
            s,v=counselor.call("POST","/api/applications/"+aid+"/review",{"decision":"reject","opinion":"证明材料不符合要求"})
            _,a=other.call("GET","/api/applications/"+aid)
            require(s==200 and a["data"]["status"]=="已驳回" and a["data"]["rejection_reason"]=="证明材料不符合要求","驳回理由不可见")
            return {"status":a["data"]["status"],"reason":a["data"]["rejection_reason"]}

        def student_review():
            s,_=student.call("POST","/api/applications/"+state["application"]["id"]+"/review",{"decision":"approve","opinion":"x"})
            require(s==403,"学生可发起审核")
            return {"http_status":s}

        def csrf():
            a,_=student.call("POST","/api/applications",{"project_id":"open"},{"X-CSRF-Token":"bad"})
            b,_=student.call("POST","/api/applications",{"project_id":"open"},{"Origin":"https://evil.test"})
            require([a,b]==[403,403],"CSRF或跨站请求未拒绝")
            return {"statuses":[a,b]}

        def persist():
            reopened=Store(root/"demo.sqlite3",root/"uploads",clock=lambda:baseline)
            reopened.seed_demo()
            a=reopened.get_application("student1",state["application"]["id"])
            require(a["status"]=="待学院复核" and len(reopened.get_audit("student1",a["id"]))==1,"重开数据丢失")
            return {"status":a["status"],"review_count":1,"persistent":True}

        try:
            for number,story,title,callback in [
                (1,"安全","匿名访问拒绝",anonymous),(2,"安全","登录与会话身份",login),
                (3,"US01","通知清单与完整详情",notices),(4,"US01","未发布隐藏与截止禁用",hidden_closed),
                (5,"US02","逐项缺少字段或材料",missing),(6,"US02","真实附件原字节下载",real_file),
                (7,"US02","完整申请唯一编号与时间",submit),(8,"US02","重复提交返回原编号",duplicate),
                (9,"US02","本人权限与数据不变",cross_owner),(10,"US02","开放前及恰截止拒绝",window),
                (11,"US03","辅导员管理范围限制",scope),(12,"US03","通过到待学院复核及完整审计",approve),
                (13,"US03","重复审核不推进不增日志",repeated_review),(14,"US03","空白驳回理由阻止",blank_reject),
                (15,"US03","驳回终止及本人查看理由",reject),(16,"US03","学生不可审核",student_review),
                (17,"安全","CSRF与跨站请求拒绝",csrf),(18,"持久化","重开数据库后记录保留",persist)]:
                check(number,story,title,callback)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
    summary={"recorded_at":datetime.now(timezone.utc).isoformat(),"method":"real local HTTP, isolated SQLite and disk files; http.client direct loopback", "scope":"US01-US03; developer replay evidence for independent PO review", "passed":sum(r["passed"] for r in results),"total":len(results),"results":results}
    if args.output:
        output=Path(args.output)
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"TOTAL={summary['total']} PASS={summary['passed']} FAIL={summary['total']-summary['passed']}")
    return 0 if summary["passed"]==18 else 1


if __name__=="__main__":
    raise SystemExit(run())
