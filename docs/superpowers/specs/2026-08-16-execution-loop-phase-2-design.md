# 第二阶段：任务执行闭环设计

## 1. 目标与范围

本阶段把“计划已生成”推进到“用户可以执行、调整并反馈”。范围严格对应 MVP PRD 的 Phase 2：自定义任务、开始/完成/跳过/超时、重新排程、满意度反馈和内部执行记录。

本阶段继续使用 PostgreSQL、现有 FastAPI 和像素视觉正式前端，不接入实时地图、日历、邮件、PDF、浏览器通知、登录或大模型。已有计划编辑接口继续保留；执行状态与计划版本编辑分开，避免“跳过执行任务”意外创建新的计划版本。

## 2. 用户流程

1. 用户在第五步看到当前计划和每个任务的状态。
2. 到达开始时间后点击“开始任务”，任务从 `pending` 变为 `active`。
3. 完成后点击“完成任务”，任务变为 `completed`，页面显示 1 至 5 分反馈入口。
4. 用户点击“跳过任务”，任务变为 `needs_adjustment`，页面显示“计划需要调整”，提供重新排程和替换入口。
5. 后端发现任务结束时间已过且任务仍为 `pending` 或 `active` 时，分别记录 `missed` 或 `overdue`，并将任务变为 `needs_adjustment`。
6. 用户提交评分和可选原因，反馈写入 PostgreSQL；重复提交同一任务反馈时更新原记录，不产生重复统计。
7. 重新排程只处理未完成任务，保留已完成任务和执行事件。

## 3. 状态机

```text
pending --start--> active --complete--> completed
pending --skip-------------------------> needs_adjustment
pending --deadline---------------------> needs_adjustment
active  --skip--------------------------> needs_adjustment
active  --deadline----------------------> needs_adjustment
```

`completed` 是终态，不能再次开始、跳过或覆盖。所有动作都在数据库事务中执行，并使用 `FOR UPDATE` 锁定目标计划任务，保证重复点击不会产生非法状态跃迁。

## 4. 数据库设计

### 4.1 `plan_items.status`

沿用现有字段，允许值为 `pending`、`active`、`completed`、`skipped`、`needs_adjustment`。执行跳过使用 `needs_adjustment`，而计划编辑页的“移出计划”仍使用已有的 `skipped`，两者语义不混用。

### 4.2 `execution_events`

```sql
CREATE TABLE IF NOT EXISTS execution_events (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL REFERENCES plan_items(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    from_status TEXT NOT NULL,
    to_status TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_execution_events_item_time
    ON execution_events(item_id, occurred_at);
```

### 4.3 `task_feedback`

```sql
CREATE TABLE IF NOT EXISTS task_feedback (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL REFERENCES plan_items(id) ON DELETE CASCADE,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    reasons_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    UNIQUE(plan_id, item_id)
);
```

## 5. 后端接口

### 执行动作

```text
POST /api/v1/plans/{plan_id}/items/{item_id}/execution/start
POST /api/v1/plans/{plan_id}/items/{item_id}/execution/complete
POST /api/v1/plans/{plan_id}/items/{item_id}/execution/skip
POST /api/v1/plans/{plan_id}/items/{item_id}/execution/check-deadline
```

动作接口返回更新后的计划任务、当前状态和最近事件。`complete` 只允许 `active` 任务，`start` 早于开始时间时返回 409，所有非法状态跃迁返回 409。

### 反馈

```text
POST /api/v1/plans/{plan_id}/items/{item_id}/feedback
GET  /api/v1/plans/{plan_id}/feedback
```

请求体：

```json
{
  "rating": 5,
  "reasons": ["符合当前精力"]
}
```

`reasons` 可为空，最多保存三个预定义原因标签，不接收长篇个人信息。

### 自定义任务

扩展现有 `POST /api/v1/plans/{plan_id}/custom-tasks`，增加可选 `reason` 字段。空值合法；任务继续经过时段、冲突和分类校验后生成新计划版本。

## 6. 前端交互

像素计划时间线每个任务卡根据状态显示：

- `pending`：开始任务、跳过任务
- `active`：完成任务、跳过任务
- `completed`：已完成、评分入口
- `needs_adjustment`：计划需要调整、重新排程、替换任务

点击动作后禁用当前按钮并显示处理中状态，成功后只刷新当前计划数据，不重置问卷或 Session。评分采用五个像素按钮，原因标签可选；提交成功后显示“反馈已记录”。

## 7. 错误与幂等

- 目标计划不存在、已被替代或任务不属于该计划：返回 404/409。
- 状态不允许当前动作：返回 409，并返回当前状态。
- 任务已过截止时间：先执行一次幂等的 deadline 检查，再返回 `needs_adjustment`。
- 重复点击同一动作：数据库锁保证只产生一次有效状态变更。
- 重复提交评分：按 `(plan_id, item_id)` 更新原反馈。
- PostgreSQL 不可用：沿用现有 503 错误格式，前端保留“重试”入口。

## 8. 验收标准

1. 任务可从 `pending` 开始并进入 `active`。
2. `active` 任务可完成并进入 `completed`。
3. 跳过、未开始和超时任务显示 `needs_adjustment`。
4. 已完成任务不能被再次修改状态。
5. 任务执行事件和反馈均持久化到 PostgreSQL。
6. 反馈评分限制为 1 至 5，原因标签可不填写。
7. 重新排程保留已完成任务及其事件。
8. 像素前端可以完成开始、完成、跳过、重排和评分主流程。
9. Swagger 展示新增接口，后端和前端回归测试全部通过。
