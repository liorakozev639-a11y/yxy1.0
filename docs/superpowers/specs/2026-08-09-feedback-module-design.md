# Feedback Module Design

## Goal

为已确认计划中的任务提供可追踪的满意度反馈，使用 PostgreSQL 持久化，提供同步 FastAPI 接口和 Swagger 调试入口。

## Scope

- 支持提交单个计划任务的反馈。
- 支持查询单个计划任务的反馈。
- 反馈必须关联 `session_id`、`plan_id`、`item_id`。
- 满意度为 1-5 分。
- 原因标签可选，最多 5 个；文字备注可选，最多 500 字符。
- 反馈只记录体验，不修改计划、任务执行状态或计划版本。
- 本次先作为独立模块运行在 `http://127.0.0.1:8003`，不接入 `main.py`。

## Architecture

`FeedbackService` 负责请求校验、任务归属校验和幂等规则；`PostgreSQLFeedbackRepository` 负责建表、写入和查询；FastAPI 路由只负责解析 HTTP 参数并返回统一 JSON。生产代码不使用内存仓储，测试使用显式的 fake repository 作为测试替身。

## Data Model

表名：`feedback`

| 字段 | 类型 | 规则 |
|---|---|---|
| `id` | `text` | 主键，格式 `feedback_<uuid>` |
| `session_id` | `text` | 必填 |
| `plan_id` | `text` | 必填 |
| `item_id` | `text` | 必填 |
| `rating` | `smallint` | 1-5 |
| `reason_tags` | `jsonb` | 可选数组，最多 5 个 |
| `comment` | `text` | 可选，最多 500 字符 |
| `created_at` | `timestamptz` | 创建时间 |
| `updated_at` | `timestamptz` | 更新时间 |

唯一约束：`(session_id, plan_id, item_id)`。重复提交使用 PostgreSQL `ON CONFLICT DO UPDATE`，返回同一条反馈记录，避免重复数据。

## Request Flow

```text
POST feedback
  -> 校验 rating / reason_tags / comment
  -> 校验 session_id、plan_id、item_id 非空
  -> 写入 feedback 表
  -> 同一任务重复提交时更新原记录
  -> 返回 feedback JSON

GET feedback
  -> 按 session_id + plan_id + item_id 查询
  -> 找到返回记录
  -> 未找到返回 404
```

## API Contract

### Submit

`POST /api/v1/sessions/{session_id}/plans/{plan_id}/items/{item_id}/feedback`

```json
{
  "rating": 5,
  "reason_tags": ["easy_to_start", "matched_energy"],
  "comment": "任务时间合适，完成起来很轻松。"
}
```

### Get

`GET /api/v1/sessions/{session_id}/plans/{plan_id}/items/{item_id}/feedback`

成功返回：`{"data": {...}, "error": null}`；不存在返回 HTTP 404。

## Error Handling

- 非法评分、超过 5 个标签、备注超过 500 字符：HTTP 422。
- 路径标识为空或不符合基本格式：HTTP 400。
- 查询不到反馈：HTTP 404。
- 数据库错误：由调用方记录并返回服务不可用错误，不泄漏 SQL 细节。

## Testing

- 评分边界 1 和 5 可通过，0 和 6 被拒绝。
- 原因标签和备注可以省略。
- 同一任务重复提交只保留一条记录并更新内容。
- 不同任务互不覆盖。
- 查询可返回已提交反馈，查询不存在反馈返回 404。
- `build_web_payload` 风格的纯函数和服务层不依赖外部网络或 MQ。

