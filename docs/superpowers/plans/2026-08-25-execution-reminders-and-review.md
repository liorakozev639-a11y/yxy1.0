# 网页提醒与计划复盘 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为已生成的空闲计划增加网页内执行提醒、统一复盘、完成感受，以及现有负向反馈和替换原因的可见化。

**Architecture:** 新建 `ReviewService` 作为 PostgreSQL 同步服务，复用 `plan_items.status` 和 `execution_events` 作为执行状态唯一来源。FastAPI 只装配三个薄路由；前端在结果页进入时及每 30 秒刷新一次，页面离开时停止定时器，并在计划结束后切换到复盘视图。

**Tech Stack:** Python 3.12、FastAPI、Pydantic、psycopg 3、PostgreSQL、原生 JavaScript、Node 内置测试、unittest。

**Spec:** `docs/superpowers/specs/2026-08-25-execution-reminders-and-review-design.md`

## Global Constraints

- 只使用 PostgreSQL；不加入内存仓储、MQ、后台定时器或异步队列。
- 只提供网页内提醒；不加入浏览器通知、邮件、账号或跨会话数据。
- `plan_items.status` 和 `execution_events` 是执行状态唯一来源；复盘不复制执行状态。
- `satisfied`、`neutral`、`dissatisfied` 是可选完成感受；只有既有 1–2 分评分和跳过会触发任务组排除。
- 每个任务完成后独立运行回归测试并提交；永远不暂存 `backup-before-github-20260814-1/`。

---

### Task 1: ReviewService 与 PostgreSQL 完成感受表

**Files:**
- Create: `review_service.py`
- Create: `tests/test_review_service.py`
- Modify: `execution_service.py`

**Interfaces:**
- Consumes: `ExecutionService.check_deadline(session_id, plan_id, item_id, now) -> dict[str, Any]` 和 `SessionService.require_active(session_id)`。
- Produces: `ReviewService.refresh_plan(session_id, plan_id, now=None) -> dict[str, Any]`、`save_reflection(session_id, plan_id, item_id, sentiment) -> dict[str, Any]`、`get_review(session_id, plan_id, now=None) -> dict[str, Any]`。
- Database: 新表 `task_completion_reflections`，唯一键为 `(plan_id, item_id)`。

- [ ] **Step 1: 写入失败的服务级测试**

在 `tests/test_review_service.py` 用现有 `ExecutionServiceLiveTests` 的 PostgreSQL 建表方式创建一份计划：一个已完成项、一个已超时 `pending` 项、一个正在进行项。测试下列契约：

```python
refreshed = service.refresh_plan(session_id, plan_id, now=after_deadline)
self.assertEqual(refreshed["summary"]["needs_adjustment_count"], 2)
self.assertEqual(refreshed["reminders"]["needs_adjustment_count"], 2)

saved = service.save_reflection(
    session_id, plan_id, completed_item_id, "satisfied"
)
self.assertEqual(saved["sentiment"], "satisfied")

review = service.get_review(session_id, plan_id, now=after_plan_end)
self.assertEqual(review["status"], "finished")
self.assertEqual(review["summary"]["completed_count"], 1)
self.assertEqual(review["summary"]["unfinished_count"], 2)
self.assertEqual(review["summary"]["satisfied_count"], 1)
```

另加断言：重复调用 `refresh_plan` 不增加事件数量；对非 `completed` 项调用 `save_reflection` 抛出 `HTTPException(status_code=409)`；第二次保存同一任务改为 `neutral` 后复盘只计入一条中立感受。

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
Set-Location D:\yxy1.0
.\.venv\Scripts\python.exe -m unittest tests.test_review_service -v
```

Expected: FAIL，报错为 `ModuleNotFoundError: No module named 'review_service'`。

- [ ] **Step 3: 实现最小 ReviewService 与批量截止检查**

创建 `review_service.py`。服务构造器接收数据库 URL、`SessionService` 和 `ExecutionService`；`init_schema()` 使用以下表结构，并额外建立 `(plan_id, item_id)` 唯一约束，不写入执行状态副本：

```python
CREATE TABLE IF NOT EXISTS task_completion_reflections (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL REFERENCES plan_items(id) ON DELETE CASCADE,
    sentiment TEXT NOT NULL CHECK (sentiment IN ('satisfied', 'neutral', 'dissatisfied')),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    UNIQUE (plan_id, item_id)
)
```

`refresh_plan` 先校验 session 和 plan 归属，读取当前计划中 `pending`、`active` 项，对每项调用既有 `ExecutionService.check_deadline`。然后读取全部计划项并返回：

```python
{
    "plan_id": plan_id,
    "items": items,
    "summary": {"total_tasks": total, "needs_adjustment_count": needs_adjustment},
    "reminders": {
        "startable_titles": startable_titles,
        "ending_soon_titles": ending_soon_titles,
        "needs_adjustment_count": needs_adjustment,
    },
}
```

“可开始”条件为 `pending` 且 `start_at <= now < end_at`；“即将结束”条件为 `active` 且 `0 <= end_at - now <= 10 分钟`。使用服务器 `now`，不接受浏览器时间作为状态依据。

`save_reflection` 用 `SELECT ... FOR UPDATE` 校验该 item 属于该 session 的当前非 `superseded` 计划且状态为 `completed`，再使用 `INSERT ... ON CONFLICT (plan_id, item_id) DO UPDATE` 保存感受。`get_review` 先调用 `refresh_plan`，读取感受，计算三类结果和确定性建议。

为避免两个模块各自拼装截止规则，在 `execution_service.py` 增加只读辅助方法：

```python
def refresh_items(
    self,
    session_id: str,
    plan_id: str,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    # 读取候选 item_id 后逐项调用 check_deadline；返回每项 payload。
```

`ReviewService.refresh_plan` 调用该方法，而不是复制 `expire_if_needed` 的实现。

- [ ] **Step 4: 运行服务级测试并确认通过**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_execution_service tests.test_review_service -v
```

Expected: 两个模块全部 PASS，包含一次性超时事件、感受覆盖和复盘汇总断言。

- [ ] **Step 5: 提交服务层**

```powershell
git add execution_service.py review_service.py tests/test_review_service.py
git commit -m "feat: add execution review service"
```

### Task 2: FastAPI 路由、输入校验与 API 回归

**Files:**
- Modify: `main.py`
- Create: `tests/test_review_api.py`

**Interfaces:**
- Consumes: Task 1 的 `ReviewService`。
- Produces:
  - `POST /api/v1/plans/{plan_id}/execution/refresh`
  - `POST /api/v1/plans/{plan_id}/items/{item_id}/reflection`
  - `GET /api/v1/plans/{plan_id}/review`

- [ ] **Step 1: 写入失败的 API 主链路测试**

在 `tests/test_review_api.py` 沿用 `tests/test_phase_two_api.py` 的真实 PostgreSQL `TestClient` setup。先将一个 item 通过 start/complete 路由置为完成，再测试：

```python
refresh = client.post(f"/api/v1/plans/{plan_id}/execution/refresh")
self.assertEqual(refresh.status_code, 200, refresh.text)
self.assertIn("reminders", refresh.json()["data"])

reflection = client.post(
    f"/api/v1/plans/{plan_id}/items/{completed_item_id}/reflection",
    json={"sentiment": "satisfied"},
)
self.assertEqual(reflection.status_code, 200, reflection.text)

review = client.get(f"/api/v1/plans/{plan_id}/review")
self.assertEqual(review.status_code, 200, review.text)
self.assertIn("suggestions", review.json()["data"])
```

再测试：`{"sentiment": "bad"}` 返回 422；未完成项写感受返回 409；不存在或不属于该计划的 item 返回 404。

- [ ] **Step 2: 运行 API 测试并确认失败**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_review_api -v
```

Expected: FAIL，三个新路径返回 404。

- [ ] **Step 3: 在 main.py 装配服务并注册薄路由**

在 `main.py` 中：

1. 导入 `ReviewService`，增加 `ReflectionInput(BaseModel)`：

```python
class ReflectionInput(BaseModel):
    sentiment: Literal["satisfied", "neutral", "dissatisfied"]
```

2. 为 `create_app` 增加可选的 `review_service: Optional[ReviewService] = None`，按现有 `ExecutionService`/`FeedbackService` 模式在数据库可用时构造它，并增加 `require_review_service()`。
3. 三条路由均先通过 `PlanManagementService.session_id_for_plan(plan_id)` 取 session，再调用 ReviewService，统一使用 `success(...)` 包装。
4. `POST /execution/refresh` 不接收 `now` 请求体；`ReviewService` 只用服务器时间。这样避免客户端篡改任务是否超时的判定。

- [ ] **Step 4: 运行 API 与既有第二阶段测试并确认通过**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_phase_two_api tests.test_review_api -v
```

Expected: PASS，旧执行/评分接口和新增复盘接口均返回统一的 `{data, error}` 结构。

- [ ] **Step 5: 提交 API 层**

```powershell
git add main.py tests/test_review_api.py
git commit -m "feat: expose execution review API"
```

### Task 3: 前端 API 客户端与既有反馈可见化

**Files:**
- Modify: `frontend/api.js`
- Modify: `frontend/flow.js`
- Modify: `frontend/app.js`
- Modify: `tests/frontend-execution.test.js`
- Modify: `tests/frontend-flow.test.js`

**Interfaces:**
- Consumes: Task 2 的三条 API 和既有计划响应中的 `recommendation_memory`、任务项中的 `replacement_reason`。
- Produces: `api.refreshExecution(planId)`、`api.saveReflection(planId, itemId, input)`、`api.getReview(planId)`，以及可复用的提醒/记忆展示数据。

- [ ] **Step 1: 写入失败的 Node 测试**

扩展 `tests/frontend-execution.test.js`，记录三个新方法的 URL 和方法：

```javascript
await api.refreshExecution('plan_1');
await api.saveReflection('plan_1', 'item_1', { sentiment: 'neutral' });
await api.getReview('plan_1');

assert.deepEqual(calls.slice(-3).map(({ url, options }) => [url, options.method]), [
  ['http://127.0.0.1:8000/api/v1/plans/plan_1/execution/refresh', 'POST'],
  ['http://127.0.0.1:8000/api/v1/plans/plan_1/items/item_1/reflection', 'POST'],
  ['http://127.0.0.1:8000/api/v1/plans/plan_1/review', 'GET'],
]);
```

在 `tests/frontend-flow.test.js` 为纯函数增加对推荐记忆摘要的验证：输入 `excluded_group_count: 2` 返回用户可读文本 `已为你避开 2 组不喜欢的任务`，输入 0 返回空字符串；不得输出 `feedback_group`。

- [ ] **Step 2: 运行前端测试并确认失败**

Run:

```powershell
node --test tests/frontend-execution.test.js tests/frontend-flow.test.js
```

Expected: FAIL，提示 `api.refreshExecution is not a function` 与缺少摘要函数。

- [ ] **Step 3: 实现 API 包装与纯展示辅助函数**

在 `frontend/api.js` 添加：

```javascript
function refreshExecution(planId) {
  return request(`/api/v1/plans/${planId}/execution/refresh`, { method: 'POST' });
}
function saveReflection(planId, itemId, input) {
  return request(`/api/v1/plans/${planId}/items/${itemId}/reflection`, {
    method: 'POST', body: input,
  });
}
function getReview(planId) {
  return request(`/api/v1/plans/${planId}/review`);
}
```

并将它们加入返回对象。`frontend/flow.js` 新增 `recommendationMemorySummary(memory)`，只使用整数 `excluded_group_count` 构造文本。`frontend/app.js` 在生成计划、跳过执行、低分反馈、替换任务和重新排程响应中保留/更新 `state.plan` 的 `recommendation_memory`，任务卡片内直接渲染 `replacement_reason`，而不仅放在详情弹窗内；替换成功使用 `showToast` 显示该原因。

- [ ] **Step 4: 运行 Node 测试并确认通过**

Run:

```powershell
node --test tests/frontend-execution.test.js tests/frontend-flow.test.js tests/frontend-visual.test.js
```

Expected: PASS，接口路径、用户可读排除摘要、卡片替换原因和像素前端原有结构均存在。

- [ ] **Step 5: 提交前端客户端与可见化**

```powershell
git add frontend/api.js frontend/flow.js frontend/app.js tests/frontend-execution.test.js tests/frontend-flow.test.js
git commit -m "feat: show recommendation feedback context"
```

### Task 4: 网页提醒、复盘界面与可选三档感受

**Files:**
- Modify: `frontend/app.js`
- Modify: `frontend/styles.css`
- Modify: `tests/frontend-execution.test.js`
- Modify: `tests/frontend-visual.test.js`

**Interfaces:**
- Consumes: Task 3 API 方法和 Task 2 refresh/review 响应。
- Produces: 结果页的 30 秒网页提醒、`state.review` 复盘视图、三档感受提交交互。

- [ ] **Step 1: 写入失败的前端行为与标记测试**

扩展 `tests/frontend-execution.test.js` 验证存在以下受控交互与生命周期标记：

```javascript
assert.match(app, /api\.refreshExecution/);
assert.match(app, /setInterval\(/);
assert.match(app, /clearInterval\(/);
assert.match(app, /data-action="view-review"/);
assert.match(app, /data-action="save-reflection"/);
assert.match(app, /satisfied/);
assert.match(app, /neutral/);
assert.match(app, /dissatisfied/);
```

扩展 `tests/frontend-visual.test.js`，要求 CSS 中存在 `.execution-reminder`、`.review-panel`、`.reflection-choice`，且没有覆盖现有像素风变量与响应式断点。

- [ ] **Step 2: 运行前端测试并确认失败**

Run:

```powershell
node --test tests/frontend-execution.test.js tests/frontend-visual.test.js
```

Expected: FAIL，缺少网页提醒、复盘和感受控件标记。

- [ ] **Step 3: 实现结果页刷新生命周期与复盘视图**

在 `frontend/app.js`：

1. 状态新增 `executionRefreshTimer`、`executionRefreshActive`、`review`、`reflectionItemId`、`reflectionSentiment`。
2. 实现 `refreshExecutionState()`：仅当 `state.step === 'result'` 且 `state.plan?.plan_id` 存在时调用 `api.refreshExecution`，把响应 items 合并进 `state.plan.items`，把 `reminders` 存到 state；失败时不清空已有计划，只调用既有 `showToast('执行状态暂时无法刷新')`。
3. 实现 `startExecutionRefresh()`：先清掉旧 timer，立即刷新一次，再通过 `setInterval(refreshExecutionState, 30000)` 开始轮询；实现 `stopExecutionRefresh()` 清理 timer。进入 result 后启动；`restart`、离开 result 或重新初始化前停止。不要在后端增加定时任务。
4. 在 `renderResult()` 顶部渲染 `.execution-reminder`：优先显示需要调整数，其次即将结束任务，再显示可开始任务。提醒只在网页打开时存在。
5. 当 refresh 或 `getReview` 发现 `review.status === 'finished'` 时，渲染“查看本次复盘”按钮；点击后调用 `api.getReview`，将 `state.review` 填入并使用 result 内的 `.review-panel` 取代时间线主体，保留“返回计划”按钮。
6. 复盘逐项列出 title、outcome 和已有 sentiment。只为 outcome 为 `completed` 的项绘制三个 `.reflection-choice` 按钮。点击选择不会写入；点击“保存感受”才调用 `api.saveReflection`，成功后重新 `api.getReview`。
7. 固定建议文本仅使用后端 `review.suggestions`，前端不重复推导完成率。`dissatisfied` 只显示体验记录，不调用评分或推荐排除接口。

在 `frontend/styles.css` 为提醒条、复盘面板、三档按钮增加像素边框、清晰的 completed/unfinished 色彩差异和 620px 移动端单列布局。使用现有 `--pixel-*` 色彩，卡片圆角保持 0。

- [ ] **Step 4: 运行前端测试并确认通过**

Run:

```powershell
node --test tests/frontend-execution.test.js tests/frontend-visual.test.js tests/frontend-flow.test.js
```

Expected: PASS，且前端静态断言证明只有结果页轮询、可进入复盘、完成项才出现三档感受。

- [ ] **Step 5: 手工浏览器验收**

启动本地 PostgreSQL、后端和静态前端后，在浏览器完成一次快速问卷并生成计划：

```powershell
Set-Location D:\yxy1.0
.\.venv\Scripts\python.exe -m http.server 5173 --bind 127.0.0.1 --directory frontend
```

确认：

1. 计划页有“已为你避开”摘要（先对一个完成项提交 1 分，或跳过一项）。
2. 点击“换一个”后，新卡片直接显示替换原因。
3. 将一项开始时间调至当前之前、结束时间调至 10 分钟内，刷新后出现网页提醒。
4. 完成项可以保存满意/一般/不满意；未完成项没有该控件。
5. 将计划结束时间调至过去后触发 refresh，查看复盘并看到完成、跳过、未完成汇总与建议。

- [ ] **Step 6: 提交网页交互**

```powershell
git add frontend/app.js frontend/styles.css tests/frontend-execution.test.js tests/frontend-visual.test.js
git commit -m "feat: add web execution reminders and review"
```

### Task 5: 接口文档、使用说明与全链路验证

**Files:**
- Modify: `docs/api.md`
- Modify: `README.md`
- Modify: `tests/live_core_flow.ps1`

**Interfaces:**
- Consumes: Task 1–4 已交付的服务、路由和前端。
- Produces: 可复制的接口契约、本地检查脚本和完整回归证据。

- [ ] **Step 1: 为文档验收添加可运行断言**

在 `tests/live_core_flow.ps1` 的计划生成后加入三条调用：刷新执行状态、将已完成测试任务保存 `satisfied` 感受、读取复盘。末尾 JSON 至少包含：

```powershell
@{
  plan_id = $plan.plan_id
  reminder_count = $refresh.data.reminders.needs_adjustment_count
  review_status = $review.data.status
  reflection = $reflection.data.sentiment
}
```

在脚本中若反射接口不是 200 或复盘没有 `summary`，使用 `throw` 中止。

- [ ] **Step 2: 运行扩展后的核心脚本并确认通过**

在 Task 2/4 完成后运行：

```powershell
.\tests\live_core_flow.ps1
```

Expected: PASS，脚本输出 `reminder_count`、`review_status` 和 `reflection`；这证明公开 HTTP 链路而非直接服务调用可用。

- [ ] **Step 3: 更新接口和项目说明**

在 `docs/api.md` 增加三条 API 的路径、方法、请求 JSON、成功响应、409/422 错误说明和“服务器时间决定超时”的约束。更新 `README.md` 的执行闭环部分：

- 网页打开期间每 30 秒刷新提醒；关闭页面后不提供后台提醒。
- 计划结束后可统一复盘；三档感受可修改且不影响低分排除。
- “已避开”摘要和替换原因是当前会话的透明说明，不显示内部任务组 id。
- 本地启动命令不包含真实数据库密码。

- [ ] **Step 4: 运行完整后端、前端与核心链路验证**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
node --test tests/*.test.js
.\tests\live_core_flow.ps1
git diff --check
```

Expected: Python 全部 PASS、Node 全部 PASS、核心脚本输出 review/reflection 字段、`git diff --check` 无输出且退出码为 0。

- [ ] **Step 5: 提交文档与验收脚本**

```powershell
git add README.md docs/api.md tests/live_core_flow.ps1
git commit -m "docs: document execution review workflow"
```
