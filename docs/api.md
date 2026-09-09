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

## Frontend Runtime

正式前端是静态网页，可作为 PWA 部署。入口文件包括：

- `frontend/index.html`
- `frontend/config.js`
- `frontend/manifest.json`
- `frontend/service-worker.js`
- `frontend/api.js`
- `frontend/flow.js`
- `frontend/app.js`

`frontend/config.js` 用于配置线上 API 地址：

```javascript
window.FREE_TIME_API_BASE_URL = 'https://api.example.com';
```

本地开发时该值可以保持为空，前端会默认请求当前网页主机名的 `:8000` 端口。正式上线时应改为公网 HTTPS 后端地址；如果使用同域名 Nginx 反向代理，可以设置为该域名本身，例如 `https://example.com`。

部署模板位于：

- `deploy/.env.production.example`
- `deploy/frontend-config.production.example.js`
- `deploy/nginx-free-time-agent.conf`
- `deploy/README-deploy.md`

Service Worker 只缓存前端壳页面和静态资源，不缓存 `/api/v1/` 和 `/health` 请求。这样用户刷新页面时前端可以更快打开，但会话、问卷、计划、执行和反馈数据仍然实时来自 FastAPI 与 PostgreSQL。

## Health

### 检查后端服务

`GET /health`

后端正常时返回 `data.status = "ok"`。该接口不访问数据库，用于判断 API 服务是否已启动。

### 检查 PostgreSQL

`GET /api/v1/health/database`

后端会执行一次只读的 `SELECT 1`。数据库正常时返回 `data.status = "ok"`；未配置或无法连接时返回 `503`，错误码为 `database_unavailable`。

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

如果当前预算、出行、同行或时间约束导致无法覆盖全部选择分类，返回 `409`，并在 `error.details` 中附带前端可执行的修复方案：

```json
{
  "data": null,
  "error": {
    "code": "questionnaire_conflict",
    "message": "当前约束下无法覆盖全部选择分类",
    "details": {
      "missing_categories": ["社交连接"],
      "recovery_options": [
        {
          "id": "relax_constraints",
          "label": "放宽条件重新生成",
          "description": "扩大预算、出行和同行范围，让系统有更多候选任务。",
          "profile_patch": {
            "budget": "high",
            "outing": "any",
            "company": "both",
            "pace": "balanced"
          }
        }
      ]
    }
  }
}
```

正式前端会把 `recovery_options` 渲染为错误条下方的按钮。用户点击后，前端会保存调整后的偏好并重新调用生成计划接口。

### 查询计划

`GET /api/v1/sessions/{session_id}/plan`

返回 `plan_id`、版本、时间范围、任务数组和未安排任务 ID。

### 前端复制计划清单

复制计划不新增后端接口。正式像素前端会读取当前 `GET /api/v1/sessions/{session_id}/plan` 返回的计划对象，并在浏览器中整理为纯文本执行清单。

清单内容包括：

- 当前 `Session ID`。
- 用户选择的偏好方向。
- 每个计划项的推荐起止时间。
- 任务标题、任务分类和当前执行状态。

用户点击“复制计划”时，前端优先使用浏览器剪贴板 API；如果浏览器不允许自动写入剪贴板，则弹出文本框让用户手动复制。该动作不修改 PostgreSQL，也不会改变计划版本号。

## Recommendation Adjustment

推荐调节用于正式像素前端的任务卡片按钮。它不需要 Token；后端通过当前 `session_id`、`plan_id` 和计划版本校验请求。

### 调节计划内任务

`POST /api/v1/plans/{plan_id}/items/{item_id}/adjust`

```json
{
  "expected_version": 3,
  "adjustment": "easier",
  "user_id": "user_xxx"
}
```

`adjustment` 可选值：

| 值 | 前端按钮 | 选择逻辑 |
| --- | --- | --- |
| `easier` | 更轻松 | 优先轻松度更高、体力或社交压力更低的同分类任务。 |
| `shorter` | 更短时间 | 只选择时长更短的同分类任务。 |
| `cheaper` | 更低预算 | 只选择预算更低的同分类任务。 |
| `nearer` | 更近/居家 | 只选择出行或地点依赖更近的同分类任务。 |
| `less_social` | 少社交 | 只选择社交压力更低或更适合独处的同分类任务。 |
| `more_growth` | 成长感 | 在自我成长分类内选择更偏学习、阅读、练习、记录或复盘的任务。 |

成功时返回新的完整计划版本。后端会先把原任务加入当前会话的任务 ID 排除池，再保存新计划版本，因此连续调节不会回到已经出现过的任务。

### 调节推荐池任务

`POST /api/v1/sessions/{session_id}/recommendations/{task_id}/adjust`

```json
{
  "adjustment": "shorter",
  "current_task_ids": ["task_calm_01", "task_calm_07", "task_energy_03"],
  "user_id": "user_xxx"
}
```

`current_task_ids` 是前端当前已经展示在推荐池或计划里的任务 ID。后端会同时排除：

- 当前被调节的任务。
- 当前页面已经展示的任务。
- 当前会话中以前被换掉或调节过的任务。
- 当前会话中低分或跳过后排除的任务组。

成功响应：

```json
{
  "task": {
    "id": "task_calm_11",
    "title": "整理一角桌面并播放轻音乐",
    "category": "松弛疗愈",
    "reason_text": "你选择了「松弛疗愈」...",
    "replacement_reason": "已按「更短时间」避开「原任务」，换成同属松弛疗愈且本会话未出现过的任务。"
  },
  "recommendation_memory": {
    "excluded_group_count": 0,
    "excluded_task_count": 3,
    "adjustment_excluded_task_count": 2
  }
}
```

如果没有满足当前按钮意图和硬约束的新任务，返回 `409`，提示 `当前没有更合适的任务`；前端会保留原任务。

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

### 刷新网页内执行提醒

`POST /api/v1/plans/{plan_id}/execution/refresh`

不需要请求体。服务端以自身当前时间批量检查当前计划中处于 `pending` 或 `active` 的任务；已过 `end_at` 的任务只会一次性变为 `needs_adjustment` 并写入执行事件。

返回任务状态、当次新增事件和网页提醒摘要：

```json
{
  "plan_id": "plan_xxx",
  "reminders": {
    "startable_titles": ["居家拉伸"],
    "ending_soon_titles": [],
    "needs_adjustment_count": 0
  }
}
```

前端仅在计划页打开时调用一次并每 30 秒轮询；关闭或离开页面后不会继续提醒。

## Review

### 保存完成感受

`POST /api/v1/plans/{plan_id}/items/{item_id}/reflection`

```json
{"sentiment": "satisfied"}
```

`sentiment` 只能是 `satisfied`、`neutral` 或 `dissatisfied`。仅 `completed` 任务可保存，未完成任务返回 `409`；非法值由请求模型返回 `422`。同一任务再次提交会覆盖当前感受，不会新增第二条记录。

### 获取统一复盘

`GET /api/v1/plans/{plan_id}/review`

接口会先执行一次服务端截止检查，再返回 `in_progress` 或 `finished`、完成/跳过/未完成数量、三档感受数量、逐项结果和确定性建议。只有服务端当前时间达到计划的 `free_end` 后，`status` 才为 `finished`。

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

前端会根据评分切换原因标签：

- `1-2` 分：`太累`、`太贵`、`不想出门`、`时间太长`、`不感兴趣`、`社交压力大`。
- `3` 分：`还可以`、`时间一般`、`有点费力`、`可以偶尔做`。
- `4-5` 分：`容易开始`、`符合当前状态`、`下次还想做`、`时间刚好`、`推荐准确`。

其中 `1-2` 分会触发当前会话的推荐记忆，后续更换或重新生成计划时会减少相似任务出现。

### 查询计划反馈

`GET /api/v1/plans/{plan_id}/feedback`

返回当前计划下已经提交的任务反馈列表。

## User History Insight

### 获取历史计划与偏好学习洞察

`GET /api/v1/users/{user_id}/history/insight`

该接口用于正式像素前端的“我的历史”视图。它会从 PostgreSQL 中聚合当前匿名用户的全部历史行为，包括完成、跳过、替换和 1-2 分低分反馈。

成功响应示例：

```json
{
  "user_id": "user_xxx",
  "has_history": true,
  "empty_state": "完成或跳过几个任务后，这里会显示系统学到的偏好。",
  "summary": {
    "completed_count": 6,
    "this_week_completed_count": 3,
    "skipped_count": 2,
    "replaced_count": 4,
    "low_rating_count": 1
  },
  "this_week_completed_tasks": [
    {
      "title": "散步十五分钟",
      "category": "活力充电",
      "feedback_group": "energy_walk",
      "completed_at": "2026-09-07T10:20:00+00:00"
    }
  ],
  "recent_plans": [
    {
      "plan_id": "plan_xxx",
      "created_at": "2026-09-07T09:30:00+00:00",
      "status": "confirmed",
      "completed_count": 2,
      "skipped_count": 1,
      "replaced_count": 1
    }
  ],
  "favorite_categories": [
    {"category": "活力充电", "completed_count": 4}
  ],
  "avoided_groups": [
    {
      "feedback_group": "crowded_social",
      "category": "社交连接",
      "negative_count": 2
    }
  ],
  "learning_notes": [
    "你更常完成「活力充电」类任务，系统会在同等条件下提高这类任务排序。"
  ],
  "next_recommendation_strategy": [
    "继续避开当前会话和历史中反复跳过或替换的细任务组。"
  ]
}
```

如果该用户还没有历史行为，`has_history=false`，统计值为 0，列表为空；前端会显示空状态并引导用户先完成一次计划。

### 典型执行顺序

```text
生成计划 → 确认计划 → 开始任务 → 完成任务 → 提交反馈 / 可选完成感受
                         ↘ 网页刷新检查 → needs_adjustment → 重新排程
计划结束 → 统一复盘 → 查看完成、跳过、未完成与下次建议
生成新计划后 → 点击我的历史 → 查看系统学到的偏好与下次推荐策略
```

## 错误

- `404`：会话或计划不存在。
- `409`：问卷未提交、分类无法覆盖或业务状态冲突。
- `410`：会话已过期。
- `422`：请求字段校验失败。
- `503`：PostgreSQL 暂不可用。
