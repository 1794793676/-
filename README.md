# 奖助学金管理系统（高校学工平台）

《软件项目管理》实验一「敏捷需求分析与用户故事编写」的落地实现。核心 Feature 为**奖助学金管理**，完整实现文档中的 8 条用户故事（US01–US08），前后端分离，可在本机直接运行。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Spring Boot 3.3 + Maven + Spring Data JPA |
| 数据库 | H2 内嵌文件数据库（无需安装 MySQL，项目启动自动建表并写入演示数据） |
| 前端 | HTML + CSS + 原生 JavaScript + Vue 3（本地文件，无需 npm） |
| 通信 | REST + JSON，前端 `fetch`，登录后通过 `X-Session-Token` 请求头认证 |

## 目录结构

```
scholarship-system/
├─ backend/                  # Spring Boot 后端
│  ├─ pom.xml
│  └─ src/main/java/com/demo/scholarship/
│     ├─ domain/             # User / Notice / Application 实体
│     ├─ repo/               # JPA 仓储
│     ├─ service/            # 业务规则（申请、审核、公示、统计、脱敏）
│     ├─ web/                # REST 控制器
│     ├─ seed/DataSeeder.java# 演示数据初始化
│     └─ config/WebConfig.java
├─ frontend/                 # 前端（静态文件）
│  ├─ index.html
│  ├─ css/style.css
│  └─ js/app.js, js/vue.global.prod.js
└─ README.md
```

## 环境要求

- JDK 17 及以上
- Maven 3.8+（也可使用项目自带的 `mvnw` / `mvnw.cmd`，首次运行会自动下载 Maven）
- 任意静态文件服务器：Python 3（`python -m http.server`）或 VS Code 的 Live Server 插件
- **不需要安装数据库**，首次启动自动创建 `backend/data/demo.mv.db`

## 启动方式

### 1. 启动后端

Windows（cmd / PowerShell）与 macOS / Linux：

```bash
cd backend
mvn clean package -DskipTests
java -jar target/scholarship-system-1.0.0.jar
```

后端地址：`http://localhost:8080`。

> 也可以使用 `mvn spring-boot:run`。如果项目所在路径包含中文，部分 Windows 环境下 `spring-boot:run` 会因编码问题报 `ClassNotFoundException`，此时请使用上面的 `java -jar` 方式启动。

### 2. 启动前端

```bash
cd frontend
python -m http.server 5500
```

浏览器打开 `http://localhost:5500`。也可以用 VS Code 的 Live Server 打开 `frontend/index.html`（端口 5500 或其他均可，后端已允许跨域）。

> 不建议直接双击 `index.html`（`file://` 协议下浏览器对跨域请求限制较多），请使用静态服务器。

## 演示账号

密码统一为 `123456`，登录页也可点击账号直接登录。

| 账号 | 姓名 | 角色 | 说明 |
|---|---|---|---|
| `zhang3` | 张三 | 学生 | 计算机学院，辅导员王老师 |
| `wangxm` | 王小明 | 学生 | 计算机学院，辅导员王老师 |
| `lisi` | 李四 | 学生 | 软件学院，辅导员刘老师 |
| `wangls` | 王老师 | 辅导员 | 管理计算机学院学生 |
| `liuls` | 刘老师 | 辅导员 | 管理软件学院学生 |
| `jsxy` | 计算机学院审核员 | 学院审核员 | 只能复核计算机学院申请 |
| `rjxy` | 软件学院审核员 | 学院审核员 | 只能复核软件学院申请 |
| `xsc` | 学生处张老师 | 学生处 | 发布公示、确认结果、统计分析 |

演示数据包含 3 条通知：国家励志奖学金（申请中）、校级奖学金（已结束）、国家奖学金（未发布，学生端不可见）。

## 3 分钟演示流程

1. **学生查看通知并申请（US01、US02）**：用 `zhang3` 登录 → 点击「国家励志奖学金」→ 填写申请理由并勾选全部材料 → 提交，得到申请编号。再次提交会返回同一申请编号（申请唯一）。
2. **辅导员审核（US03）**：退出，用 `wangls` 登录 → 点击张三的申请 → 填写意见并「审核通过」。也可尝试「驳回」（必须填理由）或「退补」（US07，需填写补正意见和未来截止时间）。
3. **学院复核（US04）**：用 `jsxy` 登录 → 复核通过，状态变为「待公示」。用 `rjxy` 登录则看不到该申请（学院隔离）。
4. **学生处公示（US05）**：用 `xsc` 登录 → 「公示管理」→ 选择批次，默认勾选全部「待公示」记录 → 将公示结束时间设为当前时间之后若干秒/分钟 → 发布公示。随后用学生账号进入「公示名单」，可见脱敏姓名（如 `张*`）和学号后四位，公示期间显示「拟入选」。
5. **确认最终结果（US06）**：公示结束时间到达后，回到学生处「公示结果确认」→ 勾选「线下异议处理已完成」→ 为每位学生选择「已获批/未获批」（未获批必须填原因）→ 确认。学生端「我的申请」即可看到最终结果。
6. **补正重提（US07，V2）**：辅导员对「待辅导员审核」的申请发起退补 → 学生端「我的申请」显示补正意见与截止时间 → 学生在截止前重新提交，申请编号不变；逾期重提会被拒绝并标记补正逾期。
7. **统计分析（US08，V3）**：「统计分析」→ 选择批次（可按学院筛选）→ 查看按项目/学院分组的申请总数、各状态数量、最终获批人数。多次重提仍按一条申请统计。

### 重置演示数据

停止后端，删除 `backend/data` 目录，重新启动后端即可恢复初始演示数据。

## 8 条用户故事与实现位置

| 编号 | 功能 | 主要页面 | 主要接口 |
|---|---|---|---|
| US01 | 查看通知 | 学生端 · 通知公告 | `GET /api/notices`、`GET /api/notices/{id}` |
| US02 | 提交申请 | 学生端 · 通知详情内申请表单 | `POST /api/applications` |
| US03 | 辅导员审核 | 辅导员端 | `POST /api/applications/{id}/counselor-review` |
| US04 | 学院复核 | 学院审核员端 | `POST /api/applications/{id}/college-review` |
| US05 | 学生处公示 | 学生处 · 公示管理；学生 · 公示名单 | `POST /api/publicity/publish`、`GET /api/publicity/{noticeId}` |
| US06 | 查看结果 | 学生 · 我的申请；学生处 · 结果确认 | `GET /api/applications/mine`、`POST /api/publicity/{noticeId}/confirm` |
| US07 | 补正重提（V2） | 辅导员端退补；学生端重提 | `POST /api/applications/{id}/correction`、`POST /api/applications/{id}/resubmit` |
| US08 | 统计分析（V3） | 学生处 · 统计分析 | `GET /api/stats` |

## 已实现的关键业务规则

- 同一学生 + 同一项目批次只允许一条申请，重复提交返回原申请编号
- 申请必须处于开放时间内，且申请理由、必需材料齐全
- 辅导员只能审核自己负责的学生；学院审核员只能复核本学院；学生不能查看他人申请
- 驳回必须填写理由；已审核的申请不能重复审核
- 公示必须整批校验：选中记录中存在非「待公示」状态时整批阻止
- 公示名单脱敏：姓名保留首尾（`张三 → 张*`、`王小明 → 王*明`），学号仅保留后 4 位
- 公示结束且线下异议处理完成后，学生处才能逐条确认全部公示记录，未获批必须填写原因，不允许遗漏
- 补正必须有意见和未来截止时间；截止前重提保留原编号和上次材料快照；逾期标记终止
- 统计口径：各状态数量之和等于申请总数，最终获批只统计「已获批」

## 说明

本项目为课程教学演示，刻意保持简单：密码明文存储、无 JWT、无真实文件上传、无通知发布管理。请勿直接用于生产环境。
