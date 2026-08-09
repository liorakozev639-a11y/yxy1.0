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

## 错误

- `404`：会话或计划不存在。
- `409`：问卷未提交、分类无法覆盖或业务状态冲突。
- `410`：会话已过期。
- `422`：请求字段校验失败。
- `503`：PostgreSQL 暂不可用。

