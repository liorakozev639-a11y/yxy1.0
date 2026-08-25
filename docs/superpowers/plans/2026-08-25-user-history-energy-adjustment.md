# User History Energy Adjustment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build user-level history learning, task-start energy confirmation, easier task replacement, and history-aware recommendation for the MVP.

**Architecture:** Add a focused `user_history_service.py` that owns anonymous users, long-term task history, and history-derived ranking weights. Keep existing session-scoped `RecommendationMemory` unchanged; feed user history into recommendation and plan replacement as an additional ranking and exclusion signal. Frontend stores an anonymous `user_id`, asks for energy before starting tasks, and calls a new easier-replacement endpoint when energy is low.

**Tech Stack:** Python 3.12, FastAPI, psycopg 3, PostgreSQL, browser-native HTML/CSS/JS frontend, Node built-in test runner, Python `unittest`.

**Spec:** `docs/superpowers/specs/2026-08-25-user-history-energy-adjustment-design.md`

## Global Constraints

- Do not add login, registration, password handling, OAuth, or third-party auth in this phase.
- Do not display recommendation explanations in the formal frontend.
- Do not introduce a large language model call, external map API, merchant API, activity API, MQ, or async worker.
- Keep PostgreSQL as the only backend persistence layer.
- Keep session-scoped negative memory and user-level history memory separate.
- Keep existing no-token MVP behavior unchanged.
- Keep current pixel frontend as the formal business frontend.
- Continue to avoid `backup-before-github-20260814-1/`; never stage or modify it.
- Work on `main` only; do not create a new git worktree.
- Use `.venv-debug\Scripts\python.exe` for Python verification unless the local environment is repaired.

---

## File Structure

- Create `user_history_service.py`: owns `user_profiles`, `user_task_history`, anonymous user creation, action recording, summary, ranking weights, and history group exclusions.
- Modify `main.py`: instantiate `UserHistoryService`; expose anonymous user, history summary, execution prepare, and easier replacement endpoints; pass user history service into orchestrator, plan, and execution services.
- Modify `mvp_orchestrator.py`: accept optional `user_id` in plan generation and call history-aware recommendation weights.
- Modify `recommendation_module.py`: add optional `history_weights` and `history_excluded_groups` inputs to ranking while keeping existing callers working.
- Modify `plan_module.py`: add `replace_item_easier(...)` and reuse existing versioning, conflict checks, `replacement_history`, and session memory exclusions.
- Modify `execution_service.py`: record user history on `complete` and `skip` actions when a `user_id` is provided or can be resolved.
- Modify `frontend/api.js`: store and send anonymous `user_id`; add API wrappers for user creation, history summary, execution prepare, and easier replacement.
- Modify `frontend/app.js`: create anonymous user on boot; show energy confirmation before starting; route low energy to easier replacement; keep manual time editing unchanged.
- Modify `README.md` and `docs/api.md`: document second-stage behavior and endpoints.
- Add tests under `tests/`: service-level, API-level, recommendation-level, and frontend flow tests.

---

### Task 1: User History Service

**Files:**
- Create: `user_history_service.py`
- Test: `tests/test_user_history_service.py`
- Modify: `requirements.txt` only if an existing import is unavailable; no new dependency is expected.

**Interfaces:**
- Produces: `class UserHistoryService`
- Produces: `UserHistoryService.ensure_user(user_id: str | None = None) -> dict[str, Any]`
- Produces: `UserHistoryService.record_action(user_id: str, session_id: str, plan_id: str, item_id: str, action: Literal["completed", "skipped", "replaced_from", "replaced_to"], occurred_at: datetime | None = None) -> dict[str, Any]`
- Produces: `UserHistoryService.summary(user_id: str) -> dict[str, Any]`
- Produces: `UserHistoryService.preference_weights(user_id: str | None) -> dict[str, Any]`
- Produces: `UserHistoryService.excluded_groups(user_id: str | None) -> set[str]`
- Consumes: existing PostgreSQL tables `sessions`, `plans`, `plan_items`
- Consumes: `TaskRepository().public_tasks` to resolve `feedback_group`, `duration`, `outing`, and `company`

- [ ] **Step 1: Write failing service tests**

Create `tests/test_user_history_service.py` with these tests:

```python
from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone

from mvp_orchestrator import GeneratePlanRequest, MVPOrchestrator, PostgreSQLProfileRepository, PostgreSQLPlanRepository
from profile_module import ProfileBuilder
from questionnaire_module import QuestionnaireRepository, QuestionnaireService, DemoSessionStore
from session_module import PostgresSessionRepository, SessionService
from task_repository import TaskRepository
from user_history_service import UserHistoryService


class UserHistoryServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        database_url = os.environ["SESSION_DATABASE_URL"]
        self.sessions = SessionService(PostgresSessionRepository(database_url))
        self.history = UserHistoryService(database_url)
        self.questionnaires = QuestionnaireService(DemoSessionStore(), QuestionnaireRepository())
        self.orchestrator = MVPOrchestrator(
            sessions=self.sessions,
            questionnaires=self.questionnaires,
            profiles=PostgreSQLProfileRepository(database_url),
            plans=PostgreSQLPlanRepository(database_url),
            profile_builder=ProfileBuilder(),
            tasks=TaskRepository(),
        )
        created = self.sessions.create()
        self.session_id = created["session_id"]
        self.sessions.save_preferences(
            self.session_id,
            {
                "interests": ["活力充电", "松弛疗愈"],
                "budget": "medium",
                "outing": "nearby",
                "company": "both",
                "duration": "half",
                "pace": "balanced",
            },
        )
        plan_result = self.orchestrator.generate_plan(
            self.session_id,
            GeneratePlanRequest(
                free_start=datetime.now(timezone.utc),
                free_end=datetime.now(timezone.utc) + timedelta(hours=4),
                density="balanced",
            ),
        )
        self.plan = plan_result["plan"]
        self.item = next(item for item in self.plan["items"] if item["kind"] == "task")

    def test_ensure_user_creates_and_restores_anonymous_user(self) -> None:
        created = self.history.ensure_user()
        restored = self.history.ensure_user(created["user_id"])
        self.assertTrue(created["created"])
        self.assertFalse(restored["created"])
        self.assertEqual(restored["user_id"], created["user_id"])

    def test_record_completed_action_updates_summary_and_weights(self) -> None:
        user = self.history.ensure_user()
        record = self.history.record_action(
            user["user_id"],
            self.session_id,
            self.plan["plan_id"],
            self.item["id"],
            "completed",
        )
        summary = self.history.summary(user["user_id"])
        weights = self.history.preference_weights(user["user_id"])
        self.assertEqual(record["action"], "completed")
        self.assertEqual(summary["completed_count"], 1)
        self.assertIn(self.item["category"], summary["top_completed_categories"])
        self.assertGreater(weights["category_boosts"][self.item["category"]], 0)

    def test_skipped_action_adds_avoided_group(self) -> None:
        user = self.history.ensure_user()
        self.history.record_action(
            user["user_id"],
            self.session_id,
            self.plan["plan_id"],
            self.item["id"],
            "skipped",
        )
        groups = self.history.excluded_groups(user["user_id"])
        self.assertEqual(len(groups), 1)
        self.assertEqual(self.history.summary(user["user_id"])["skipped_count"], 1)
```

- [ ] **Step 2: Run service tests to verify they fail**

Run:

```powershell
$env:SESSION_DATABASE_URL="postgresql://postgres:你的数据库密码@127.0.0.1:5433/free_time_agent"
& ".\.venv-debug\Scripts\python.exe" -m unittest tests.test_user_history_service -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'user_history_service'`.

- [ ] **Step 3: Implement `user_history_service.py`**

Create `user_history_service.py` with these concrete elements:

```python
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

import psycopg
from fastapi import HTTPException
from psycopg.rows import dict_row

from task_repository import TaskRepository

HistoryAction = Literal["completed", "skipped", "replaced_from", "replaced_to"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class UserHistoryService:
    def __init__(self, database_url: str, tasks: TaskRepository | None = None) -> None:
        if not database_url:
            raise ValueError("database_url 不能为空")
        self.database_url = database_url
        self.tasks = tasks or TaskRepository()
        self.init_schema()
```

Implement:

- `_connect()` using `psycopg.connect(self.database_url)`.
- `init_schema()` using the two tables and two indexes from the spec.
- `ensure_user(user_id=None)`:
  - Generate `user_<uuid>` when `user_id` is missing.
  - Insert into `user_profiles`.
  - On conflict update `updated_at`.
  - Return `{"user_id": row["id"], "created": created_bool}`.
- `_plan_item_context(connection, session_id, plan_id, item_id)`:
  - Join `plans` and `plan_items`.
  - Check ownership by `session_id`.
  - Return `task_id`, `category`, `duration_minutes`, `session_id`, `plan_id`, `item_id`.
  - Raise 404 when no row.
- `_feedback_group_for(task_id)`:
  - Find matching task in `self.tasks.public_tasks`.
  - Return `task.feedback_group`.
  - Return `f"custom:{task_id}"` for custom tasks.
- `record_action(...)`:
  - Validate `action`.
  - Ensure user exists.
  - Insert one history row with resolved task context.
  - Return row payload.
- `summary(user_id)`:
  - Return counts for completed, skipped, replaced.
  - `replaced_count` counts `replaced_from`.
  - `top_completed_categories` is top 3 categories by completed count.
  - `avoided_group_count` counts distinct feedback groups where action is `skipped` or `replaced_from`.
- `preference_weights(user_id)`:
  - Return:
    ```python
    {
        "category_boosts": {"松弛疗愈": 0.2},
        "group_boosts": {"stretch_light": 0.35},
        "group_penalties": {"crowded_social": 0.5},
        "preferred_duration_minutes": 45,
    }
    ```
  - Completed category boost: `min(0.3, count * 0.05)`.
  - Completed group boost: `min(0.4, count * 0.08)`.
  - Skipped/replaced_from group penalty: `min(0.7, count * 0.15)`.
  - Preferred duration is rounded average duration of completed rows; return `None` when no completed rows.
- `excluded_groups(user_id)`:
  - Return groups with at least two rows where action is `skipped` or `replaced_from`.
  - Return empty set when `user_id` is missing.

- [ ] **Step 4: Run service tests to verify they pass**

Run:

```powershell
$env:SESSION_DATABASE_URL="postgresql://postgres:你的数据库密码@127.0.0.1:5433/free_time_agent"
& ".\.venv-debug\Scripts\python.exe" -m unittest tests.test_user_history_service -v
```

Expected: 3 tests pass.

- [ ] **Step 5: Commit Task 1**

Run:

```powershell
git add user_history_service.py tests/test_user_history_service.py
git commit -m "feat: add user history service"
```

---

### Task 2: History-Aware Recommendation and Action Recording

**Files:**
- Modify: `recommendation_module.py`
- Modify: `mvp_orchestrator.py`
- Modify: `execution_service.py`
- Modify: `plan_module.py`
- Modify: `main.py`
- Test: `tests/test_user_history_recommendation.py`
- Test: `tests/test_user_history_api.py`

**Interfaces:**
- Consumes: `UserHistoryService.preference_weights(user_id)`
- Consumes: `UserHistoryService.excluded_groups(user_id)`
- Produces: `recommend_tasks(..., history_weights: dict[str, Any] | None = None, history_excluded_groups: set[str] | None = None)`
- Produces: `MVPOrchestrator.generate_plan(session_id, request, user_id: str | None = None)`
- Produces: `ExecutionService.execute(..., user_id: str | None = None)`
- Produces: `PlanManagementService.replace_item_easier(session_id, plan_id, item_id, expected_version, user_id=None)`

- [ ] **Step 1: Write failing recommendation and API tests**

Create `tests/test_user_history_recommendation.py`:

```python
import unittest

from recommendation_module import recommend_tasks
from task_repository import Task


class HistoryAwareRecommendationTest(unittest.TestCase):
    def test_completed_group_moves_task_ahead_of_equal_candidate(self) -> None:
        tasks = [
            Task("task_a", "普通散步", "活力充电", 30, 0, "nearby", "solo", feedback_group="walk_plain"),
            Task("task_b", "熟悉路线慢走", "活力充电", 30, 0, "nearby", "solo", feedback_group="walk_favorite"),
        ]
        profile = {
            "selected_categories": ["活力充电"],
            "scores": {"活力充电": 0.8},
            "constraints": {"budget": "low", "outing": "nearby", "company": "solo"},
        }
        result = recommend_tasks(
            profile,
            tasks,
            limit=2,
            history_weights={"group_boosts": {"walk_favorite": 0.4}},
        )
        self.assertEqual(result["tasks"][0]["task_id"], "task_b")

    def test_history_excluded_group_is_not_returned(self) -> None:
        tasks = [
            Task("task_a", "普通散步", "活力充电", 30, 0, "nearby", "solo", feedback_group="walk_plain"),
            Task("task_b", "拥挤广场活动", "活力充电", 30, 0, "nearby", "group", feedback_group="crowded"),
        ]
        profile = {
            "selected_categories": ["活力充电"],
            "scores": {"活力充电": 0.8},
            "constraints": {"budget": "low", "outing": "nearby", "company": "both"},
        }
        result = recommend_tasks(profile, tasks, limit=2, history_excluded_groups={"crowded"})
        self.assertTrue(all(task["feedback_group"] != "crowded" for task in result["tasks"]))
```

Create `tests/test_user_history_api.py`:

```python
from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from main import create_app


class UserHistoryApiTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["SESSION_DATABASE_URL"] = os.environ["SESSION_DATABASE_URL"]
        self.client = TestClient(create_app())

    def _create_plan(self) -> tuple[str, str, str]:
        session = self.client.post("/api/v1/sessions").json()["data"]
        session_id = session["session_id"]
        self.client.put(
            f"/api/v1/sessions/{session_id}/preferences",
            json={
                "interests": ["活力充电", "松弛疗愈"],
                "budget": "medium",
                "outing": "nearby",
                "company": "both",
                "duration": "half",
                "pace": "balanced",
            },
        )
        self.client.post(f"/api/v1/sessions/{session_id}/questionnaire/start", json={"mode": "quick"})
        progress = self.client.get(f"/api/v1/sessions/{session_id}/questionnaire/progress").json()["data"]
        for question in progress["questions"]:
            self.client.patch(
                f"/api/v1/sessions/{session_id}/questionnaire/answers/{question['id']}",
                json={"value": 3},
            )
        self.client.post(f"/api/v1/sessions/{session_id}/questionnaire/submit")
        plan = self.client.post(
            f"/api/v1/sessions/{session_id}/plan/generate",
            json={
                "free_start": datetime.now(timezone.utc).isoformat(),
                "free_end": (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
                "density": "balanced",
            },
        ).json()["data"]["plan"]
        item = next(entry for entry in plan["items"] if entry["kind"] == "task")
        return session_id, plan["plan_id"], item["id"]

    def test_anonymous_user_and_completed_action_update_history_summary(self) -> None:
        user = self.client.post("/api/v1/users/anonymous", json={}).json()["data"]
        _, plan_id, item_id = self._create_plan()
        self.client.post(
            f"/api/v1/plans/{plan_id}/items/{item_id}/execution/start",
            json={"user_id": user["user_id"]},
        )
        self.client.post(
            f"/api/v1/plans/{plan_id}/items/{item_id}/execution/complete",
            json={"user_id": user["user_id"]},
        )
        summary = self.client.get(f"/api/v1/users/{user['user_id']}/history/summary").json()["data"]
        self.assertEqual(summary["completed_count"], 1)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
$env:SESSION_DATABASE_URL="postgresql://postgres:你的数据库密码@127.0.0.1:5433/free_time_agent"
& ".\.venv-debug\Scripts\python.exe" -m unittest tests.test_user_history_recommendation tests.test_user_history_api -v
```

Expected: FAIL because recommendation does not accept history inputs and API routes do not exist.

- [ ] **Step 3: Modify `recommendation_module.py`**

Change `recommend_tasks` signature to:

```python
def recommend_tasks(
    profile: dict[str, Any],
    candidates: list[Task],
    limit: int = 10,
    excluded_feedback_groups: set[str] | None = None,
    history_weights: dict[str, Any] | None = None,
    history_excluded_groups: set[str] | None = None,
) -> dict[str, Any]:
```

Inside the candidate filter:

```python
excluded = (excluded_feedback_groups or set()) | (history_excluded_groups or set())
```

Add helper:

```python
def history_score(task: Task, history_weights: dict[str, Any] | None) -> float:
    if not history_weights:
        return 0.0
    score = 0.0
    score += history_weights.get("category_boosts", {}).get(task.category, 0)
    score += history_weights.get("group_boosts", {}).get(task.feedback_group, 0)
    score -= history_weights.get("group_penalties", {}).get(task.feedback_group, 0)
    preferred = history_weights.get("preferred_duration_minutes")
    if preferred:
        distance = abs(task.duration - preferred)
        score += max(0, 0.12 - min(distance, 60) / 500)
    return round(score, 4)
```

Add `-history_score(task, history_weights)` into the existing sort key before duration and budget, so higher history score ranks earlier.

- [ ] **Step 4: Modify `mvp_orchestrator.py`**

Add optional constructor field:

```python
user_history: Any | None = None
```

Change `generate_plan` signature to:

```python
def generate_plan(
    self,
    session_id: str,
    request: GeneratePlanRequest,
    user_id: str | None = None,
) -> dict[str, Any]:
```

Before calling `recommend_tasks`, compute:

```python
history_weights = self.user_history.preference_weights(user_id) if self.user_history else None
history_excluded_groups = self.user_history.excluded_groups(user_id) if self.user_history else set()
```

Pass both values into `recommend_tasks`.

- [ ] **Step 5: Modify `execution_service.py`**

Change `execute` signature:

```python
def execute(
    self,
    session_id: str,
    plan_id: str,
    item_id: str,
    action: str,
    now: datetime | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
```

Add constructor field:

```python
user_history: Any | None = None
```

After successful state update:

```python
if self.user_history is not None and user_id and action in {"complete", "skip"}:
    self.user_history.record_action(
        user_id,
        session_id,
        plan_id,
        item_id,
        "completed" if action == "complete" else "skipped",
    )
```

- [ ] **Step 6: Modify `plan_module.py`**

Add optional constructor field `user_history: Any | None = None`.

In `replace_item`, after `current = self._find_item(...)`, record `replaced_from` and `replaced_to` when `user_id` is provided by a new optional parameter:

```python
def replace_item(
    self,
    session_id: str,
    plan_id: str,
    item_id: str,
    expected_version: int,
    replacement_task_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
```

Add `replace_item_easier(...)` with the same shape but no `replacement_task_id`. It should call a new selector that sorts available candidates by:

```python
(task.duration, task.budget, outing_rank[task.outing], company_rank[task.company], task.id)
```

Use:

```python
outing_rank = {"home": 0, "nearby": 1, "city": 2}
company_rank = {"solo": 0, "both": 1, "group": 2}
```

Use existing `used_ids`, `replacement_history`, session memory exclusions, and `self.user_history.excluded_groups(user_id)` in the exclusion set.

- [ ] **Step 7: Modify `main.py`**

Add Pydantic inputs:

```python
class AnonymousUserInput(BaseModel):
    user_id: Optional[str] = None


class ExecutionInput(BaseModel):
    user_id: Optional[str] = None


class GeneratePlanInput(BaseModel):
    free_start: datetime
    free_end: datetime
    density: str = Field(pattern="^(light|balanced|full)$")
    user_id: Optional[str] = None


class ExecutionPrepareInput(BaseModel):
    user_id: Optional[str] = None
    energy: Literal["high", "medium", "low"]
```

Wire `UserHistoryService(database_url, TaskRepository())` into `build_services` or `create_app`, pass it into orchestrator, plan, and execution services.

Add routes:

```python
@app.post("/api/v1/users/anonymous")
def create_anonymous_user(body: AnonymousUserInput) -> dict[str, Any]:
    return success(user_history_service.ensure_user(body.user_id))


@app.get("/api/v1/users/{user_id}/history/summary")
def get_user_history_summary(user_id: str) -> dict[str, Any]:
    return success(user_history_service.summary(user_id))


@app.post("/api/v1/plans/{plan_id}/items/{item_id}/execution/prepare")
def prepare_execution(plan_id: str, item_id: str, body: ExecutionPrepareInput) -> dict[str, Any]:
    return success({
        "item_id": item_id,
        "energy": body.energy,
        "recommended_action": "replace_easier" if body.energy == "low" else "start",
        "can_start": body.energy in {"high", "medium"},
    })


@app.post("/api/v1/plans/{plan_id}/items/{item_id}/replace-easier")
def replace_plan_item_easier(plan_id: str, item_id: str, body: PlanItemMutationInput) -> dict[str, Any]:
    manager = require_plan_service()
    session_id = _session_id_from_plan(manager, plan_id)
    return success(manager.replace_item_easier(session_id, plan_id, item_id, body.expected_version, body.user_id))
```

If `PlanItemMutationInput` does not include `user_id`, add `user_id: Optional[str] = None`.

- [ ] **Step 8: Run tests to verify Task 2 passes**

Run:

```powershell
$env:SESSION_DATABASE_URL="postgresql://postgres:你的数据库密码@127.0.0.1:5433/free_time_agent"
& ".\.venv-debug\Scripts\python.exe" -m unittest tests.test_user_history_service tests.test_user_history_recommendation tests.test_user_history_api -v
```

Expected: all tests pass.

- [ ] **Step 9: Commit Task 2**

Run:

```powershell
git add recommendation_module.py mvp_orchestrator.py execution_service.py plan_module.py main.py tests/test_user_history_recommendation.py tests/test_user_history_api.py
git commit -m "feat: apply user history to recommendations"
```

---

### Task 3: Frontend Anonymous User and Energy Confirmation

**Files:**
- Modify: `frontend/api.js`
- Modify: `frontend/app.js`
- Modify: `frontend/styles.css`
- Test: `tests/frontend-api.test.js`
- Test: `tests/frontend-execution.test.js`

**Interfaces:**
- Consumes: `POST /api/v1/users/anonymous`
- Consumes: `POST /api/v1/plans/{plan_id}/items/{item_id}/execution/prepare`
- Consumes: `POST /api/v1/plans/{plan_id}/items/{item_id}/replace-easier`
- Produces: localStorage key `free_time_agent_user_id`
- Produces: `api.ensureAnonymousUser()`
- Produces: `api.prepareExecution(planId, itemId, input)`
- Produces: `api.replacePlanItemEasier(planId, itemId, input)`

- [ ] **Step 1: Write failing frontend API tests**

Update `tests/frontend-api.test.js` with:

```javascript
test('api creates and persists anonymous user id', async () => {
  const calls = [];
  const storage = new Map();
  const api = createApi({
    fetch: async (url, options) => {
      calls.push({ url, options });
      return jsonResponse({ data: { user_id: 'user_001', created: true }, error: null });
    },
    storage: {
      getItem: (key) => storage.get(key) || null,
      setItem: (key, value) => storage.set(key, value),
      removeItem: (key) => storage.delete(key),
    },
  });
  const user = await api.ensureAnonymousUser();
  assert.equal(user.user_id, 'user_001');
  assert.equal(storage.get('free_time_agent_user_id'), 'user_001');
  assert.equal(calls[0].url, 'http://127.0.0.1:8000/api/v1/users/anonymous');
});

test('api prepares execution and replaces with easier task', async () => {
  const calls = [];
  const api = createApi({
    fetch: async (url, options) => {
      calls.push({ url, options });
      return jsonResponse({ data: { ok: true }, error: null });
    },
  });
  await api.prepareExecution('plan_1', 'item_1', { energy: 'low', user_id: 'user_1' });
  await api.replacePlanItemEasier('plan_1', 'item_1', { expected_version: 2, user_id: 'user_1' });
  assert.equal(calls[0].url, 'http://127.0.0.1:8000/api/v1/plans/plan_1/items/item_1/execution/prepare');
  assert.equal(calls[1].url, 'http://127.0.0.1:8000/api/v1/plans/plan_1/items/item_1/replace-easier');
});
```

- [ ] **Step 2: Run frontend API tests to verify they fail**

Run:

```powershell
node --test tests/frontend-api.test.js
```

Expected: FAIL because new API wrappers are missing.

- [ ] **Step 3: Modify `frontend/api.js`**

Add storage key:

```javascript
const USER_STORAGE_KEY = 'free_time_agent_user_id';
```

Add:

```javascript
async function ensureAnonymousUser() {
  const existing = storage.getItem(USER_STORAGE_KEY);
  const data = await request('/api/v1/users/anonymous', {
    method: 'POST',
    body: JSON.stringify(existing ? { user_id: existing } : {}),
  });
  storage.setItem(USER_STORAGE_KEY, data.user_id);
  return data;
}

function currentUserId() {
  return storage.getItem(USER_STORAGE_KEY);
}

function prepareExecution(planId, itemId, input) {
  return request(`/api/v1/plans/${planId}/items/${itemId}/execution/prepare`, {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

function replacePlanItemEasier(planId, itemId, input) {
  return request(`/api/v1/plans/${planId}/items/${itemId}/replace-easier`, {
    method: 'POST',
    body: JSON.stringify(input),
  });
}
```

Export the four functions.

- [ ] **Step 4: Modify `frontend/app.js`**

Add state fields:

```javascript
userId: null,
energyItemId: null,
energyChoice: null,
```

During `init()`:

```javascript
const user = await api.ensureAnonymousUser();
state.userId = user.user_id;
```

When generating a plan, include:

```javascript
user_id: state.userId,
```

Change `start-execution` action:

- Do not call `api.startExecution` immediately.
- Set `state.energyItemId = itemId`.
- Render a compact energy panel on that task card.

Add handlers:

```javascript
if (action === 'choose-energy') {
  state.energyChoice = control.dataset.energy;
  render();
  return;
}

if (action === 'confirm-energy-start') {
  const prepare = await api.prepareExecution(plan.plan_id, state.energyItemId, {
    user_id: state.userId,
    energy: state.energyChoice,
  });
  if (prepare.recommended_action === 'replace_easier') {
    state.energyReplacementSuggested = true;
    render();
    return;
  }
  const payload = await api.startExecution(plan.plan_id, state.energyItemId, { user_id: state.userId });
  mergeExecutionPayload(payload);
  state.energyItemId = null;
  state.energyChoice = null;
  render();
}

if (action === 'replace-easier') {
  state.plan = await api.replacePlanItemEasier(plan.plan_id, state.energyItemId, {
    expected_version: plan.version,
    user_id: state.userId,
  });
  state.energyItemId = null;
  state.energyChoice = null;
  render();
}
```

When completing or skipping execution, send:

```javascript
{ user_id: state.userId }
```

- [ ] **Step 5: Modify `frontend/styles.css`**

Add pixel-consistent classes:

```css
.energy-panel {
  border: 3px solid var(--ink);
  background: var(--paper);
  padding: 14px;
  margin-top: 12px;
  box-shadow: 6px 6px 0 var(--shadow);
}

.energy-options {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.energy-option.is-selected {
  background: var(--mint);
  border-color: var(--green);
}
```

- [ ] **Step 6: Run frontend tests**

Run:

```powershell
node --test tests/frontend-api.test.js tests/frontend-execution.test.js tests/frontend-flow.test.js tests/frontend-visual.test.js
```

Expected: all selected frontend tests pass.

- [ ] **Step 7: Commit Task 3**

Run:

```powershell
git add frontend/api.js frontend/app.js frontend/styles.css tests/frontend-api.test.js tests/frontend-execution.test.js
git commit -m "feat: add energy check before task start"
```

---

### Task 4: Docs, Live Flow, and Full Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/api.md`
- Modify: `tests/live_core_flow.ps1`
- Test: existing Python and Node tests

**Interfaces:**
- Consumes: all Task 1 to Task 3 interfaces
- Produces: updated developer and user documentation
- Produces: live script that validates anonymous user, quick questionnaire, plan generation with user history, energy prepare, easier replacement, start, complete, and history summary

- [ ] **Step 1: Update API documentation**

In `docs/api.md`, add sections for:

```text
POST /api/v1/users/anonymous
GET /api/v1/users/{user_id}/history/summary
POST /api/v1/plans/{plan_id}/items/{item_id}/execution/prepare
POST /api/v1/plans/{plan_id}/items/{item_id}/replace-easier
```

For each endpoint include:

- Purpose
- Request JSON
- Response JSON
- Common 409/422 behavior

- [ ] **Step 2: Update README**

In `README.md`, add a “第二阶段能力” section covering:

- Anonymous `user_id` for future account migration
- Completed/skipped/replaced task learning
- Energy confirmation before start
- Easier replacement
- Manual start/end time editing remains supported
- Local startup still requires PostgreSQL, backend, and frontend commands

- [ ] **Step 3: Extend live flow script**

Modify `tests/live_core_flow.ps1` to:

1. Create anonymous user.
2. Pass `user_id` to plan generation.
3. Call execution prepare with `energy = low`.
4. Call easier replacement for the first task.
5. Start and complete the replacement task with `user_id`.
6. Fetch history summary.
7. Fail when `completed_count` is less than 1.

Add output fields:

```powershell
user_id = $userId
energy_recommended_action = $prepare.recommended_action
history_completed_count = $summary.completed_count
```

- [ ] **Step 4: Run full Python tests**

Run:

```powershell
$env:SESSION_DATABASE_URL="postgresql://postgres:你的数据库密码@127.0.0.1:5433/free_time_agent"
& ".\.venv-debug\Scripts\python.exe" -m unittest discover -s tests -q
```

Expected: exit code 0.

- [ ] **Step 5: Run full frontend tests**

Run:

```powershell
node --test tests/*.test.js
```

Expected: exit code 0.

- [ ] **Step 6: Run live core flow**

With backend running at `http://127.0.0.1:8000`, run:

```powershell
powershell -ExecutionPolicy Bypass -File tests/live_core_flow.ps1
```

Expected output contains:

```json
"energy_recommended_action": "replace_easier"
"history_completed_count": 1
```

- [ ] **Step 7: Commit Task 4**

Run:

```powershell
git add README.md docs/api.md tests/live_core_flow.ps1
git commit -m "docs: document user history energy flow"
```

---

## Final Verification and Push

- [ ] **Step 1: Check git status**

Run:

```powershell
git status --short --branch
```

Expected: the branch is clean except for the existing untracked `backup-before-github-20260814-1/` directory.

- [ ] **Step 2: Verify local and remote**

Run:

```powershell
git log -4 --oneline
```

Expected: four task commits appear in order after this plan commit.

- [ ] **Step 3: Push main**

Run:

```powershell
git push origin main
```

Expected: `main -> main`.

---

## Review Notes for Implementers

- Treat `user_id` as personalization identity, not authentication.
- Do not expose recommendation explanation copy in the frontend.
- Keep old sessions working when no `user_id` is sent.
- Make history write failures non-fatal for execution and plan generation, but never hide direct endpoint failures for `/history/summary`.
- Keep `replace_item_easier` same-category only.
- Do not stage `backup-before-github-20260814-1/`.
