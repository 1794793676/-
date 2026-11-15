"""US01–US03 business rules. SQLite is the source of truth for all permissions.

Demo users and policies are teaching fixtures, not real university data.
"""
import base64
import binascii
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from pathlib import Path
import sqlite3
import uuid

MAX_FILE_SIZE = 2 * 1024 * 1024
DEMO_SALT = b"scholarship-local-teaching-only"
DEMO_HASH = hashlib.pbkdf2_hmac("sha256", b"demo123", DEMO_SALT, 120000)
FIELDS = [{"key":"phone", "label":"联系电话"}, {"key":"application_reason", "label":"申请理由"}]
MATERIALS = [{"key":"transcript", "label":"成绩单"}, {"key":"proof", "label":"证明材料"}]
COLLEGE_REVIEWERS = [("college1","周老师（演示）","college_reviewer","计算机学院",None),
                     ("college2","吴老师（演示）","college_reviewer","文学院",None)]
STUDENT_AFFAIRS = [("office1","学生处老师（演示）","student_affairs","学生处",None)]
PUBLIC_ITEM_FIELDS = ("masked_name","masked_student_id","college","project_name","proposed_level")


class AppError(Exception):
    def __init__(self, status, code, message, details=None, current_status=None):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message
        self.details = details or []
        self.current_status = current_status


class Store:
    def __init__(self, db_path, upload_dir, clock=None):
        self.db_path, self.upload_dir = Path(db_path), Path(upload_dir)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        with self.connection() as con:
            con.executescript("""
              CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL,
                college TEXT NOT NULL, counselor_id TEXT);
              CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, batch TEXT NOT NULL,
                conditions TEXT NOT NULL, required_fields TEXT NOT NULL,
                required_materials TEXT NOT NULL, open_at TEXT NOT NULL,
                deadline TEXT NOT NULL, published INTEGER NOT NULL);
              CREATE TABLE IF NOT EXISTS applications (
                id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES users(id),
                project_id TEXT NOT NULL REFERENCES projects(id), batch TEXT NOT NULL,
                fields TEXT NOT NULL, status TEXT NOT NULL, submitted_at TEXT NOT NULL,
                rejection_reason TEXT NOT NULL DEFAULT '',
                UNIQUE(student_id, project_id, batch));
              CREATE TABLE IF NOT EXISTS attachments (
                id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id),
                project_id TEXT NOT NULL REFERENCES projects(id), material_key TEXT NOT NULL,
                filename TEXT NOT NULL, path TEXT NOT NULL, size INTEGER NOT NULL,
                sha256 TEXT NOT NULL, content_type TEXT NOT NULL,
                application_id TEXT REFERENCES applications(id));
              CREATE TABLE IF NOT EXISTS reviews (
                id TEXT PRIMARY KEY, application_id TEXT NOT NULL REFERENCES applications(id),
                reviewer_id TEXT NOT NULL REFERENCES users(id), decision TEXT NOT NULL,
                opinion TEXT NOT NULL, reviewed_at TEXT NOT NULL);
              CREATE INDEX IF NOT EXISTS attachment_application ON attachments(application_id);
            """)
        self.migrate_college_review()
        self.migrate_publication_results()

    @contextmanager
    def connection(self):
        con = sqlite3.connect(self.db_path, timeout=20)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        try:
            with con:
                yield con
        finally:
            con.close()

    def migrate_college_review(self):
        """US04: 幂等补齐学院审核员与状态索引，不改动任何既有教学数据。"""
        with self.connection() as con:
            con.executemany("INSERT OR IGNORE INTO users VALUES (?,?,?,?,?)", COLLEGE_REVIEWERS)
            con.execute("CREATE INDEX IF NOT EXISTS application_status ON applications(status)")

    def migrate_publication_results(self):
        """US05/US06: 幂等补齐学生处账号与公示/结果表，不对既有表做任何 ALTER。"""
        with self.connection() as con:
            con.executemany("INSERT OR IGNORE INTO users VALUES (?,?,?,?,?)", STUDENT_AFFAIRS)
            con.executescript("""
              CREATE TABLE IF NOT EXISTS publications (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                batch TEXT NOT NULL, proposed_level TEXT NOT NULL,
                start_at TEXT NOT NULL, end_at TEXT NOT NULL,
                published_by TEXT NOT NULL REFERENCES users(id), published_at TEXT NOT NULL,
                status TEXT NOT NULL, objection_handled INTEGER NOT NULL DEFAULT 0,
                confirmed_by TEXT, confirmed_at TEXT);
              CREATE TABLE IF NOT EXISTS publication_items (
                publication_id TEXT NOT NULL REFERENCES publications(id),
                application_id TEXT NOT NULL REFERENCES applications(id),
                PRIMARY KEY (publication_id, application_id));
              CREATE TABLE IF NOT EXISTS results (
                application_id TEXT PRIMARY KEY REFERENCES applications(id),
                publication_id TEXT NOT NULL REFERENCES publications(id),
                decision TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '',
                confirmed_by TEXT NOT NULL, confirmed_at TEXT NOT NULL);
              CREATE INDEX IF NOT EXISTS publication_batch ON publications(project_id,batch);
            """)

    def seed_demo(self):
        now = self.clock()
        users = [("student1","林同学（演示）","student","计算机学院","counselor1"),
                 ("student2","陈同学（演示）","student","计算机学院","counselor1"),
                 ("student3","王同学（演示）","student","文学院","counselor2"),
                 ("counselor1","李老师（演示）","counselor","计算机学院",None),
                 ("counselor2","赵老师（演示）","counselor","文学院",None)]
        projects = [("open","2026秋季学业奖学金",-1,7,1),
                    ("future","冬季助学金（即将开放）",1,8,1),
                    ("closed","上期奖学金（已结束）",-10,-1,1),
                    ("draft","未发布通知",-1,7,0)]
        with self.connection() as con:
            con.executemany("INSERT OR IGNORE INTO users VALUES (?,?,?,?,?)", users)
            for pid, name, start, end, published in projects:
                con.execute("INSERT OR IGNORE INTO projects VALUES (?,?,?,?,?,?,?,?,?)",
                            (pid,name,"2026秋季第一批","全日制在校生；如实填写申请信息并提交通知列明的材料。",
                             json.dumps(FIELDS,ensure_ascii=False),json.dumps(MATERIALS,ensure_ascii=False),
                             (now+timedelta(days=start)).isoformat(),(now+timedelta(days=end)).isoformat(),published))

    def get_user(self, actor):
        with self.connection() as con:
            row = con.execute("SELECT * FROM users WHERE id=?", (actor,)).fetchone()
        if row is None:
            raise AppError(401,"AUTH_REQUIRED","请先登录演示账号")
        return dict(row)

    def authenticate(self, username, password):
        if not isinstance(username,str) or not isinstance(password,str) or len(password)>200:
            raise AppError(401,"BAD_CREDENTIALS","账号或密码错误")
        derived = hashlib.pbkdf2_hmac("sha256",password.encode(),DEMO_SALT,120000)
        with self.connection() as con:
            row = con.execute("SELECT * FROM users WHERE id=?",(username,)).fetchone()
        if row is None or not hmac.compare_digest(derived,DEMO_HASH):
            raise AppError(401,"BAD_CREDENTIALS","账号或密码错误")
        return dict(row)

    def _project(self, row):
        if row is None:
            raise AppError(404,"NOT_FOUND","通知不存在或尚未发布")
        item = dict(row)
        item["required_fields"] = json.loads(item["required_fields"])
        item["required_materials"] = json.loads(item["required_materials"])
        now = self.clock()
        opened, deadline = datetime.fromisoformat(item["open_at"]), datetime.fromisoformat(item["deadline"])
        item["window_state"] = "未开始" if now<opened else ("申请已结束" if now>=deadline else "开放中")
        item["can_apply"] = opened<=now<deadline
        return item

    def list_projects(self, actor):
        self.get_user(actor)
        with self.connection() as con:
            return [self._project(row) for row in con.execute("SELECT * FROM projects WHERE published=1 ORDER BY id")]

    def get_project(self, actor, project_id):
        self.get_user(actor)
        with self.connection() as con:
            return self._project(con.execute("SELECT * FROM projects WHERE id=? AND published=1",(project_id,)).fetchone())

    @staticmethod
    def _student(user):
        if user["role"]!="student":
            raise AppError(403,"FORBIDDEN","仅学生本人可提交申请与材料")

    @staticmethod
    def _public_attachment(row):
        return {k:row[k] for k in ("id","material_key","filename","size","sha256","content_type")}

    def upload(self, actor, project_id, material_key, filename, content_base64):
        self._student(self.get_user(actor))
        project = self.get_project(actor,project_id)
        if material_key not in [m["key"] for m in project["required_materials"]]:
            raise AppError(400,"UNKNOWN_MATERIAL","通知未要求此材料")
        if not isinstance(filename,str) or not filename.strip() or not isinstance(content_base64,str):
            raise AppError(400,"INVALID_FILE","请选择有效文件")
        filename = filename.replace("\\","/").rsplit("/",1)[-1][:200]
        if not filename or any(ord(c)<32 for c in filename):
            raise AppError(400,"INVALID_FILE","文件名无效")
        try:
            data = base64.b64decode(content_base64,validate=True)
        except (ValueError,binascii.Error):
            raise AppError(400,"INVALID_FILE","附件编码无效") from None
        if not data:
            raise AppError(400,"INVALID_FILE","附件不能为空")
        if len(data)>MAX_FILE_SIZE:
            raise AppError(400,"FILE_TOO_LARGE","单个文件不得超过2 MiB")
        ext = Path(filename).suffix.lower()
        types = {".pdf":("application/pdf",b"%PDF-"),".png":("image/png",b"\x89PNG\r\n\x1a\n"),".jpg":("image/jpeg",b"\xff\xd8\xff"),".jpeg":("image/jpeg",b"\xff\xd8\xff")}
        if ext not in types or not data.startswith(types[ext][1]):
            raise AppError(400,"FILE_TYPE","仅支持内容与扩展名一致的PDF、PNG或JPG")
        aid = uuid.uuid4().hex
        path = self.upload_dir.resolve()/(aid+ext)
        path.write_bytes(data)
        item = {"id":aid,"material_key":material_key,"filename":filename,"size":len(data),"sha256":hashlib.sha256(data).hexdigest(),"content_type":types[ext][0]}
        try:
            with self.connection() as con:
                con.execute("INSERT INTO attachments VALUES (?,?,?,?,?,?,?,?,?,NULL)",
                            (aid,actor,project_id,material_key,filename,str(path),len(data),item["sha256"],item["content_type"]))
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return item

    def _authorized_application(self, con, user, application_id):
        row = con.execute("SELECT a.*, u.counselor_id, u.name AS student_name, u.college AS college FROM applications a JOIN users u ON a.student_id=u.id WHERE a.id=?",(application_id,)).fetchone()
        if row is None:
            raise AppError(404,"NOT_FOUND","申请不存在")
        allowed = ((user["role"]=="student" and row["student_id"]==user["id"])
                   or (user["role"]=="counselor" and row["counselor_id"]==user["id"])
                   or (user["role"]=="college_reviewer" and row["college"]==user["college"]))
        if not allowed:
            raise AppError(403,"FORBIDDEN","无权访问此申请或材料")
        return row

    def _application(self, con, row, duplicate=False):
        result = dict(row)
        result.pop("counselor_id",None)
        result.pop("college",None)
        result["fields"] = json.loads(result["fields"])
        result["attachments"] = [self._public_attachment(r) for r in con.execute("SELECT * FROM attachments WHERE application_id=? ORDER BY material_key",(row["id"],))]
        result["duplicate"] = duplicate
        return result

    def submit(self, actor, project_id, fields, attachment_ids, target_student_id=None):
        self._student(self.get_user(actor))
        if target_student_id is not None and target_student_id!=actor:
            raise AppError(403,"FORBIDDEN","禁止代他人提交申请")
        project = self.get_project(actor,project_id)
        if not isinstance(fields,dict) or not isinstance(attachment_ids,list) or not all(isinstance(x,str) for x in attachment_ids):
            raise AppError(400,"INVALID_INPUT","表单或材料编号格式不正确")
        with self.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            old = con.execute("SELECT * FROM applications WHERE student_id=? AND project_id=? AND batch=?",(actor,project_id,project["batch"])).fetchone()
            if old:
                return self._application(con,old,duplicate=True)
            submitted_at=self.clock()
            if not (datetime.fromisoformat(project["open_at"])<=submitted_at<datetime.fromisoformat(project["deadline"])):
                raise AppError(409,"WINDOW_CLOSED","当前不在申请开放时间内",[project["open_at"],project["deadline"]])
            missing = [f["label"] for f in project["required_fields"] if not isinstance(fields.get(f["key"]),str) or not fields[f["key"]].strip()]
            normalized = {f["key"]:str(fields.get(f["key"],"")).strip() for f in project["required_fields"]}
            if any(len(v)>2000 for v in normalized.values()):
                raise AppError(400,"INVALID_INPUT","单项内容不得超过2000字符")
            files=[]
            for aid in dict.fromkeys(attachment_ids):
                row = con.execute("SELECT * FROM attachments WHERE id=?",(aid,)).fetchone()
                if row is None:
                    raise AppError(404,"NOT_FOUND","材料不存在")
                if row["owner_id"]!=actor:
                    raise AppError(403,"FORBIDDEN","不能使用他人的材料")
                if row["project_id"]!=project_id:
                    raise AppError(400,"WRONG_PROJECT","材料属于其他项目")
                files.append(row)
            available = {f["material_key"] for f in files}
            missing += [m["label"] for m in project["required_materials"] if m["key"] not in available]
            if missing:
                raise AppError(400,"INCOMPLETE","请补齐以下必填信息和材料",missing)
            if len(files)!=len(available):
                raise AppError(400,"INVALID_INPUT","每类材料只提交一个文件")
            app_id = "APP-"+uuid.uuid4().hex[:16].upper()
            con.execute("INSERT INTO applications(id,student_id,project_id,batch,fields,status,submitted_at) VALUES (?,?,?,?,?,?,?)",
                        (app_id,actor,project_id,project["batch"],json.dumps(normalized,ensure_ascii=False),"待辅导员审核",submitted_at.isoformat()))
            con.executemany("UPDATE attachments SET application_id=? WHERE id=?",[(app_id,r["id"]) for r in files])
            return self._application(con,con.execute("SELECT * FROM applications WHERE id=?",(app_id,)).fetchone())

    def list_applications(self, actor):
        user = self.get_user(actor)
        with self.connection() as con:
            if user["role"]=="student":
                rows=con.execute("SELECT a.*,u.name AS student_name FROM applications a JOIN users u ON a.student_id=u.id WHERE a.student_id=? ORDER BY submitted_at DESC",(actor,)).fetchall()
            elif user["role"]=="college_reviewer":
                rows=con.execute("SELECT a.*,u.name AS student_name FROM applications a JOIN users u ON a.student_id=u.id WHERE u.college=? ORDER BY submitted_at DESC",(user["college"],)).fetchall()
            elif user["role"]=="counselor":
                rows=con.execute("SELECT a.*,u.name AS student_name FROM applications a JOIN users u ON a.student_id=u.id WHERE u.counselor_id=? ORDER BY submitted_at DESC",(actor,)).fetchall()
            else:
                raise AppError(403,"FORBIDDEN","该角色不通过申请列表读取数据，请使用公示与结果接口")
            return [self._application(con,r) for r in rows]

    def get_application(self, actor, application_id):
        user=self.get_user(actor)
        with self.connection() as con:
            return self._application(con,self._authorized_application(con,user,application_id))

    def modify_application(self, actor, application_id, fields):
        self.get_application(actor,application_id)
        raise AppError(409,"IMMUTABLE","已提交申请不可修改；本Sprint不含退补")

    def review(self, actor, application_id, decision, opinion):
        user=self.get_user(actor)
        if user["role"]!="counselor":
            raise AppError(403,"FORBIDDEN","仅负责该学生的辅导员可审核")
        with self.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            row=self._authorized_application(con,user,application_id)
            if row["status"]!="待辅导员审核":
                raise AppError(409,"ALREADY_REVIEWED","申请已处理，不能重复审核",current_status=row["status"])
            if decision not in ("approve","reject") or not isinstance(opinion,str) or len(opinion)>2000:
                raise AppError(400,"INVALID_DECISION","审核动作或意见格式无效")
            opinion=opinion.strip()
            if decision=="reject" and not opinion:
                raise AppError(400,"REASON_REQUIRED","驳回必须填写非空理由")
            status="待学院复核" if decision=="approve" else "已驳回"
            con.execute("UPDATE applications SET status=?,rejection_reason=? WHERE id=? AND status='待辅导员审核'",(status,opinion if decision=="reject" else "",application_id))
            con.execute("INSERT INTO reviews VALUES (?,?,?,?,?,?)",(uuid.uuid4().hex,application_id,actor,decision,opinion,self.clock().isoformat()))
            return self._application(con,con.execute("SELECT * FROM applications WHERE id=?",(application_id,)).fetchone())

    def college_review(self, actor, application_id, decision, opinion):
        """US04: 学院审核员仅可处理本学院「待学院复核」的申请。"""
        user=self.get_user(actor)
        if user["role"]!="college_reviewer":
            raise AppError(403,"FORBIDDEN","仅本学院审核员可复核申请")
        with self.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            row=self._authorized_application(con,user,application_id)
            if row["status"]!="待学院复核":
                raise AppError(409,"ALREADY_REVIEWED","申请已处理，不能重复复核",current_status=row["status"])
            if decision not in ("approve","reject") or not isinstance(opinion,str) or len(opinion)>2000:
                raise AppError(400,"INVALID_DECISION","复核动作或意见格式无效")
            opinion=opinion.strip()
            if decision=="reject" and not opinion:
                raise AppError(400,"REASON_REQUIRED","驳回必须填写非空理由")
            status="待公示" if decision=="approve" else "已驳回"
            con.execute("UPDATE applications SET status=?,rejection_reason=? WHERE id=? AND status='待学院复核'",
                        (status,opinion if decision=="reject" else "",application_id))
            con.execute("INSERT INTO reviews VALUES (?,?,?,?,?,?)",
                        (uuid.uuid4().hex,application_id,actor,decision,opinion,self.clock().isoformat()))
            return self._application(con,con.execute("SELECT * FROM applications WHERE id=?",(application_id,)).fetchone())

    def get_attachment(self, actor, attachment_id):
        user=self.get_user(actor)
        with self.connection() as con:
            row=con.execute("SELECT * FROM attachments WHERE id=?",(attachment_id,)).fetchone()
            if row is None:
                raise AppError(404,"NOT_FOUND","材料不存在")
            if row["owner_id"]!=actor:
                if not row["application_id"]:
                    raise AppError(403,"FORBIDDEN","无权访问未提交的材料")
                self._authorized_application(con,user,row["application_id"])
            return dict(row)

    def get_audit(self, actor, application_id):
        user=self.get_user(actor)
        with self.connection() as con:
            self._authorized_application(con,user,application_id)
            return [dict(r) for r in con.execute("SELECT * FROM reviews WHERE application_id=? ORDER BY reviewed_at,id",(application_id,))]

    # ---- US05 学生处整批公示 / US06 进度与最终结果 ----

    @staticmethod
    def _affairs(user):
        if user["role"]!="student_affairs":
            raise AppError(403,"FORBIDDEN","仅学生处可发布公示与确认最终结果")

    @staticmethod
    def _mask_name(name):
        base=str(name).split("（")[0].split("(")[0].strip()
        return (base[0] if base else "*")+"**"

    @staticmethod
    def _mask_student_id(student_id):
        text=str(student_id)
        return (text[0] if text else "*")+"***"+(text[-1] if len(text)>1 else "")

    @staticmethod
    def _parse_window(value):
        if not isinstance(value,str) or not value.strip():
            raise AppError(400,"INVALID_WINDOW","公示起止时间不能为空")
        try:
            moment=datetime.fromisoformat(value)
        except ValueError:
            raise AppError(400,"INVALID_WINDOW","公示起止时间必须是ISO 8601格式") from None
        if moment.tzinfo is None:
            moment=moment.replace(tzinfo=timezone.utc)
        return moment

    def _publication_meta(self, con, row):
        project=con.execute("SELECT name FROM projects WHERE id=?",(row["project_id"],)).fetchone()
        return {"id":row["id"],"project_id":row["project_id"],
                "project_name":project["name"] if project else "",
                "batch":row["batch"],"proposed_level":row["proposed_level"],
                "start_at":row["start_at"],"end_at":row["end_at"],
                "published_at":row["published_at"],"status":row["status"],
                "objection_handled":bool(row["objection_handled"]),
                "confirmed_by":row["confirmed_by"],"confirmed_at":row["confirmed_at"]}

    def _publication_items(self, con, publication_id, level):
        """公开名单：先查内部数据，再按白名单投影，任何新字段都进不了响应。"""
        rows=con.execute("""SELECT u.name AS student_name,u.id AS student_id,u.college,p.name AS project_name
                            FROM publication_items i
                            JOIN applications a ON a.id=i.application_id
                            JOIN users u ON u.id=a.student_id
                            JOIN projects p ON p.id=a.project_id
                            WHERE i.publication_id=? ORDER BY i.application_id""",(publication_id,)).fetchall()
        raw=[{"masked_name":self._mask_name(r["student_name"]),
              "masked_student_id":self._mask_student_id(r["student_id"]),
              "college":r["college"],"project_name":r["project_name"],
              "proposed_level":level} for r in rows]
        return [{key:item[key] for key in PUBLIC_ITEM_FIELDS} for item in raw]

    def pending_batches(self, actor):
        """US05: 供学生处挑选可整批发布的「项目 + 批次」，只列还有待公示记录的组合。"""
        self._affairs(self.get_user(actor))
        with self.connection() as con:
            rows=con.execute("""SELECT a.project_id,p.name AS project_name,a.batch,COUNT(*) AS pending_count
                                FROM applications a JOIN projects p ON p.id=a.project_id
                                WHERE a.status='待公示'
                                GROUP BY a.project_id,a.batch ORDER BY p.name,a.batch""").fetchall()
            return [dict(r) for r in rows]

    def publish_batch(self, actor, project_id, batch, start_at, end_at, proposed_level):
        """US05: 只把同一项目批次里全部「待公示」记录整批发布，任何不合条件整批不变。"""
        self._affairs(self.get_user(actor))
        for value in (project_id,batch,start_at,end_at,proposed_level):
            if not isinstance(value,str) or not value.strip():
                raise AppError(400,"INVALID_INPUT","项目、批次、公示时间与拟获等级均为必填字符串")
        project_id,batch,proposed_level=project_id.strip(),batch.strip(),proposed_level.strip()
        if len(proposed_level)>100:
            raise AppError(400,"INVALID_LENGTH","拟获等级名称过长")
        start,end=self._parse_window(start_at),self._parse_window(end_at)
        if start>=end:
            raise AppError(400,"INVALID_WINDOW","公示开始时间必须早于结束时间")
        with self.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            if con.execute("SELECT 1 FROM projects WHERE id=?",(project_id,)).fetchone() is None:
                raise AppError(404,"NOT_FOUND","通知项目不存在")
            if con.execute("SELECT 1 FROM publications WHERE project_id=? AND batch=? AND status IN ('公示中','已确认')",(project_id,batch)).fetchone():
                raise AppError(409,"ALREADY_PUBLISHED","该项目批次已发布公示")
            pending=con.execute("SELECT id FROM applications WHERE project_id=? AND batch=? AND status='待公示' ORDER BY id",(project_id,batch)).fetchall()
            if not pending:
                raise AppError(409,"BATCH_INCOMPLETE","该项目批次没有待公示记录")
            unfinished=con.execute("SELECT COUNT(*) FROM applications WHERE project_id=? AND batch=? AND status IN ('待辅导员审核','待学院复核')",(project_id,batch)).fetchone()[0]
            if unfinished:
                raise AppError(409,"BATCH_INCOMPLETE","批次内仍有未完成的审核，整批不发布")
            pub_id="PUB-"+uuid.uuid4().hex[:16].upper()
            now=self.clock().isoformat()
            con.execute("INSERT INTO publications VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (pub_id,project_id,batch.strip(),proposed_level.strip(),start.isoformat(),end.isoformat(),
                         actor,now,"公示中",0,None,None))
            con.executemany("INSERT INTO publication_items VALUES (?,?)",[(pub_id,r["id"]) for r in pending])
            updated=con.executemany("UPDATE applications SET status='公示中' WHERE id=? AND status='待公示'",
                                    [(r["id"],) for r in pending]).rowcount
            if updated!=len(pending):
                raise AppError(409,"BATCH_INCOMPLETE","批次状态发生变化，整批不发布")
            row=con.execute("SELECT * FROM publications WHERE id=?",(pub_id,)).fetchone()
            result=self._publication_meta(con,row)
            result["items"]=self._publication_items(con,pub_id,row["proposed_level"])
            result["item_count"]=len(pending)
            return result

    def publication_items_for_office(self, actor, publication_id):
        """学生处确认前需要申请编号才能整批提交；身份字段仍只给脱敏值。"""
        self._affairs(self.get_user(actor))
        with self.connection() as con:
            if con.execute("SELECT 1 FROM publications WHERE id=?",(publication_id,)).fetchone() is None:
                raise AppError(404,"NOT_FOUND","公示批次不存在")
            rows=con.execute("""SELECT i.application_id,u.name AS student_name,u.id AS student_id,
                                       u.college,p.name AS project_name,pub.proposed_level
                                FROM publication_items i
                                JOIN publications pub ON pub.id=i.publication_id
                                JOIN applications a ON a.id=i.application_id
                                JOIN users u ON u.id=a.student_id
                                JOIN projects p ON p.id=a.project_id
                                WHERE i.publication_id=? ORDER BY i.application_id""",(publication_id,)).fetchall()
            return [{"application_id":r["application_id"],
                     "masked_name":self._mask_name(r["student_name"]),
                     "masked_student_id":self._mask_student_id(r["student_id"]),
                     "college":r["college"],"project_name":r["project_name"],
                     "proposed_level":r["proposed_level"]} for r in rows]

    def list_publications(self, actor):
        self.get_user(actor)
        with self.connection() as con:
            return [self._publication_meta(con,r) for r in
                    con.execute("SELECT * FROM publications ORDER BY published_at DESC,id")]

    def get_publication(self, actor, publication_id):
        """公开名单：登录可看，但响应只含元数据 + 严格白名单名单项。"""
        self.get_user(actor)
        with self.connection() as con:
            row=con.execute("SELECT * FROM publications WHERE id=?",(publication_id,)).fetchone()
            if row is None:
                raise AppError(404,"NOT_FOUND","公示批次不存在")
            result=self._publication_meta(con,row)
            result["items"]=self._publication_items(con,publication_id,row["proposed_level"])
            result["item_count"]=len(result["items"])
            return result

    def finalize_batch(self, actor, publication_id, decisions, objection_handled):
        """US06: 公示期结束 + 线下异议已处理 + 整批决定齐全，才形成终态。"""
        self._affairs(self.get_user(actor))
        if objection_handled is not True:
            raise AppError(409,"OBJECTION_UNHANDLED","需先确认线下异议已处理")
        if not isinstance(decisions,dict) or not decisions:
            raise AppError(400,"INVALID_INPUT","最终确认必须提供整批决定")
        with self.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            pub=con.execute("SELECT * FROM publications WHERE id=?",(publication_id,)).fetchone()
            if pub is None:
                raise AppError(404,"NOT_FOUND","公示批次不存在")
            if pub["status"]!="公示中":
                raise AppError(409,"ALREADY_FINALIZED","该公示批次已确认，不能重复提交",current_status=pub["status"])
            if self.clock()<self._parse_window(pub["end_at"]):
                raise AppError(409,"PUBLICATION_OPEN","公示期尚未结束，不能形成最终结果")
            items=con.execute("""SELECT a.id,a.status FROM publication_items i
                                 JOIN applications a ON a.id=i.application_id
                                 WHERE i.publication_id=? ORDER BY a.id""",(publication_id,)).fetchall()
            ids={r["id"] for r in items}
            if not ids or set(decisions)!=ids:
                raise AppError(409,"BATCH_INCOMPLETE","最终确认必须覆盖整批记录，禁止部分提交")
            if any(r["status"]!="公示中" for r in items):
                raise AppError(409,"BATCH_INCOMPLETE","批次内存在非公示中记录，整批不确认")
            normalized=[]
            for app_id in sorted(ids):
                entry=decisions[app_id]
                if not isinstance(entry,dict):
                    raise AppError(400,"INVALID_DECISION","每条决定必须是对象")
                decision,reason=entry.get("decision"),entry.get("reason","")
                if decision not in ("approve","reject") or not isinstance(reason,str) or len(reason)>2000:
                    raise AppError(400,"INVALID_DECISION","最终决定或原因格式无效")
                reason=reason.strip()
                if decision=="reject" and not reason:
                    raise AppError(400,"REASON_REQUIRED","未获批必须填写非空原因")
                normalized.append((app_id,decision,reason))
            now=self.clock().isoformat()
            for app_id,decision,reason in normalized:
                con.execute("UPDATE applications SET status=?,rejection_reason=? WHERE id=? AND status='公示中'",
                            ("已获批" if decision=="approve" else "未获批",reason if decision=="reject" else "",app_id))
                con.execute("INSERT INTO results VALUES (?,?,?,?,?,?)",
                            (app_id,publication_id,decision,reason,actor,now))
            con.execute("UPDATE publications SET status='已确认',objection_handled=1,confirmed_by=?,confirmed_at=? WHERE id=? AND status='公示中'",
                        (actor,now,publication_id))
            row=con.execute("SELECT * FROM publications WHERE id=?",(publication_id,)).fetchone()
            result=self._publication_meta(con,row)
            result["items"]=self._publication_items(con,publication_id,row["proposed_level"])
            result["item_count"]=len(normalized)
            return result

    def list_publication_results(self, actor, publication_id):
        self._affairs(self.get_user(actor))
        with self.connection() as con:
            if con.execute("SELECT 1 FROM publications WHERE id=?",(publication_id,)).fetchone() is None:
                raise AppError(404,"NOT_FOUND","公示批次不存在")
            rows=con.execute("""SELECT r.application_id,r.decision,r.reason,r.confirmed_by,r.confirmed_at,a.status
                                FROM results r JOIN applications a ON a.id=r.application_id
                                WHERE r.publication_id=? ORDER BY r.application_id""",(publication_id,)).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def _result_view(row):
        return {"application_id":row["application_id"],"project_name":row["project_name"],
                "batch":row["batch"],"status":row["status"],"submitted_at":row["submitted_at"],
                "final_reason":row["final_reason"] or "","confirmed_at":row["confirmed_at"],
                "publication_id":row["publication_id"],"start_at":row["start_at"],"end_at":row["end_at"]}

    def get_my_results(self, actor):
        self._student(self.get_user(actor))
        with self.connection() as con:
            rows=con.execute("""SELECT a.id AS application_id,p.name AS project_name,a.batch,a.status,a.submitted_at,
                                       COALESCE(r.reason,'') AS final_reason,r.confirmed_at,
                                       pub.id AS publication_id,pub.start_at,pub.end_at
                                FROM applications a JOIN projects p ON p.id=a.project_id
                                LEFT JOIN results r ON r.application_id=a.id
                                LEFT JOIN publications pub ON pub.id=r.publication_id
                                WHERE a.student_id=? ORDER BY a.submitted_at DESC""",(actor,)).fetchall()
            return [self._result_view(r) for r in rows]

    def get_application_result(self, actor, application_id):
        self._student(self.get_user(actor))
        with self.connection() as con:
            row=con.execute("""SELECT a.id AS application_id,p.name AS project_name,a.batch,a.status,a.submitted_at,
                                      COALESCE(r.reason,'') AS final_reason,r.confirmed_at,
                                      pub.id AS publication_id,pub.start_at,pub.end_at
                               FROM applications a JOIN projects p ON p.id=a.project_id
                               LEFT JOIN results r ON r.application_id=a.id
                               LEFT JOIN publications pub ON pub.id=r.publication_id
                               WHERE a.id=? AND a.student_id=?""",(application_id,actor)).fetchone()
            if row is None:
                if con.execute("SELECT 1 FROM applications WHERE id=?",(application_id,)).fetchone():
                    raise AppError(403,"FORBIDDEN","无权查看他人申请的结果")
                raise AppError(404,"NOT_FOUND","申请不存在")
            return self._result_view(row)
