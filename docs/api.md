# MVP Core API

服务地址：`http://127.0.0.1:8000`

Swagger：`http://127.0.0.1:8000/docs`

统一返回结构：

```json
{
  "data": {},
  "error": null
}
```

## Session

### 创建会话

`POST /api/v1/sessions`

返回 `session_id`、`stage`、`version` 和 `expires_at`。

### 恢复会话

`GET /api/v1/sessions/{session_id}`

### 保存偏好

`PUT /api/v1/sessions/{session_id}/preferences`

```json
{
  "categories": ["活力充电", "松弛疗愈"],
  "duration": "half",
  "budget": "medium",
  "outing": "home",
  "company": "solo",
  "city_or_campus": "测试校园",
  "rest_only": false
}
```

## Questionnaire

- `POST /api/v1/sessions/{session_id}/questionnaire/start`
- `PATCH /api/v1/sessions/{session_id}/questionnaire/answers/{question_id}`
- `POST /api/v1/sessions/{session_id}/questionnaire/skip/{question_id}`
- `GET /api/v1/sessions/{session_id}/questionnaire/progress`
- `POST /api/v1/sessions/{session_id}/questionnaire/submit`

开始问卷：`{"mode": "quick"}`。答案：`{"value": 4}`。

量表固定为：`1 完全不同意`、`2 不太同意`、`3 比较同意`、`4 非常同意`。

## Plan Generation

### 生成计划

`POST /api/v1/sessions/{session_id}/plan/generate`

```json
{
  "free_start": "2026-08-09T10:00:00+08:00",
  "free_end": "2026-08-09T14:00:00+08:00",
  "density": "balanced"
}
```

`density` 可选 `light`、`balanced`、`full`。后端依次执行画像计算、任务筛选、分类覆盖推荐、时间排程、计划保存和网页交付 JSON 生成。

### 查询计划

`GET /api/v1/sessions/{session_id}/plan`

返回 `plan_id`、版本、时间范围、任务数组和未安排任务 ID。

## Execution Loop

计划生成并确认后，前端按任务状态调用执行接口。执行接口不需要登录令牌；服务端通过 `plan_id`、任务归属和会话有效期校验请求。

请求体统一为可选的服务器时间覆盖字段。正常使用可传空对象 `{}`，调试或自动化验收时可传 ISO 8601 时间：

```json
{"now": "2026-08-09T10:05:00+08:00"}
```

### 开始任务

`POST /api/v1/plans/{plan_id}/items/{item_id}/execution/start`

`pending` 任务在开始时间到达后变为 `active`，并记录 `started` 事件。

### 完成任务

`POST /api/v1/plans/{plan_id}/items/{item_id}/execution/complete`

`active` 任务变为 `completed`，并记录 `completed` 事件。

### 跳过任务

`POST /api/v1/plans/{plan_id}/items/{item_id}/execution/skip`

将可执行任务变为 `needs_adjustment`，并记录 `skipped` 事件。它和计划编辑接口中的 `.../skip` 不同：前者表示执行阶段主动跳过，后者表示修改计划版本。

### 检查任务截止时间

`POST /api/v1/plans/{plan_id}/items/{item_id}/execution/check-deadline`

当任务超过 `end_at` 仍未完成时，`pending` 任务记录 `missed`，`active` 任务记录 `overdue`，两者都会变为 `needs_adjustment`。重复检查不会重复产生事件。

### 查询执行事件

`GET /api/v1/plans/{plan_id}/execution/events?item_id={item_id}`

`item_id` 可选；不传时返回整个计划的执行事件。

## Feedback

只有状态为 `completed` 的任务可以提交反馈。同一计划中的同一任务重复提交会更新原记录。

### 保存任务反馈

`POST /api/v1/plans/{plan_id}/items/{item_id}/feedback`

```json
{
  "rating": 5,
  "reasons": ["容易开始", "符合当前状态"]
}
```

`rating` 为 1 到 5 的整数，`reasons` 可为空，最多 3 项。

### 查询计划反馈

`GET /api/v1/plans/{plan_id}/feedback`

返回当前计划下已经提交的任务反馈列表。

### 典型执行顺序

```text
生成计划 → 确认计划 → 开始任务 → 完成任务 → 提交反馈
                         ↘ 超时检查 → needs_adjustment → 重新排程
```

## 错误

- `404`：会话或计划不存在。
- `409`：问卷未提交、分类无法覆盖或业务状态冲突。
- `410`：会话已过期。
- `422`：请求字段校验失败。
- `503`：PostgreSQL 暂不可用。
