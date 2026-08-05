# Session 与 Questionnaire 前后端联调设计

## 1. 目标

基于现有 `session_module.py`、`questionnaire_module.py` 和 `frontend` 静态原型，交付一个可以本地完整跑通的测试版本。

本轮链路为：

```text
创建会话
-> 保存活动方向和前置条件
-> 选择快速版或深度版问卷
-> 保存、修改或跳过答案
-> 查看并恢复问卷进度
-> 提交问卷
-> 显示联调结果摘要
```

本轮不接入 Profile、Task Repository、Recommendation、任务候选和计划排程。

## 2. 已验证现状

- Session Module 可以独立完成创建、恢复、偏好保存和会话清理。
- Questionnaire Module 可以独立完成快速版 5 题、深度版 30 题、答题、跳过、进度和提交。
- 两个模块当前使用不同的内存会话仓库，同一个 `session_id` 无法直接贯通。
- 当前前端只使用 JavaScript 内存状态，没有调用后端接口。
- 当前后端没有允许 `5173` 前端访问的 CORS 配置。
- `task_repository.py` 存在既有缩进错误，但不在本轮范围内，也不应被本轮修改。

## 3. 架构选择

采用统一单服务方案。

新增 `main.py` 作为唯一启动入口，统一监听：

```text
http://127.0.0.1:8000
```

文件职责：

- `main.py`：创建 FastAPI 应用、配置 CORS、组合 Session 与 Questionnaire 路由。
- `session_module.py`：会话模型、PostgreSQL 会话仓库和会话业务逻辑。
- `questionnaire_module.py`：题库、问卷模型、PostgreSQL 问卷仓库和问卷业务逻辑。
- `frontend/api.js`：封装统一 API 地址、请求、错误解析和 `session_id` 管理。
- `frontend/app.js`：页面状态、交互流程和后端数据渲染。
- `frontend/logic.js`：保留与展示有关的纯函数；不再生成本地模拟问卷。

原有独立应用入口可以保留用于模块调试，但正式联调只启动 `main.py`。

## 4. 身份识别规则

本地测试版不使用 Token，也不发送 `Authorization` 请求头。

会话只通过不可预测的 `session_id` 识别。前端使用以下键保存它：

```text
free_time_agent_session_id
```

保存位置为 `localStorage`，使刷新或重新打开页面后可以恢复测试进度。

该方案仅用于本地测试。正式上线账号体系后，应改为受保护的用户身份或安全会话机制。

## 5. PostgreSQL 数据模型

数据库连接通过环境变量配置：

```text
SESSION_DATABASE_URL=postgresql://<user>:<password>@127.0.0.1:5433/free_time_agent
```

代码和示例文件中不写入真实数据库密码。

### 5.1 sessions

- `id`：会话 ID，主键。
- `stage`：当前流程阶段。
- `preferences`：JSONB，保存分类、预算、时间、地点、出行和同行偏好。
- `profile`：JSONB，保留后续模块扩展字段，本轮为空。
- `plan`：JSONB，保留后续模块扩展字段，本轮为空。
- `created_at`、`updated_at`：时间戳。
- `expires_at`：会话过期时间。
- `version`：更新版本号。

测试版不需要 `token_hash`。

如果本地数据库已有旧版 `sessions.token_hash` 字段，初始化逻辑只负责解除其非空约束并停止读写该字段，不删除其他历史列或数据。

### 5.2 questionnaires

- `session_id`：主键，同时关联会话。
- `mode`：`quick` 或 `deep`。
- `question_ids`：JSONB，保存本次抽取题目的固定顺序。
- `submitted`：是否已经提交。
- `created_at`、`updated_at`、`submitted_at`：时间戳。

一个会话只保留一份当前问卷。问卷开始后再次调用 start，应恢复原问卷，不重新抽题。

### 5.3 questionnaire_answers

- `session_id`、`question_id`：联合主键。
- `value`：1 到 4；跳过时可以为空。
- `skipped`：是否跳过。
- `answered_at`：最后更新时间。

相同题目再次保存时执行更新，不新增重复答案。

## 6. HTTP 接口

所有接口统一返回：

```json
{
  "data": {},
  "error": null
}
```

失败时 `data` 为 `null`，`error` 包含错误代码和中文信息。

### 6.1 Session

```text
POST   /api/v1/sessions
GET    /api/v1/sessions/{session_id}
PUT    /api/v1/sessions/{session_id}/preferences
DELETE /api/v1/sessions/{session_id}/data
```

创建会话只返回 `session_id`、阶段和过期时间，不返回 Token。

### 6.2 Questionnaire

```text
POST  /api/v1/sessions/{session_id}/questionnaire/start
PATCH /api/v1/sessions/{session_id}/questionnaire/answers/{question_id}
POST  /api/v1/sessions/{session_id}/questionnaire/skip/{question_id}
GET   /api/v1/sessions/{session_id}/questionnaire/progress
POST  /api/v1/sessions/{session_id}/questionnaire/submit
```

`start` 接受：

```json
{
  "mode": "quick"
}
```

快速版返回 5 题，深度版返回 30 题。题目从 Python 静态题库选择，本轮不增加题库表。

## 7. 前端工作流

### 7.1 初始化

1. 从 `localStorage` 读取 `session_id`。
2. 如果存在，调用会话恢复接口。
3. 如果会话不存在或过期，删除旧值并创建新会话。
4. 如果问卷已经开始，获取进度并恢复到未完成题目。
5. 如果问卷已经提交，直接进入结果摘要页。

### 7.2 偏好与问卷

1. 用户选择活动方向并调整优先级。
2. 用户填写时间、预算、出行、地点和同行偏好。
3. 前端保存 preferences。
4. 用户选择快速版 5 题或深度版 30 题。
5. 前端调用 start，并以后端返回题目为唯一数据源。
6. 每次回答后立即保存，成功后进入下一题。
7. 跳过题目时调用 skip。
8. 问卷完成后调用 submit。

### 7.3 结果页

结果页显示：

- 问卷模式。
- 总题数。
- 已答数量。
- 跳过数量。
- 提交状态。
- `session_id`，便于本地调试。

本轮不进入候选任务和计划页面。

## 8. 错误处理

- 请求进行中禁用重复操作。
- 网络错误保留当前页面和本地选择，并提供重试按钮。
- 会话不存在或过期时清理本地 `session_id`，创建新会话。
- 问卷已经开始时返回并恢复原问卷。
- 问卷提交后，答题和跳过接口返回冲突错误。
- 不属于当前问卷的 `question_id` 返回 400。
- PostgreSQL 不可用时返回 503 或统一的数据库错误，不暴露连接密码。
- 前端集中解析 `{data, error}` 并通过现有 toast 组件显示中文提示。

## 9. CORS

统一应用仅允许以下前端来源：

```text
http://127.0.0.1:5173
http://localhost:5173
```

允许本轮接口使用的 `GET`、`POST`、`PUT`、`PATCH`、`DELETE` 和 `OPTIONS` 方法。

## 10. 测试策略

### 10.1 后端自动化测试

- 创建、恢复和清理会话。
- 保存并重新读取 preferences。
- 快速版返回 5 题。
- 深度版返回 30 题。
- 新增、修改和跳过答案。
- 进度统计准确。
- 问卷提交后禁止修改。
- 不存在的会话和题目返回预期错误。
- CORS 预检成功。
- 服务重启后仍能从 PostgreSQL 恢复会话和问卷。

### 10.2 前后端联调验收

```text
启动 PostgreSQL
-> 启动 python main.py
-> 启动 frontend 静态服务
-> 打开 http://127.0.0.1:5173/
-> 保存分类和前置条件
-> 选择 5 题或 30 题
-> 作答一部分后刷新页面
-> 自动恢复进度
-> 完成并提交问卷
-> 显示联调结果摘要
```

## 11. 交付物

- 统一后端入口 `main.py`。
- PostgreSQL 会话和问卷仓库实现。
- 接入真实接口的 `frontend/api.js` 与更新后的前端页面。
- `.env.example`，只包含占位连接信息。
- 自动化接口测试。
- 中文启动、PyCharm 调试和验收说明。

## 12. 非目标

- 不接入 Profile Module。
- 不修复或改造 Task Repository。
- 不接入 Recommendation Module。
- 不实现候选任务、计划生成、PDF 或邮件发送。
- 不实现账号、Token、OAuth 或其他正式身份验证。
- 不修改现有前端视觉主题，除非联调状态需要增加必要控件。
