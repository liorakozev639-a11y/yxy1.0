# 留白计划极简模式 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变完整模式主流程的前提下，用现有任务库提供“时长 + 精力 -> 立即可做的一条建议”，允许查看更多、休息和轻量反馈，并让两种模式共用偏好学习。

**Architecture:** 极简模式使用独立的推荐轮次与反馈表，不创建问卷、计划或执行记录。任务库与未来模型共用 `CandidateProvider` 契约；来源之后的硬约束、排序、持久化和 API 均由后端负责。首页共用现有匿名身份，完整模式与极简模式保留各自的会话 ID 和草稿。

**Tech Stack:** Python 3.12+、FastAPI、Pydantic、psycopg 3、PostgreSQL、静态 HTML/CSS/JavaScript、Python `unittest`、Node `node:test`。

**Spec:** `docs/superpowers/specs/2026-09-20-quick-mode-design.md`

## Global Constraints

- 实施目标是 `D:\yxy1.0` 当前代码；其工作区已有未提交修改。开始前先 `git status --short`，逐文件核对本计划所列路径，保留所有用户改动。不要用较旧的干净文档工作区覆盖正式仓库。
- 本期不调用 DeepSeek 或其他模型，不需要模型密钥、不消耗 Token；现有 `TASK_GENERATION_MODE=mock` 仍仅用于本地测试，不冒充 AI。
- 极简只询问正整数 `available_minutes` 与 `energy_level=low|medium|high`；预算固定 0、居家、可独自做；不可放宽硬条件凑满 10 项。
- 极简只从人工审核、立即可开始且有 `first_action` 的现有任务中选；不安排、不监督、不计完成，也不让“喜欢”进入完成统计。
- 推荐最多 10 个不同任务。首屏一个首选；查看更多展开其余候选；休息是中性选择。“不喜欢”不得循环回当前任务。
- 完整模式 API 形状、问卷、排程、执行和历史完成数保持现状；允许极简轻量反馈影响后续排序。
- 数据继续用同一个 PostgreSQL 和现有匿名 `user_id`；匿名 ID 不是认证凭证，不增加按任意 `user_id` 读取个人历史的新接口。
- 所有 API 沿用 `success(data)` 与现有错误封装；前端保持现有像素设计体系、中文文案和移动端可读性。
- 在提交或部署前运行对应单元、API、前端和完整模式回归测试；每次局部功能修改给用户可操作的测试步骤。不要在本计划执行前推送 GitHub 或部署 Vercel。
- 正式仓库原有文件有未提交改动，涉及这些文件的任务使用 `git add -p` 只暂存本任务的 hunk，并在每次 commit 前核对 `git diff --cached`；不要把原有改动顺带提交。

## Review Focus

1. `available_minutes` 为 0、负数、极大值或精力枚举错误时，API 应返回 422 且不运行推荐（Task 5）。
2. 合格候选为 0 或少于 10 时，只返回真实候选和休息入口，不放宽预算/居家限制、不重复任务（Task 3、5、6）。
3. 重复反馈、伪造任务 ID 或错配 `run_id/session_id` 时，不重复计权；非法对象返回 404/409（Task 4、5）。
4. 刷新或切换模式时，两种草稿和最近一轮结果均保留；极简反馈不会生成计划项或完成事件（Task 4、6）。
5. 完整模式的问卷、10 候选、排程、执行、评分和历史统计在没有极简反馈时不变；有反馈时只改变合法排序/排除（Task 2、4、7）。

---

## File Map And Dependency Order

1. `quick_task_catalog.py`：人工核对过的任务 ID 与第一步；`tests/test_quick_task_catalog.py`：准入数据检查。
2. `candidate_provider.py`：`RecommendationContext`、`CandidateTask`、`CandidateProvider`、任务库来源与降级包装；`tests/test_candidate_provider.py`：来源契约。
3. `quick_recommendation.py`：统一硬校验、精力/历史/启动阻力排序、理由；`tests/test_quick_recommendation.py`：纯业务逻辑。
4. `quick_recommendation_store.py`：推荐轮次/轻反馈 PostgreSQL 持久化；`user_history_service.py`：跨模式权重汇总；`tests/test_quick_recommendation_store.py`、`tests/test_user_history_recommendation.py`：数据库与排序。
5. `quick_recommendation_service.py`：协调来源、排序和存储；`main.py`：三个 API 端点；`tests/test_quick_recommendation_api.py`：API 合同。
6. `frontend/api.js`、`frontend/flow.js`、`frontend/app.js`、`frontend/styles.css`、`frontend/index.html`、`frontend/service-worker.js`：双模式界面、恢复与客户端请求；`tests/frontend-quick.test.js`：交互状态；现有前端测试：回归。
7. `docs/quick-mode-test.md`：人工验收；补齐全链路自动化与移动端、弱网检查。

**执行基线检查：** 在 `D:\yxy1.0` 中先记录 `git status --short`、`git diff -- main.py task_repository.py frontend/app.js frontend/api.js`，确认 700 条任务库的当前结构及已有改动后才动手。本计划中的函数和文件为新增契约；若执行时本地代码已出现同名实现，先读现状再合并，不覆盖。

### Task 1: 人工准入目录与第一步

**Files:**
- Create: `quick_task_catalog.py`
- Test: `tests/test_quick_task_catalog.py`
- Read: `task_repository.py`（保留现有 `Task` 及约 700 条原始任务）

**Interfaces:**
- Consumes: `TaskRepository().public_tasks: list[Task]`；`Task.id/duration/budget/outing/company/status`。
- Produces: `QUICK_FIRST_ACTIONS: dict[str, str]`；`quick_metadata(task: Task) -> str | None`，仅人工核对过且符合立即开始准入的任务有返回值。

- [ ] **Step 1: 写失败测试。**

```python
import unittest
from quick_task_catalog import QUICK_FIRST_ACTIONS, quick_metadata
from task_repository import TaskRepository

class QuickCatalogTest(unittest.TestCase):
    def test_curated_entries_are_real_safe_and_actionable(self):
        by_id = {task.id: task for task in TaskRepository().public_tasks}
        self.assertGreaterEqual(len(QUICK_FIRST_ACTIONS), 10)
        for task_id, action in QUICK_FIRST_ACTIONS.items():
            task = by_id[task_id]
            self.assertEqual(task.status, "approved")
            self.assertEqual(task.budget, 0)
            self.assertEqual(task.outing, "home")
            self.assertIn(task.company, {"solo", "both"})
            self.assertTrue(action.strip())
            self.assertEqual(quick_metadata(task), action)

    def test_unreviewed_task_does_not_enter_quick_mode(self):
        task = next(t for t in TaskRepository().public_tasks if t.id not in QUICK_FIRST_ACTIONS)
        self.assertIsNone(quick_metadata(task))
```

- [ ] **Step 2: 运行 `& '.\.venv\Scripts\python.exe' -m unittest tests.test_quick_task_catalog -v`。**预期模块不存在，RED。
- [ ] **Step 3: 在 `quick_task_catalog.py` 定义 `QUICK_FIRST_ACTIONS` 和 `quick_metadata`。**以下 ID 已在当前正式任务库中核对；落地前再核对标题、时长与前置条件。优先覆盖低/中/高精力及 10/15/20/30 分钟；当前 5 分钟条目另核查，无合适条目时保留 5 分钟空状态，不把 10 分钟任务硬塞进去。排除需要物品、预约、购买、等人或临时出门的任务。

```python
from task_repository import Task

QUICK_FIRST_ACTIONS: dict[str, str] = {
    "task_recovery_01": "坐稳，把双脚放在地上，缓慢呼吸一次。",
    "task_recovery_02": "找个安全舒适的位置坐下或躺下。",
    "task_recovery_08": "坐稳，注意到自己当下的一次呼吸。",
    "task_recovery_11": "放松肩膀，尝试缓慢地用腹部呼吸。",
    "task_recovery_32": "闭上眼睛，先让视线离开屏幕。",
    "task_recovery_18": "坐稳，先觉察双脚与地面的接触。",
    "task_energy_01": "站稳，先轻轻活动肩膀和颈部。",
    "task_energy_06": "站稳，缓慢转动肩膀一次。",
    "task_energy_11": "起身站稳，先做一次温和伸展。",
    "task_energy_16": "轻轻转动手腕与脚踝各一次。",
    "task_energy_22": "站在原地，缓慢伸展上肢一次。",
    "task_energy_27": "放松肩膀，轻轻打开胸口。",
}

def quick_metadata(task: Task) -> str | None:
    return QUICK_FIRST_ACTIONS.get(task.id)
```

- [ ] **Step 4: 重跑该测试，预期 PASS；再运行 `& '.\.venv\Scripts\python.exe' -m unittest tests.test_task_repository_expansion -v` 确认任务库未破坏。**
- [ ] **Step 5: 只提交本任务文件。** `git add quick_task_catalog.py tests/test_quick_task_catalog.py`；核对 `git diff --cached` 后 `git commit -m "feat: curate immediately actionable quick tasks"`。

### Task 2: 共用候选来源接口与保守回退

**Files:**
- Create: `candidate_provider.py`
- Modify: `mvp_orchestrator.py` 的 `_recommend`：在 `rules` 分支通过任务库提供者取候选，后续 `recommend_tasks(...)` 和 `mock` 分支保持现状
- Test: `tests/test_candidate_provider.py`
- Test: `tests/test_mvp_integration.py`

**Interfaces:**
- Consumes: `TaskRepository.search_tasks(session_id, budget_limit, max_duration, outing, company, categories=None, scenarios=None) -> list[Task]`；Task 1 的 `quick_metadata`。
- Produces: `RecommendationContext(mode: Literal["quick", "full"], session_id: str, user_id: str | None, available_minutes: int, energy_level: Literal["low", "medium", "high"], categories: tuple[str, ...] = (), budget_limit: int = 0, outing: str = "home", company: str = "solo", scenarios: tuple[str, ...] = ())`；`CandidateTask(task: Task, first_action: str, source: str, immediate_start: bool = False, startup_cost: int = 0)`；`CandidateProvider.generate(context: RecommendationContext) -> list[CandidateTask]`；`is_quick_eligible(context, item) -> bool`；`TaskBankProvider`；`FallbackCandidateProvider(primary, fallback)`。

- [ ] **Step 1: 写契约与回退失败测试。**

```python
import unittest
from candidate_provider import RecommendationContext, TaskBankProvider, FallbackCandidateProvider
from task_repository import TaskRepository

class CandidateProviderTest(unittest.TestCase):
    def test_quick_bank_only_returns_curated_tasks(self):
        context = RecommendationContext("quick", "sess_test", None, 30, "low")
        candidates = TaskBankProvider(TaskRepository()).generate(context)
        self.assertTrue(candidates)
        self.assertTrue(all(c.first_action and c.source == "task_bank" for c in candidates))

    def test_primary_failure_falls_back_to_bank(self):
        class BrokenProvider:
            def generate(self, context):
                raise TimeoutError("upstream timeout")
        context = RecommendationContext("quick", "sess_test", None, 30, "low")
        results = FallbackCandidateProvider(BrokenProvider(), TaskBankProvider(TaskRepository())).generate(context)
        self.assertTrue(results)
        self.assertTrue(all(c.source == "task_bank" for c in results))
```

- [ ] **Step 2: 运行 `& '.\.venv\Scripts\python.exe' -m unittest tests.test_candidate_provider -v`，预期 import 失败。**
- [ ] **Step 3: 新增窄契约。**`TaskBankProvider.generate()` 用现有 `search_tasks`；`quick` 用 catalog 筛选并置 `immediate_start=True`，`full` 不强制第一步。公共 `is_quick_eligible` 检查审核、时间、预算、居家、独自可做、立即开始标志与第一步。`FallbackCandidateProvider` 只捕获明确的来源失败（如超时），也在首选来源无任何合格候选时回退任务库；不要吞掉编程错误。来源只写内部日志，不透出到 UI。代码骨架：

```python
@dataclass(frozen=True)
class CandidateTask:
    task: Task
    first_action: str
    source: str
    immediate_start: bool = False
    startup_cost: int = 0

class CandidateProvider(Protocol):
    def generate(self, context: RecommendationContext) -> list[CandidateTask]: ...
```

- [ ] **Step 4: 在 `mvp_orchestrator.py` 的 rules `_recommend` 中，仅把 `search_tasks` 换为 `TaskBankProvider.generate(full_context)` 后提取 `.task`；保留原排序和历史排除。**运行 `& '.\.venv\Scripts\python.exe' -m unittest tests.test_candidate_provider tests.test_mvp_integration -v`，预期 PASS；`TASK_GENERATION_MODE=mock` 路径不得变成真实模型调用。
- [ ] **Step 5: `git add candidate_provider.py tests/test_candidate_provider.py`；`git add -p mvp_orchestrator.py`；核对 `git diff --cached` 后 `git commit -m "refactor: share candidate source boundary"`。**

### Task 3: 极简硬约束与排序

**Files:**
- Create: `quick_recommendation.py`
- Test: `tests/test_quick_recommendation.py`

**Interfaces:**
- Consumes: `RecommendationContext`、`CandidateTask`；`history_weights` 使用现有 `preference_weights()` 字典键 `category_boosts/group_boosts/group_penalties/preferred_duration_minutes`；`excluded_task_ids: set[str]`。
- Produces: `rank_quick(context: RecommendationContext, candidates: list[CandidateTask], history_weights: dict[str, Any] | None = None, excluded_task_ids: set[str] | None = None) -> list[dict[str, Any]]`，按序返回至多 10 个可 JSON 序列化任务：`id/title/category/duration_minutes/budget/outing/company/first_action/reason/feedback_group/ease_level/physical_load/social_pressure`。

- [ ] **Step 1: 写失败测试，显式包含硬约束、去重、低精力与无候选。**

```python
import unittest
from candidate_provider import RecommendationContext, CandidateTask
from quick_recommendation import rank_quick
from task_repository import Task

def candidate(id, duration=10, budget=0, outing="home", company="solo", ease=4, physical=1, action="现在站起来伸展一下", startup_cost=0):
    task = Task(id, id, "松弛疗愈", duration, budget, outing, company,
                feedback_group=id, ease_level=ease, physical_load=physical)
    return CandidateTask(task, action, "task_bank", True, startup_cost)

class RankQuickTest(unittest.TestCase):
    def test_rejects_unsafe_and_duplicate_candidates(self):
        ctx = RecommendationContext("quick", "sess", None, 15, "low")
        tasks = rank_quick(ctx, [candidate("ok"), candidate("ok"), candidate("paid", budget=2),
                                 candidate("out", outing="nearby"), candidate("long", duration=20),
                                 candidate("missing", action="")])
        self.assertEqual([task["id"] for task in tasks], ["ok"])

    def test_low_energy_prefers_easy_task_not_just_shortest(self):
        ctx = RecommendationContext("quick", "sess", None, 20, "low")
        tasks = rank_quick(ctx, [candidate("short_hard", 5, ease=1, physical=5),
                                 candidate("easy", 15, ease=5, physical=1)])
        self.assertEqual(tasks[0]["id"], "easy")

    def test_empty_pool_does_not_relax_constraints(self):
        ctx = RecommendationContext("quick", "sess", None, 5, "low")
        self.assertEqual(rank_quick(ctx, [candidate("too_long", duration=20)]), [])

    def test_same_energy_fit_prefers_lower_preparation_cost(self):
        ctx = RecommendationContext("quick", "sess", None, 20, "medium")
        tasks = rank_quick(ctx, [candidate("needs_setup", 5, startup_cost=2),
                                 candidate("instant", 15, startup_cost=0)])
        self.assertEqual(tasks[0]["id"], "instant")
```

- [ ] **Step 2: 运行 `& '.\.venv\Scripts\python.exe' -m unittest tests.test_quick_recommendation -v`，预期 RED。**
- [ ] **Step 3: 实现 `rank_quick`。**复用 Task 2 的 `is_quick_eligible`，不要新写一套会漂移的硬条件；人工目录已审核无预约/购物/特殊装备，未来其他来源必须有等价的立即开始声明并复验。排序优先能源适配与历史权重，其次准备阻力，再比分钟数和 ID；建议理由只用已知事实，不杜撰用户偏好。

```python
from candidate_provider import is_quick_eligible

def quick_sort_key(item, context, weights):
    task = item.task
    weights = weights or {}
    group_boost = weights.get("group_boosts", {}).get(task.feedback_group, 0.0)
    group_penalty = weights.get("group_penalties", {}).get(task.feedback_group, 0.0)
    category_boost = weights.get("category_boosts", {}).get(task.category, 0.0)
    target_load = {"low": 1, "medium": 2, "high": 3}[context.energy_level]
    energy_fit = (task.ease_level - abs(task.physical_load - target_load)
                  - (task.social_pressure if context.energy_level == "low" else 0))
    score = energy_fit + group_boost - group_penalty + category_boost
    return (-score, item.startup_cost, task.duration, task.id)

def to_quick_payload(item, context):
    task = item.task
    reason = ("适合现在的低精力状态，可在家独自开始。"
              if context.energy_level == "low"
              else "无需出门或花钱，现在就能开始。")
    return {"id": task.id, "title": task.title, "category": task.category,
            "duration_minutes": task.duration, "budget": task.budget,
            "outing": task.outing, "company": task.company,
            "first_action": item.first_action, "reason": reason,
            "feedback_group": task.feedback_group, "ease_level": task.ease_level,
            "physical_load": task.physical_load,
            "social_pressure": task.social_pressure}

def rank_quick(context, candidates, history_weights=None, excluded_task_ids=None):
    usable = {item.task.id: item for item in candidates
              if is_quick_eligible(context, item)
              and item.task.id not in (excluded_task_ids or set())}
    return [to_quick_payload(item, context) for item in sorted(
        usable.values(), key=lambda item: quick_sort_key(item, context, history_weights)
    )[:10]]
```

- [ ] **Step 4: 运行目标测试与 `& '.\.venv\Scripts\python.exe' -m unittest tests.test_recommendation_reasons tests.test_user_history_recommendation -v`，预期 PASS。**
- [ ] **Step 5: `git add quick_recommendation.py tests/test_quick_recommendation.py`；核对 `git diff --cached` 后 `git commit -m "feat: rank safe quick recommendations"`。**

### Task 4: 推荐轮次、轻反馈和共用偏好

**Files:**
- Create: `quick_recommendation_store.py`
- Modify: `user_history_service.py` 的 `preference_weights`、`excluded_groups`；新增 `excluded_task_ids(user_id: str | None) -> set[str]`
- Modify: `mvp_orchestrator.py` rules 推荐时合并共用的任务 ID 排除
- Test: `tests/test_quick_recommendation_store.py`、`tests/test_user_history_recommendation.py`

**Interfaces:**
- Consumes: Task 3 的有序推荐 `list[dict[str, Any]]`；现有 `UserHistoryService.preference_weights(user_id)`。
- Produces: `QuickRecommendationStore(database_url)`；`save_run(session_id, user_id, available_minutes, energy_level, tasks) -> str`、`latest_run(session_id) -> dict[str, Any] | None`（带本轮已保存反馈） 、`save_feedback(session_id, run_id, action, task_id) -> dict[str, Any]`；`UserHistoryService.excluded_task_ids(user_id)`。

- [ ] **Step 1: 写数据库失败测试；用独立测试数据库和每例新 session/user，不能删线上数据。**

```python
import os
import unittest
from fastapi.testclient import TestClient
from main import create_app
from quick_recommendation_store import QuickRecommendationStore

class QuickStoreTest(unittest.TestCase):
    def setUp(self):
        client = TestClient(create_app())
        self.session_id = client.post("/api/v1/sessions").json()["data"]["session_id"]
        self.user_id = client.post("/api/v1/users/anonymous", json={}).json()["data"]["user_id"]
        self.store = QuickRecommendationStore(os.environ["SESSION_DATABASE_URL"])

    def test_feedback_is_idempotent_and_run_bound(self):
        run_id = self.store.save_run(self.session_id, self.user_id, 15, "low",
                                     [{"id": "task_recovery_01", "title": "呼吸", "first_action": "坐稳"}])
        self.store.save_feedback(self.session_id, run_id, "liked", "task_recovery_01")
        self.store.save_feedback(self.session_id, run_id, "liked", "task_recovery_01")
        self.assertEqual(len(self.store.latest_run(self.session_id)["feedback"]), 1)
        with self.assertRaises(LookupError):
            self.store.save_feedback("other_session", run_id, "liked", "task_recovery_01")
        with self.assertRaises(LookupError):
            self.store.save_feedback(self.session_id, run_id, "liked", "not_in_run")

    def test_rest_is_neutral_and_creates_no_plan_action(self):
        run_id = self.store.save_run(self.session_id, self.user_id, 10, "low", [])
        self.store.save_feedback(self.session_id, run_id, "rest_selected", None)
        self.assertEqual(self.store.latest_run(self.session_id)["feedback"][0]["action"], "rest_selected")
```

- [ ] **Step 2: 用测试用 `SESSION_DATABASE_URL` 运行 `& '.\.venv\Scripts\python.exe' -m unittest tests.test_quick_recommendation_store -v`，预期 RED。**
- [ ] **Step 3: 在同一 PostgreSQL 增加 `quick_recommendation_runs`（`id/session_id/user_id/available_minutes/energy_level/tasks_json/created_at`）和 `quick_recommendation_feedback`（`run_id/task_id/action/created_at`）。**为 `run_id, task_id` 设置唯一约束，休息使用单独部分唯一索引；数据库事务中核对任务确属该轮、`session_id` 一致，用 UPSERT 保留最新喜欢/不喜欢。应用构造时必须先初始化这两张表，再让 `UserHistoryService` 查询它们；不要向 `plans`、`plan_items`、`user_task_history` 写极简事件。

```sql
CREATE UNIQUE INDEX IF NOT EXISTS quick_feedback_task_unique
  ON quick_recommendation_feedback(run_id, task_id) WHERE task_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS quick_feedback_rest_unique
  ON quick_recommendation_feedback(run_id) WHERE action = 'rest_selected';
```

- [ ] **Step 4: 把最新任务反馈汇入 `preference_weights`；两次及以上同组负面反馈才进 `excluded_groups`，单次不喜欢只经 `excluded_task_ids` 排除具体任务。**`latest_run` 返回已保存的本轮反馈，让刷新时能隐藏被否定的任务、恢复休息状态。完整模式既有完成数统计仍只读 `user_task_history.action='completed'`。新增测试：两次相同反馈只计一次、`rest_selected` 不降权、极简喜欢改变完整模式等分任务顺序、极简不喜欢排除任务但未满阈值不排整组。

```python
def test_one_quick_dislike_excludes_only_task(self):
    self.assertIn("task_recovery_01", self.history.excluded_task_ids(self.user_id))
    self.assertNotIn("recovery_group", self.history.excluded_groups(self.user_id))
```

- [ ] **Step 5: 运行 `& '.\.venv\Scripts\python.exe' -m unittest tests.test_quick_recommendation_store tests.test_user_history_recommendation tests.test_user_history_service -v`，预期 PASS。**确认只在测试库运行后，`git add quick_recommendation_store.py tests/test_quick_recommendation_store.py`，对已修改文件用 `git add -p user_history_service.py mvp_orchestrator.py tests/test_user_history_recommendation.py`；核对 `git diff --cached` 后 `git commit -m "feat: persist quick feedback and share learning"`。

### Task 5: 极简 API 与服务协调

**Files:**
- Create: `quick_recommendation_service.py`
- Modify: `main.py` 的 `create_app` 与 Pydantic 输入模型
- Test: `tests/test_quick_recommendation_api.py`

**Interfaces:**
- Consumes: Task 2 `CandidateProvider.generate`、Task 3 `rank_quick`、Task 4 `QuickRecommendationStore` 与 `UserHistoryService`。
- Produces: `QuickRecommendationService.generate(session_id, user_id, available_minutes, energy_level) -> dict[str, Any]`、`latest(session_id) -> dict[str, Any] | None`、`feedback(session_id, run_id, action, task_id) -> dict[str, Any]`；API 三个端点均用 `success(data)`。

- [ ] **Step 1: 写 API 失败测试，包含 Review Focus 1、2、3。**

```python
from fastapi.testclient import TestClient
from main import create_app

def test_quick_recommendation_contract():
    client = TestClient(create_app())
    session = client.post("/api/v1/sessions").json()["data"]["session_id"]
    user = client.post("/api/v1/users/anonymous", json={}).json()["data"]["user_id"]
    path = f"/api/v1/sessions/{session}/quick-recommendations"
    assert client.post(path, json={"available_minutes": 0, "energy_level": "low", "user_id": user}).status_code == 422
    assert client.post(path, json={"available_minutes": -1, "energy_level": "low", "user_id": user}).status_code == 422
    assert client.post(path, json={"available_minutes": 999999, "energy_level": "low", "user_id": user}).status_code == 422
    assert client.post(path, json={"available_minutes": 999999, "energy_level": "wrong", "user_id": user}).status_code == 422
    response = client.post(path, json={"available_minutes": 15, "energy_level": "low", "user_id": user})
    assert response.status_code == 200
    data = response.json()["data"]
    assert len([data["primary_task"], *data["alternatives"]]) <= 10
    assert client.get(path + "/latest").json()["data"]["run_id"] == data["run_id"]
    assert client.post(path + f"/{data['run_id']}/feedback", json={"action": "liked", "task_id": "not_in_run"}).status_code in {404, 409}
```

- [ ] **Step 2: 使用测试数据库运行 `& '.\.venv\Scripts\python.exe' -m unittest tests.test_quick_recommendation_api -v`，预期 404 或导入失败。**测试文件按现有 `unittest.TestCase` 包装上面的测试体。
- [ ] **Step 3: 实现服务和路由。**Pydantic `available_minutes: int = Field(ge=1, le=480)`，`energy_level: Literal["low", "medium", "high"]`，`user_id: str`；服务从 `SessionService.restore` 核对会话存在，读取共用权重/排除，调用来源与 `rank_quick`，保存轮次。返回 `{run_id, primary_task, alternatives, constraints, feedback}`；无候选时 `primary_task=None, alternatives=[]`。`latest` 无记录返回 `{run_id: None, primary_task: None, alternatives: [], constraints: None, feedback: []}`；有记录时根据已保存反馈隐藏 `disliked` 项，必要时提升下一项。反馈核对轮次/任务；`rest_selected` 不带 `task_id`。新路由只能在正确服务配置后启用，不创建计划。

```python
class QuickInput(BaseModel):
    available_minutes: int = Field(ge=1, le=480)
    energy_level: Literal["low", "medium", "high"]
    user_id: str = Field(min_length=1)

class QuickFeedbackInput(BaseModel):
    action: Literal["liked", "disliked", "rest_selected"]
    task_id: str | None = None
```

- [ ] **Step 4: 测试 5 分钟无候选的空状态、跨 session 反馈拒绝、重复喜欢幂等、直接休息中性、无问卷仍可生成；并运行 `& '.\.venv\Scripts\python.exe' -m unittest tests.test_quick_recommendation_api tests.test_api_flow tests.test_mock_api_flow -v`。**预期 PASS。
- [ ] **Step 5: `git add quick_recommendation_service.py tests/test_quick_recommendation_api.py`；`git add -p main.py`；核对 `git diff --cached` 后 `git commit -m "feat: expose quick recommendation API"`。**

### Task 6: 双模式前端与恢复

**Files:**
- Modify: `frontend/api.js`、`frontend/flow.js`、`frontend/app.js`、`frontend/styles.css`、`frontend/index.html`、`frontend/service-worker.js`
- Create: `tests/frontend-quick.test.js`
- Test: `tests/frontend-flow.test.js`、`tests/frontend-pwa.test.js`、`tests/frontend-visual.test.js`

**Interfaces:**
- Consumes: Task 5 的三个 `success(data)` 端点；沿用 `frontend/api.js` 的 `currentUserId()`、`ensureAnonymousUser()`、`createSession()`、`restoreSession()`。
- Produces: API client `createQuickSession()`、`getQuickSessionId()`、`createQuickRecommendations(input, sessionId)`、`getLatestQuickRecommendations(sessionId)`、`sendQuickFeedback(runId, input, sessionId)`；前端状态 `productMode: "quick" | "full"` 与独立 `quickSessionId/quickDraft/quickRun`。

- [ ] **Step 1: 在 `frontend/flow.js` 写纯函数测试并先见 RED。**

```javascript
const assert = require('node:assert/strict');
const test = require('node:test');
const { selectQuickTask, afterQuickDislike } = require('../frontend/flow.js');

test('quick result starts with one task and never cycles to disliked task', () => {
  const run = { primary_task: { id: 'a' }, alternatives: [{ id: 'b' }, { id: 'c' }] };
  assert.equal(selectQuickTask(run, 'b').primary_task.id, 'b');
  const next = afterQuickDislike(run, 'a');
  assert.equal(next.primary_task.id, 'b');
  assert.deepEqual(next.alternatives.map(x => x.id), ['c']);
});

test('last dislike yields empty task and retains rest choice', () => {
  const next = afterQuickDislike({ primary_task: { id: 'a' }, alternatives: [] }, 'a');
  assert.equal(next.primary_task, null);
  assert.deepEqual(next.alternatives, []);
});
```

- [ ] **Step 2: 运行 `node --test tests/frontend-quick.test.js`，预期导出函数缺失，RED。**
- [ ] **Step 3: 在 `frontend/api.js` 添加新会话方法和三个客户端方法，URL 与 Task 5 完全一致；在 `frontend/flow.js` 加纯状态转换。**现有 `createSession()` 写完整模式的 `STORAGE_KEY`，极简必须让 `createQuickSession()` 直接 POST `/api/v1/sessions` 并写独立 `QUICK_STORAGE_KEY`，不能先调用 `createSession()` 覆盖完整模式 ID。新 key 还保存极简草稿、当前产品模式和用户在候选列表中选中的 `selected_task_id`；恢复时从后端 `latest` 获取最近推荐及反馈状态，再仅对仍合格的 ID 恢复选中，不使用本地缓存伪造成功。只把用户已明确输入的时长/精力作为切换默认值。

```javascript
function selectQuickTask(run, taskId) {
  const tasks = [run.primary_task, ...(run.alternatives || [])].filter(Boolean);
  const selected = tasks.find(task => task.id === taskId);
  if (!selected) return run;
  return { ...run, primary_task: selected,
    alternatives: tasks.filter(task => task.id !== taskId) };
}

function afterQuickDislike(run, taskId) {
  const remaining = [run.primary_task, ...(run.alternatives || [])]
    .filter(task => task && task.id !== taskId);
  return { ...run, primary_task: remaining[0] || null, alternatives: remaining.slice(1) };
}
```

- [ ] **Step 4: 在 `frontend/app.js` 首页加极简/完整模式选择，极简只显示两输入、一主任务、理由/第一步/时间、“查看更多”、喜欢/不喜欢和同级“直接休息”；不复用完整模式的 `renderTaskCard` 执行按钮。**“不喜欢”先等待保存成功再移除当前任务；失败保留页面并展示重试。无候选仍显示休息和修改时长；切换完整模式保留其既有问卷/计划状态。`styles.css` 遵循既有像素尺寸/颜色，窄屏无溢出；更新 `index.html`/service-worker 的静态版本以避免旧 JS 混用。
- [ ] **Step 5: 运行 `node --test tests/frontend-quick.test.js tests/frontend-flow.test.js tests/frontend-pwa.test.js tests/frontend-visual.test.js`，预期 PASS；补浏览器测试或人工录屏验证 375px/768px/desktop、刷新恢复、弱网重试、模式切换与完整模式未回归。**
- [ ] **Step 6: `git add tests/frontend-quick.test.js`；对已有改动的前端文件逐个 `git add -p`，核对 `git diff --cached` 后 `git commit -m "feat: add quick mode experience"`。**

### Task 7: 全链路验收、文档与发布门槛

**Files:**
- Create: `docs/quick-mode-test.md`
- Modify only if required by failing tests: corresponding owner files from Tasks 1-6
- Test: `tests/test_quick_recommendation_api.py`、`tests/test_mvp_integration.py`、`tests/test_user_history_api.py`、`tests/frontend-quick.test.js`

**Interfaces:**
- Consumes: 前六任务已交付的数据库/API/前端；不引入新业务接口。
- Produces: 可重复的本地手工验收清单、测试结果与发布记录。

- [ ] **Step 1: 先写一个贯通失败测试。**同一匿名用户开极简 session，15 分钟低精力拿首选，喜欢它；另开完整 session，完成原问卷并生成计划；断言完整模式可用且 `user_task_history` 中没有因为喜欢而新增 `completed` 行。再用同一用户点“不喜欢”并检查下一轮不出现该任务。测试只用独立测试库及新 ID。

```python
def test_quick_feedback_never_counts_as_completion(self):
    quick = self.client.post(self.quick_path, json=self.quick_input).json()["data"]
    task_id = quick["primary_task"]["id"]
    response = self.client.post(
        f"{self.quick_path}/{quick['run_id']}/feedback",
        json={"action": "liked", "task_id": task_id},
    )
    self.assertEqual(response.status_code, 200)
    summary = self.client.get(f"/api/v1/users/{self.user_id}/history/summary").json()["data"]
    self.assertEqual(summary["completed_count"], 0)
```

- [ ] **Step 2: 运行该测试，确保在补全前它会真实失败；再补齐测试所需的跨模式场景。**避免只检查 200，须断言任务变化、历史计数及完整模式核心输出。
- [ ] **Step 3: 在 `docs/quick-mode-test.md` 写用户能照做的验收步骤与期望结果。**至少包含：创建匿名用户/极简 5、15、30 分钟；低精力；展开/收起；喜欢/不喜欢；休息；刷新；切换完整模式；无候选；断网重试；手机窄屏；现有完整流程。记录临时测试 session ID 而不写数据库密码。
- [ ] **Step 4: 执行 `& '.\.venv\Scripts\python.exe' -m unittest discover -s tests -p 'test_*.py'` 与 `node --test tests`。**另用真实测试数据库执行三条新 API 的 smoke 请求；检查 `git diff --check`、`git status --short`，不得把用户原有改动当作本功能清理。
- [ ] **Step 5: 做静态与手工复核。**确认本期没有真实 AI 网络调用/密钥、极简无开始/完成、来源不误标 AI、休息中性、实际手机按钮可触达。若测试失败，回到对应任务做红绿循环再复测；不要带失败部署。
- [ ] **Step 6: `git add docs/quick-mode-test.md` 及本任务新增测试；`git commit -m "test: verify quick and full mode workflow"`。**只有获得用户对实施及发布方式的确认后，才在正式仓库按既有主分支流程推送 GitHub 并观察 Vercel 自动部署；部署后分别测试手机与桌面公开网址。不要把本地数据库 URL 或密码写进 commit。

## Self-Review / Handoff

- 设计中的准入、来源、排序、轻反馈、跨模式学习、三个 API、前端两模式、恢复、回归与弱网/移动验收分别归属 Tasks 1-7；真实 AI 接入明确留到后续设计。
- 反馈 REST 与计划执行语义隔离；`first_action` 不改变完整模式现有 `Task` 数据结构，减少 700 条任务数据迁移风险。
- Task 4 的测试辅助方法、Task 7 的贯通测试方法须在对应测试类中实现；实施者不得只复制片段而跳过数据库隔离与 cleanup。
- 本文件是计划，不代表功能已写入、提交到 `D:\yxy1.0`、推送 GitHub 或部署 Vercel。
