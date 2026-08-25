# 用户历史偏好与执行前调整设计

**日期：** 2026-08-25  
**状态：** 待用户评审  
**范围：** 用户级历史偏好学习、开始任务前精力确认、换成更轻松任务、任务起止时间调整、未来账号体系预留

## 1. 目标与边界

第二阶段目标是让产品从“本次会话内生成计划”升级为“下次推荐能自动利用历史偏好”的空闲时间规划工具。

本阶段优先解决三件事：

1. 系统根据用户历史完成、跳过、替换行为，自动影响下次推荐。
2. 用户开始任务前确认当下精力；精力偏低时可以快速换成更轻松任务。
3. 用户可以继续修改每个任务的起止时间，并按调整后的时间执行。

本阶段不做完整登录注册、不做跨端同步 UI、不在前端展示推荐解释、不引入大模型和外部活动 API。

## 2. 用户级历史偏好

现有 `recommendation_memory` 主要按 `session_id` 记录当前会话的负向排除。第二阶段新增用户级历史偏好层，使用 `user_id` 作为长期学习主键。

当前 MVP 先由前端生成匿名 `user_id` 并保存到浏览器；未来上线登录后，可把匿名 `user_id` 合并或绑定到真实账号。

### 2.1 数据来源

历史偏好只采集强行为信号：

| 行为 | 含义 | 对推荐影响 |
| --- | --- | --- |
| 完成任务 | 用户愿意实际执行 | 同分类、同任务组、相近时长和相近场景加权 |
| 跳过任务 | 用户当下不想做 | 当前任务组降权 |
| 替换任务 | 原任务不合适 | 原任务组降权，新任务完成后再加权 |

用户完成后填写的复盘感受可以作为辅助字段保留，但本阶段不作为主要权重来源。

### 2.2 新数据表

```sql
CREATE TABLE user_profiles (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    linked_account_id TEXT
);

CREATE TABLE user_task_history (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL REFERENCES plan_items(id) ON DELETE CASCADE,
    task_id TEXT,
    feedback_group TEXT NOT NULL,
    category TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('completed', 'skipped', 'replaced_from', 'replaced_to')),
    duration_minutes INTEGER NOT NULL,
    outing TEXT,
    company TEXT,
    occurred_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_user_task_history_user_time
ON user_task_history(user_id, occurred_at DESC);

CREATE INDEX idx_user_task_history_user_group
ON user_task_history(user_id, feedback_group);
```

`linked_account_id` 是未来账号体系预留字段。MVP 不填该字段，也不需要登录接口。

## 3. 推荐权重规则

推荐模块在生成候选任务后，读取用户历史并调整排序。

### 3.1 加权规则

| 历史信号 | 权重变化 |
| --- | --- |
| 近期完成同任务组 | 明显加权 |
| 近期完成同分类 | 轻度加权 |
| 多次完成相近时长任务 | 相近时长任务轻度加权 |
| 跳过或替换过同任务组 | 降权 |
| 最近一次明确跳过同任务组 | 强降权 |

排序仍要先满足预算、出行、同行、时间约束。历史偏好只改变同等可行任务之间的优先级，不强行推荐不符合前置条件的任务。

### 3.2 不展示解释

历史偏好只在后端影响推荐结果。前端不显示“因为你之前完成过……”等说明，避免页面变重。

## 4. 开始任务前精力确认

用户点击“开始任务”时，前端先展示一个轻量确认面板：

```text
现在的精力如何？
- 充足
- 一般
- 偏低
```

选择“充足”或“一般”时，正常调用现有开始接口：

```text
POST /api/v1/plans/{plan_id}/items/{item_id}/execution/start
```

选择“偏低”时，不直接开始原任务，而是提示用户换成更轻松任务。

## 5. 换成更轻松任务

新增轻松替换能力，复用现有计划替换和版本机制，但候选排序更强调低负担。

### 5.1 更轻松任务判定

同分类内优先选择：

1. 持续时间更短；
2. 预算更低；
3. 出行成本更低，优先 `home`，其次 `nearby`；
4. 社交成本更低，优先 `solo` 或 `both`；
5. 恢复型和低压力任务优先。

若同分类没有可用任务，可以返回 409 并提示用户改时间、跳过或重新生成计划。本阶段不跨分类替换，避免计划覆盖的兴趣方向被破坏。

### 5.2 历史排除

轻松替换必须继续排除：

1. 当前任务；
2. 当前计划中已经出现过的任务；
3. `replacement_history` 中出现过的任务；
4. 当前会话不再推荐的任务组；
5. 用户历史中多次跳过或替换掉的任务组。

## 6. 起止时间调整

已有的计划项时间编辑继续保留，并作为第二阶段的正式能力：

```text
PATCH /api/v1/plans/{plan_id}/items/{item_id}
```

后端继续校验：

1. 结束时间必须晚于开始时间；
2. 任务必须在整份计划可用时间内；
3. 不能和其他未跳过任务冲突；
4. 使用 `expected_version` 防止旧页面覆盖新计划。

用户修改时间后，生成新的计划版本；执行流程按新版本继续。

## 7. 后端接口

新增或扩展以下接口：

```text
POST /api/v1/users/anonymous
GET  /api/v1/users/{user_id}/history/summary
POST /api/v1/plans/{plan_id}/items/{item_id}/execution/prepare
POST /api/v1/plans/{plan_id}/items/{item_id}/replace-easier
```

### 7.1 匿名用户

`POST /api/v1/users/anonymous` 创建或恢复匿名用户：

```json
{
  "user_id": "user_xxx",
  "created": true
}
```

前端首次打开页面时调用，之后把 `user_id` 存入 `localStorage`。后续创建会话、保存偏好、生成计划和执行任务时都可以携带该用户标识。

### 7.2 历史摘要

`GET /api/v1/users/{user_id}/history/summary` 返回用户历史统计，主要用于调试和未来个人页：

```json
{
  "completed_count": 12,
  "skipped_count": 3,
  "replaced_count": 5,
  "top_completed_categories": ["松弛疗愈", "自我成长"],
  "avoided_group_count": 4
}
```

正式推荐页不展示该解释。

### 7.3 执行前准备

`POST /execution/prepare` 接收当下精力：

```json
{
  "energy": "high | medium | low"
}
```

返回：

```json
{
  "item_id": "item_xxx",
  "energy": "low",
  "recommended_action": "replace_easier",
  "can_start": false
}
```

若 `energy` 为 `high` 或 `medium`，返回 `recommended_action = start`。

### 7.4 更轻松替换

`POST /replace-easier` 返回替换后的整份计划：

```json
{
  "plan_id": "plan_xxx",
  "version": 4,
  "items": []
}
```

该接口内部复用计划版本保存、时间冲突校验和 `replacement_history`。

## 8. 前端流程

1. 页面初始化时恢复或创建匿名 `user_id`。
2. 创建 session 或保存前置条件时携带 `user_id`。
3. 生成计划时，后端读取该用户的历史偏好并影响推荐排序。
4. 用户点击“开始任务”后，先选择当下精力。
5. 精力充足或一般：正常开始任务。
6. 精力偏低：显示“换成更轻松任务”按钮。
7. 用户点击后调用 `replace-easier`，页面展示新任务和原有时间段。
8. 用户仍可手动编辑新任务起止时间，再按调整后流程执行。

## 9. 错误处理

1. 匿名用户不存在时，后端返回 404，前端重新创建匿名用户并重试一次。
2. 历史表写入失败不阻断核心执行流程，但要记录错误并返回普通计划结果。
3. 轻松替换没有候选任务时返回 409，前端提示用户调整时间、跳过或重新生成计划。
4. `user_id` 不参与安全认证，公开上线前必须补齐登录、鉴权和隐私策略。
5. 老用户没有历史记录时，推荐逻辑退回现有排序。

## 10. 测试与验收

1. 匿名 `user_id` 可创建、恢复，并被前端持久保存。
2. 完成任务后写入 `user_task_history(action='completed')`。
3. 跳过任务后写入 `user_task_history(action='skipped')`。
4. 替换任务后写入 `replaced_from` 和 `replaced_to`。
5. 下次生成计划时，已完成任务相关分类或任务组排序更靠前。
6. 下次生成计划时，多次跳过或替换掉的任务组排序更靠后。
7. 点击开始任务先出现精力确认。
8. 精力偏低时不会直接开始原任务，而是引导更轻松替换。
9. 更轻松替换继续排除当前任务、历史替换任务和负向任务组。
10. 手动修改起止时间后，执行接口按新计划版本正常开始、完成和跳过。

## 11. 文件边界

| 文件 | 预计变更 |
| --- | --- |
| `user_history_service.py` | 新建：匿名用户、历史行为写入、历史摘要、推荐权重读取 |
| `recommendation_module.py` | 读取用户历史权重，调整候选任务排序 |
| `recommendation_memory.py` | 保留会话级排除，与用户历史层并行 |
| `plan_module.py` | 新增更轻松替换接口能力 |
| `execution_service.py` | 完成、跳过时写入用户历史 |
| `main.py` | 装配用户历史服务，新增匿名用户、历史摘要、准备执行、轻松替换路由 |
| `frontend/api.js` | 新增用户、历史、执行准备、轻松替换 API 包装 |
| `frontend/app.js` | 初始化匿名用户，开始前精力确认，精力低时轻松替换 |
| `tests/` | 增加用户历史、推荐权重、执行前准备、轻松替换和前端流程测试 |
| `README.md`、`docs/api.md` | 更新第二阶段能力、启动与接口说明 |

## 12. 分阶段落地

建议拆成四个提交完成：

1. 用户历史表与服务：匿名用户、行为写入、历史摘要。
2. 推荐排序接入历史偏好：完成加权、跳过和替换降权。
3. 执行前精力确认与轻松替换：后端接口和前端交互。
4. 文档与主链路测试：README、API 文档、Python 与前端回归测试。

这样每个提交都可独立验证，出现问题时也能快速定位。
