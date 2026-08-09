# MVP 新增内容运行与调试指南设计

## 目标

为初学者生成一份中文 Markdown 教学文档，解释本次新增的 `mvp_orchestrator.py`、`docs/api.md` 和 `tests/live_core_flow.ps1` 的底层运行逻辑，并指导用户在本地 PostgreSQL、FastAPI、前端和 PyCharm 环境中运行及调试完整核心链路。

## 输出文件

`docs/MVP新增内容运行与调试指南.md`

## 读者

正在学习 Python、FastAPI、PostgreSQL 和断点调试的大学生。文档不假设读者熟悉依赖注入、Repository、编排器、OpenAPI 或 HTTP 调试。

## 文档结构

1. 新增内容总览：三个文件分别解决什么问题。
2. 核心工作流：从前端请求到 PostgreSQL 网页计划的调用顺序。
3. `mvp_orchestrator.py`：输入、依赖、画像计算、任务推荐、排程、持久化、网页交付和查询恢复。
4. PostgreSQL：`profiles`、`plans`、`plan_items`、`delivery_jobs` 的字段用途和关联关系。
5. `docs/api.md`：静态接口文档、FastAPI 路由、OpenAPI 和 Swagger 的关系。
6. `tests/live_core_flow.ps1`：脚本每一步请求、输入和预期响应。
7. 本地运行：PostgreSQL、环境变量、后端、前端和访问 URL。
8. PyCharm 调试：运行配置、断点顺序、Variables 观察项和单步按键。
9. 分层调试路线：HTTP 路由、编排层、业务模块、Repository、PostgreSQL。
10. 常见错误：数据库连接、问卷状态、分类映射、约束覆盖、时间窗口和端口占用。
11. 验收清单：如何判断整条链路运行成功。

## 讲解方式

- 每个概念先用通俗语言解释，再给出本项目中的真实代码位置和数据示例。
- 断点使用当前文件中的函数名定位，不依赖容易变化的固定行号。
- 命令使用 Windows PowerShell，并区分“PowerShell 终端”和“PyCharm Python Console”。
- 数据库密码只用 `<password>` 占位，不写入文档。
- 说明当前核心流程覆盖 Session、Questionnaire、Profile、Task、Recommendation、Scheduling 和 Web Delivery；Execution 与 Feedback 尚未接入主流程。

## 验收标准

- 文档能够让用户从零启动 PostgreSQL、后端和前端。
- 文档能够让用户通过 Swagger 和脚本分别完成一次计划生成。
- 文档明确三个新增文件的输入、输出、依赖和数据流。
- 文档给出可操作的断点顺序和每个断点应观察的变量。
- 文档包含成功响应特征和常见错误排查路径。
- 文档不包含真实密码、Token 或个人数据。

