# 网页提醒与计划复盘设计

**日期：** 2026-08-25  
**状态：** 待用户评审  
**范围：** 负向反馈与替换原因可见化、网页内执行提醒、自动未完成、计划结束统一复盘、完成感受记录

## 1. 目标与边界

本次迭代让已生成的计划可以被执行、被提醒，并在结束后形成一份易读的复盘：

1. 计划页在网页打开期间提示“可开始”“即将结束”和“已超时未处理”的任务。
2. 到任务结束时间仍处于 `pending` 或 `active` 的任务，后端统一标记为 `needs_adjustment`，复盘中展示为“未完成”。
3. 当整份计划到达 `free_end` 后，用户可查看统一复盘：完成、跳过、未完成、可选完成感受和下一次建议。
4. 对已完成任务，用户可选填三档感受：`satisfied`、`neutral`、`dissatisfied`。
5. 计划页明确展示已生效的“不再推荐”偏好；任务替换后明确解释替换原因。
6. 不增加浏览器通知、邮件、账号、后台定时器、MQ 或跨会话数据。

## 2. 设计原则

- **状态唯一来源：** `plan_items.status` 和 `execution_events` 仍是执行状态唯一来源；复盘只读取和聚合，不复制状态。
- **网页主动检查：** 浏览器每 30 秒调用批量检查接口；后端根据传入的服务器当前时间更新过期任务，页面刷新后也可恢复正确状态。
- **低填写成本：** 完成感受不是必填；复盘在计划结束后统一出现，执行中不弹出打断流程的表单。
- **与负向偏好分离：** 复盘中的“不满意”默认只记录体验，不等同于 1–2 分负反馈；只有既有的 1–2 分评分和跳过继续触发任务组排除。

## 3. 数据模型

### 3.1 已有数据复用

```text
plans.free_start / free_end
plan_items.status / start_at / end_at
execution_events.event_type / occurred_at
task_feedback.rating / reasons_json
```

### 3.2 新表：完成感受

```sql
CREATE TABLE task_completion_reflections (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL REFERENCES plan_items(id) ON DELETE CASCADE,
    sentiment TEXT NOT NULL CHECK (sentiment IN ('satisfied', 'neutral', 'dissatisfied')),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    UNIQUE (plan_id, item_id)
);
```

仅允许 `completed` 任务写入。重复提交更新当前任务的感受，便于用户修正选择。

## 4. 后端模块与接口

新增 `review_service.py`，负责初始化感受表、批量检查计划状态、保存感受和生成复盘。它依赖 `SessionService` 与 PostgreSQL，不直接修改推荐偏好。

| 方法 | 作用 |
| --- | --- |
| `refresh_plan(session_id, plan_id, now)` | 逐项调用既有截止检查规则，返回更新后的计划状态和提醒摘要 |
| `save_reflection(session_id, plan_id, item_id, sentiment)` | 保存已完成任务的三档感受 |
| `get_review(session_id, plan_id, now)` | 先刷新过期任务，再汇总计划复盘 |

新增 API：

```text
POST /api/v1/plans/{plan_id}/execution/refresh
POST /api/v1/plans/{plan_id}/items/{item_id}/reflection
GET  /api/v1/plans/{plan_id}/review
```

`GET /review` 响应：

```json
{
  "plan_id": "plan_xxx",
  "status": "in_progress | finished",
  "ends_at": "2026-08-25T18:00:00+08:00",
  "summary": {
    "total_tasks": 4,
    "completed_count": 2,
    "skipped_count": 1,
    "unfinished_count": 1,
    "satisfied_count": 1,
    "neutral_count": 1,
    "dissatisfied_count": 0
  },
  "items": [
    {"item_id": "item_xxx", "title": "居家拉伸", "outcome": "completed", "sentiment": "satisfied"}
  ],
  "suggestions": ["下次可以继续保留已完成的轻量任务。"]
}
```

`unfinished_count` 包含 `needs_adjustment`、`pending` 和 `active`。计划是否结束由 `now >= plans.free_end` 判断。

## 5. 网页流程

1. 用户进入已生成计划页，前端加载计划并调用一次 `refresh`。
2. 页面存活时每 30 秒继续调用 `refresh`；离开结果页时清理定时器。
3. 结果页顶部显示网页内提醒条：
   - 到开始时间：`现在可以开始：任务名`；
   - 距结束 10 分钟内：`任务即将结束`；
   - 已超时：`有 N 项任务需要调整`。
4. 当前时间达到 `free_end` 后，页面显示“查看本次复盘”入口并自动请求 `/review`；用户可手动返回计划页。
5. 复盘页逐项显示结果；仅 `completed` 项显示三档感受按钮。保存后刷新复盘统计。
6. 若当前会话已有“低分”或“跳过”产生的排除记录，计划页显示简短摘要，例如“已为你避开 2 组不喜欢的任务”。不显示内部 `feedback_group` 标识。
7. 用户替换计划项后，任务卡片在本次页面停留期间展示后端返回的替换原因，例如“因你希望居家且独处，已换成同类轻量任务”。

## 5.1 已有功能的前端可见化

负向偏好记忆与任务替换原因已经由现有后端维护；本轮不改变它们的判定规则，只补齐前端表达：

| 场景 | 现有后端来源 | 前端呈现 |
| --- | --- | --- |
| 用户给任务 1–2 分或跳过 | `recommendation_memory` | 计划页顶部的“已避开”摘要；不暴露具体内部任务组名称 |
| 用户执行“更换任务” | 替换接口中的 `replacement_reason` | 新任务卡片下的原因标签，并在操作完成时显示一次轻提示 |

## 6. 建议规则

复盘建议保持确定性、可解释，不调用大模型：

| 条件 | 建议 |
| --- | --- |
| 完成率 >= 75% | 下次可维持当前计划密度 |
| 完成率 < 50% | 下次建议选择更轻的计划密度或缩短时段 |
| 未完成数 > 0 | 下次预留更多缓冲和休息时间 |
| `dissatisfied_count` > 0 | 下次优先替换感受不佳任务，不自动触发任务组排除 |
| 跳过数 > 0 | 已有排除规则继续生效，复盘说明已避开相似任务 |

## 7. 错误处理与兼容性

1. 复盘和感受写入均使用 `plan_id + session_id` 校验归属。
2. 非完成任务提交感受返回 409；非法感受值由 Pydantic 返回 422。
3. 重复刷新幂等：没有新超时任务时不重复写入事件。
4. 旧计划没有感受记录时，三类感受计数为 0，仍可正常查看复盘。
5. 前端接口失败时保留现有计划页，不阻断开始、完成、跳过和重排操作。

## 8. 测试与验收

1. 到结束时间未处理的 `pending` 和 `active` 任务仅被标记一次为 `needs_adjustment`。
2. 刷新接口返回可开始、即将结束、需要调整的提醒摘要。
3. 仅已完成任务能保存三档感受，重复提交覆盖旧值。
4. 计划结束后的复盘汇总完成、跳过、未完成和三档感受计数正确。
5. 前端定时刷新只在结果页运行且卸载时清理；计划结束后可进入复盘页。
6. 既有执行、反馈、负向推荐与计划编辑回归测试继续通过。

## 9. 文件边界

| 文件 | 变更 |
| --- | --- |
| `review_service.py` | 新建：刷新、感受、复盘聚合 |
| `main.py` | 装配服务与新增三条路由 |
| `frontend/api.js` | 新增 refresh、保存感受、读取复盘 API 包装 |
| `frontend/app.js` | 网页提醒、复盘页面、感受交互和定时器 |
| `tests/test_review_service.py` | PostgreSQL 服务级回归 |
| `tests/test_review_api.py` | API 主链路回归 |
| `tests/frontend-execution.test.js` | 提醒和复盘前端行为回归 |
| `README.md`、`docs/api.md` | 使用方式和接口契约 |
