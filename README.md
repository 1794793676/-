# 高校学工平台

软件项目管理实验三的团队协作仓库。当前后端已整体切换为 Spring Boot 工程（`backend/`），原实验二的 Python 标准库增量已移除，如需查阅可从 Git 历史取回。

## 目录

- `backend/`：Spring Boot 后端工程（Java 17 + Maven + Spring Data JPA + H2）。
- `docs/`：需求、设计、站会、配置管理与发布文档。
- `src/`：后续新模块预留目录。
- `test/`：后续新测试预留目录。

## 后端运行

```bash
cd backend
./mvnw spring-boot:run        # Windows: mvnw.cmd spring-boot:run
```

- 默认端口 `8080`；H2 文件库落在 `backend/data/demo.mv.db`，首次启动自动建表并写入演示数据。
- 演示账号密码统一 `123456`：学生 `zhang3` / `wangxm` / `lisi`，辅导员 `wangls` / `liuls`，学院审核员 `jsxy` / `rjxy`，学生处 `xsc`。
- 接口鉴权通过请求头 `X-User-Id` 传递登录返回的用户主键。

## 协作约定

`main` 保持可发布状态。功能开发使用 `feature/*`，缺陷修复使用 `bugfix/*`，紧急修复使用 `hotfix/*`。从最新的 `main` 创建分支，按 Conventional Commits 提交，推送后创建 Pull Request；至少一位其他成员完成 Code Review，验证通过后再合并。

提交示例：`feat: 实现用户登录`、`fix: 修复登录错误`、`docs: 更新站会记录`、`chore: 初始化项目骨架与目录结构`。

配置项变更先记录申请与影响评估，经 PO 审批后在分支实施，并通过评审和测试后合入 `main`。达到可发布状态时再创建语义化版本标签与 Release Notes。

## 不入库的内容

`backend/target/`（构建产物）与 `backend/data/`（H2 数据库文件）已在 `.gitignore` 中排除，请勿提交。`docs/` 下标注为 Python 实现的接口说明与讲解报告对应的是已移除的旧后端，仅供历史查阅。

## 当前状态

Spring Boot 后端已入库，覆盖通知、申请与补正、辅导员审核、学院复核、整批公示、最终结果确认与统计。尚未建立发布标签，也尚未补齐与新后端配套的自动化测试。
