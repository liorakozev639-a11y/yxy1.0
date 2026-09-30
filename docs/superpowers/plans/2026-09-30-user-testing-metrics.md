# 用户测试与推荐效果指标实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变现有推荐、排程和执行决策的前提下，为大学生测试用户增加匿名观测、完成后评价、跳过/替换原因和管理员指标看板。

**Architecture:** 在现有 FastAPI + PostgreSQL 中增加独立的测试观测表和服务。前端通过匿名测试编号和白名单事件上报行为，后端异步语义地保存观测数据并提供管理员认证和聚合指标接口；观测失败不得阻断原有业务流程。管理员看板作为独立页面，不进入普通用户主流程。

**Tech Stack:** Python 3.12+、FastAPI、Pydantic、psycopg、PostgreSQL、原生 HTML/CSS/JavaScript、现有 unittest/Node 测试工具。

**Spec:** `docs/superpowers/specs/2026-09-30-user-testing-metrics-design.md`

## Global Constraints

- 不接入 AI 大模型。
- 不修改任务推荐、相似任务排除、排程和执行的核心规则。
- 不修改任务库内容。
- 测试用户只使用匿名编号，不采集姓名、手机号、邮箱等个人信息。
- 第一阶段测试对象为 20 名以上大学生，周期为 1 个月。
- 观测接口失败不能阻断用户查看、开始、完成或跳过任务。
- 管理员看板只允许单一管理员角色访问。
- 数据默认保留 90 天，管理员可以删除观测数据，但不能删除业务所需数据。
- 数据库迁移必须可重复执行，不得覆盖现有业务数据。
- 每个新增接口必须有成功、非法输入、未授权和重复请求测试。

## Review Focus

- 重复事件上报：相同 `idempotency_key` 只能产生一条事件记录；测试归入 Task 2。
- 观测数据库不可用：主流程仍返回原业务结果；测试归入 Task 4。
- 管理员登录失败和过期会话：不能泄露账号信息；测试归入 Task 3。
- 匿名编号和自由文本越界：拒绝控制字符、过长内容和未允许字段；测试归入 Task 2。
- 并发看板查询和筛选：不能混淆日期、批次和匿名用户维度；测试归入 Task 3。

## 文件地图

- `migrations/002_user_testing_metrics.sql`：创建测试用户、事件、测试反馈和管理员会话表。
- `test_observability.py`：测试用户、事件和任务评价的存储服务。
- `admin_metrics_service.py`：管理员认证、权限校验和聚合指标查询。
- `main.py`：注册 Pydantic 请求模型、测试观测接口和管理员指标接口；不改现有业务决策代码。
- `frontend/api.js`：新增测试身份、事件、任务评价和管理员接口调用。
- `frontend/app.js`：在既有流程节点增加匿名身份初始化、事件上报和完成后评价上报。
- `frontend/admin.html`、`frontend/admin.js`、`frontend/admin.css`：开发者看板页面。
- `tests/test_test_observability.py`：存储、校验和幂等行为测试。
- `tests/test_admin_metrics.py`：认证、聚合和筛选测试。
- `tests/test_testing_api.py`：FastAPI 接口和观测失败隔离测试。
- `tests/frontend-testing.test.js`：前端埋点和看板基础交互测试。
- `docs/user-testing-metrics.md`：测试人员使用说明、指标口径和测试记录方法。

### Task 1: 数据库迁移与数据契约

**Files:**
- Create: `migrations/002_user_testing_metrics.sql`
- Test: `tests/test_database_migrations.py`

**Interfaces:**
- Produces tables `test_users`, `test_events`, `task_test_feedback`, `admin_users`, `admin_sessions`.
- `test_events.event_type` 只允许设计文档中的白名单值。
- `task_test_feedback.rating` 为 1 到 5 的整数。
- `test_events.idempotency_key` 具有唯一约束或等价幂等约束。

- [ ] **Step 1: 为新迁移增加失败测试**

  在 `tests/test_database_migrations.py` 增加迁移文件存在、版本顺序、五张核心表、关键索引和约束断言。

- [ ] **Step 2: 运行迁移测试确认失败**

  Run: `python -m unittest tests.test_database_migrations -v`

  Expected: 新表和约束断言失败。

- [ ] **Step 3: 实现 `002_user_testing_metrics.sql`**

  使用现有迁移机制创建五张表和查询索引；所有 `CREATE` 操作可重复执行；不要修改现有业务表结构。

- [ ] **Step 4: 在独立 PostgreSQL 数据库上执行迁移两次**

  Run: `python migrate.py`

  Expected: 两次均成功，第二次不重复插入迁移记录、不报表已存在错误。

- [ ] **Step 5: 运行迁移测试确认通过**

  Run: `python -m unittest tests.test_database_migrations -v`

  Expected: PASS。

- [ ] **Step 6: Commit**

  ```bash
  git add migrations/002_user_testing_metrics.sql tests/test_database_migrations.py
  git commit -m "feat: add user testing metrics schema"
  ```

### Task 2: 匿名测试用户、事件和评价存储

**Files:**
- Create: `test_observability.py`
- Test: `tests/test_test_observability.py`

**Interfaces:**
- `TestObservabilityService.identify(anonymous_id: str, cohort: str) -> dict[str, str]`
- `TestObservabilityService.record_event(*, anonymous_id: str, event_type: str, session_id: str | None, plan_id: str | None, plan_item_id: str | None, reason_code: str | None, metadata: dict[str, Any], idempotency_key: str) -> dict[str, Any]`
- `TestObservabilityService.save_feedback(*, anonymous_id: str, session_id: str, plan_item_id: str, rating: int, comment: str | None) -> dict[str, Any]`
- `TestObservabilityService.delete_anonymous_data(anonymous_id: str) -> int`

- [ ] **Step 1: 写失败测试**

  覆盖匿名编号格式、事件白名单、原因白名单、自由文本长度、评分范围、重复幂等键和重复评价更新。

- [ ] **Step 2: 运行测试确认失败**

  Run: `python -m unittest tests.test_test_observability -v`

  Expected: `TestObservabilityService` 尚未实现或断言失败。

- [ ] **Step 3: 实现存储服务**

  使用现有 `psycopg` 连接和 `dict_row` 访问方式。所有写入字段使用参数化 SQL；事件元数据只保存调用方传入的白名单字段；重复幂等键返回原事件，不新增记录。

- [ ] **Step 4: 验证测试通过**

  Run: `python -m unittest tests.test_test_observability -v`

  Expected: PASS。

- [ ] **Step 5: Commit**

  ```bash
  git add test_observability.py tests/test_test_observability.py
  git commit -m "feat: persist anonymous testing telemetry"
  ```

### Task 3: 管理员认证和指标聚合

**Files:**
- Create: `admin_metrics_service.py`
- Test: `tests/test_admin_metrics.py`

**Interfaces:**
- `AdminMetricsService.login(username: str, password: str) -> dict[str, Any]`
- `AdminMetricsService.logout(token: str) -> None`
- `AdminMetricsService.authenticate(token: str) -> dict[str, Any]`
- `AdminMetricsService.summary(filters: MetricsFilters) -> dict[str, Any]`
- `AdminMetricsService.funnel(filters: MetricsFilters) -> dict[str, Any]`
- `AdminMetricsService.recommendations(filters: MetricsFilters) -> list[dict[str, Any]]`
- `AdminMetricsService.reasons(filters: MetricsFilters) -> list[dict[str, Any]]`
- `AdminMetricsService.errors(filters: MetricsFilters) -> list[dict[str, Any]]`

- [ ] **Step 1: 写失败测试**

  测试正确密码登录、错误密码统一失败、过期令牌拒绝、退出后令牌失效、日期/批次/匿名编号筛选，以及 summary、funnel、recommendations、reasons、errors 的聚合结果。

- [ ] **Step 2: 运行测试确认失败**

  Run: `python -m unittest tests.test_admin_metrics -v`

  Expected: 服务类和指标方法尚未实现。

- [ ] **Step 3: 实现管理员认证**

  使用标准库密码哈希和安全随机令牌；管理员初始账号从环境变量读取，首次启动时写入哈希，不把明文密码写入数据库或日志。认证失败统一返回“登录失败”，并限制连续失败次数。

- [ ] **Step 4: 实现指标查询**

  用单独的 `MetricsFilters` 数据结构统一处理 `from`、`to`、`cohort`、`anonymous_id` 和 `task_category`；聚合查询只读取测试观测表和必要的只读业务字段。

- [ ] **Step 5: 运行测试确认通过**

  Run: `python -m unittest tests.test_admin_metrics -v`

  Expected: PASS。

- [ ] **Step 6: Commit**

  ```bash
  git add admin_metrics_service.py tests/test_admin_metrics.py
  git commit -m "feat: add admin metrics service"
  ```

### Task 4: FastAPI 接口接入并保护主流程

**Files:**
- Modify: `main.py`（新增请求模型、服务依赖和接口，不改现有推荐/排程函数）
- Test: `tests/test_testing_api.py`

**Interfaces:**
- `POST /api/v1/test-users/identify`
- `POST /api/v1/test-events`
- `POST /api/v1/test-feedback`
- `POST /api/v1/admin/login`
- `POST /api/v1/admin/logout`
- `GET /api/v1/admin/me`
- `GET /api/v1/admin/metrics/summary`
- `GET /api/v1/admin/metrics/funnel`
- `GET /api/v1/admin/metrics/recommendations`
- `GET /api/v1/admin/metrics/reasons`
- `GET /api/v1/admin/metrics/errors`

- [ ] **Step 1: 写失败 API 测试**

  使用现有 `create_app` 测试方式，覆盖正常请求、非法评分、非法事件、重复事件、未登录访问管理员接口、已登录访问管理员接口和观测服务异常不阻断主流程。

- [ ] **Step 2: 运行测试确认失败**

  Run: `python -m unittest tests.test_testing_api -v`

  Expected: 新路由不存在或返回非预期状态码。

- [ ] **Step 3: 注册服务和请求模型**

  在 `create_app` 中注入 `TestObservabilityService` 和 `AdminMetricsService`；保持未配置数据库时现有 mock/unconfigured 行为不变。

- [ ] **Step 4: 实现观测接口**

  对请求体进行 Pydantic 校验；观测写入异常捕获为非阻断错误，主业务响应仍保持原有格式和状态码。

- [ ] **Step 5: 实现管理员保护**

  管理员接口统一调用 `AdminMetricsService.authenticate`；未认证返回 401，登录失败不暴露账号信息。

- [ ] **Step 6: 运行 API 测试和原有后端测试**

  Run: `python -m unittest tests.test_testing_api -v`

  Run: `python -m unittest discover -s tests -p "test_*.py"`

  Expected: 新测试和原有测试全部 PASS。

- [ ] **Step 7: Commit**

  ```bash
  git add main.py tests/test_testing_api.py
  git commit -m "feat: expose testing telemetry and admin metrics api"
  ```

### Task 5: 前端匿名埋点、完成后反馈和管理员看板

**Files:**
- Modify: `frontend/api.js`
- Modify: `frontend/app.js`
- Create: `frontend/admin.html`
- Create: `frontend/admin.js`
- Create: `frontend/admin.css`
- Test: `tests/frontend-testing.test.js`

**Interfaces:**
- `api.identifyTestUser(anonymousId, cohort)`
- `api.recordTestEvent(event)`
- `api.saveTestFeedback(feedback)`
- `api.adminLogin(username, password)`
- `api.adminMetrics(path, filters)`

- [ ] **Step 1: 写失败前端测试**

  验证首次加载生成并复用 `mvp_test_anonymous_id`，主流程关键节点调用事件接口，任务完成后提交评价，跳过/替换时提交原因；验证管理员页面可登录并请求 summary、funnel、recommendations、reasons、errors。

- [ ] **Step 2: 运行前端测试确认失败**

  Run: `node --test tests/frontend-testing.test.js`

  Expected: 新 API 方法、事件钩子或管理员页面尚未存在。

- [ ] **Step 3: 实现 `frontend/api.js` 调用封装**

  复用现有请求封装和错误处理；事件接口失败只记录前端调试信息，不弹出阻断主流程的错误。

- [ ] **Step 4: 在 `frontend/app.js` 接入事件**

  只在已有会话、问卷、推荐、开始、完成、跳过、替换和反馈动作成功后上报对应事件。匿名编号保存在 `localStorage`，不放入页面可见内容。

- [ ] **Step 5: 创建管理员看板页面**

  实现管理员登录、日期/批次/匿名编号筛选、总体指标、流程漏斗、推荐效果、跳过/替换原因和错误列表；不复用普通用户页面状态，不展示个人身份信息。

- [ ] **Step 6: 运行前端测试确认通过**

  Run: `node --test tests/frontend-testing.test.js`

  Run: `node --test tests/frontend-flow.test.js tests/frontend-execution.test.js tests/frontend-api.test.js`

  Expected: 新测试和原有前端测试全部 PASS。

- [ ] **Step 7: Commit**

  ```bash
  git add frontend/api.js frontend/app.js frontend/admin.html frontend/admin.js frontend/admin.css tests/frontend-testing.test.js
  git commit -m "feat: add testing telemetry and admin dashboard"
  ```

### Task 6: 完整验证、测试说明和交付审查

**Files:**
- Create: `docs/user-testing-metrics.md`
- Modify: `README.md`
- Test: `tests/test_testing_api.py`, `tests/frontend-testing.test.js`

- [ ] **Step 1: 补充测试人员使用文档**

  写明如何生成匿名编号、如何邀请大学生测试、如何执行完整主流程、如何查看管理员看板、每个指标的计算口径以及如何记录 1 个月测试结论。

- [ ] **Step 2: 更新 README 启动说明**

  只增加管理员环境变量、看板地址、测试命令和安全提醒，不修改原有业务启动方式。

- [ ] **Step 3: 运行 Python 全量测试**

  Run: `python -m unittest discover -s tests -p "test_*.py"`

  Expected: 全部 PASS。

- [ ] **Step 4: 运行 Node 全量测试**

  Run: `node --test tests/*.test.js`

  Expected: 全部 PASS。

- [ ] **Step 5: 运行真实测试数据库迁移和 API 冒烟**

  Run: `python migrate.py`

  Run: `python -m unittest tests.test_testing_api tests.test_database_migrations -v`

  Expected: 迁移成功，主流程和观测接口均可用。

- [ ] **Step 6: 做代码审查**

  检查观测失败是否会阻断主流程、管理员路由是否全部认证、是否有明文密码、是否把个人信息写入事件、是否修改了推荐和排程决策逻辑。

- [ ] **Step 7: Commit**

  ```bash
  git add README.md docs/user-testing-metrics.md
  git commit -m "docs: document user testing and metrics workflow"
  ```

- [ ] **Step 8: 最终验证和交付**

  Run: `git diff --check`

  Run: `git status --short`

  Expected: 无空白错误；只保留明确属于用户的未提交文件；记录测试命令和结果后，再决定是否推送远程仓库和部署。
