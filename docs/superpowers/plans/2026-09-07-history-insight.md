# History Insight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a history plan and preference-learning view for the current anonymous user.

**Architecture:** A new backend service aggregates PostgreSQL history tables into one insight payload. FastAPI exposes one read endpoint, and the existing pixel single-page frontend switches from the plan view into an in-page history view.

**Tech Stack:** Python 3, FastAPI, psycopg/PostgreSQL, browser-native JavaScript, Node test runner.

**Spec:** `docs/superpowers/specs/2026-09-07-history-insight-design.md`

## Global Constraints

- Work directly in `D:\yxy1.0` on `main`.
- Do not add authentication or cross-device account logic in this phase.
- Use PostgreSQL-backed data already recorded by the product.
- Keep the frontend as one static HTML/CSS/JS app.
- Update README and `docs/api.md`.
- Commit completed work and push to `https://github.com/liorakozev639-a11y/yxy1.0`.

---

### Task 1: Backend History Insight Service

**Files:**
- Create: `history_insight_service.py`
- Test: `tests/test_history_insight_service.py`

**Interfaces:**
- Produces: `HistoryInsightService(database_url: str)`
- Produces: `HistoryInsightService.insight(user_id: str) -> dict[str, Any]`

- [x] **Step 1: Write failing tests**

Create tests for:
- Empty user history returns `has_history=false`.
- Completed, skipped, replaced, and low-rating records affect summary counts.
- Recent plans are limited to 5 and sorted newest first.
- Favorite categories and avoided groups are returned with user-facing labels.

- [x] **Step 2: Run tests and verify failure**

Run:

```powershell
.\.venv-debug\Scripts\python.exe -m unittest tests.test_history_insight_service -v
```

Expected: fails because `history_insight_service` does not exist.

- [x] **Step 3: Implement service**

Implement PostgreSQL queries against `user_task_history`, `plans`, `plan_items`, and `task_feedback`.

- [ ] **Step 4: Run tests and verify pass**

Run the same unittest command.

Status: blocked locally because PostgreSQL on `127.0.0.1:5433` is not accepting connections. Offline Python compilation has passed.

### Task 2: FastAPI Endpoint

**Files:**
- Modify: `main.py`
- Test: `tests/test_user_history_api.py`

**Interfaces:**
- Consumes: `HistoryInsightService.insight(user_id)`
- Produces: `GET /api/v1/users/{user_id}/history/insight`

- [x] **Step 1: Write failing API test**

Add a TestClient assertion that the new endpoint returns `has_history` and `summary`.

- [ ] **Step 2: Run test and verify failure**

Expected: `404 Not Found`.

- [x] **Step 3: Wire service into `build_services()` and `create_app()`**

Instantiate `HistoryInsightService` when `SESSION_DATABASE_URL` is present.

- [ ] **Step 4: Run API tests and verify pass**

Run:

```powershell
.\.venv-debug\Scripts\python.exe -m unittest tests.test_user_history_api -v
```

### Task 3: Frontend History View

**Files:**
- Modify: `frontend/api.js`
- Modify: `frontend/app.js`
- Modify: `frontend/styles.css`
- Test: `tests/frontend-api.test.js`
- Test: `tests/frontend-visual.test.js`

**Interfaces:**
- Consumes: `api.getHistoryInsight(userId)`
- Produces: plan page button `data-action="view-history"` and view state `state.showingHistory`.

- [x] **Step 1: Write failing frontend tests**

Assert that:
- API client calls `/api/v1/users/{user_id}/history/insight`.
- Formal frontend source contains `view-history`, `history-panel`, and empty-state copy.

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
node --test tests/frontend-api.test.js tests/frontend-visual.test.js
```

- [x] **Step 3: Implement API and UI**

Add API wrapper, state, click handlers, history render function, and pixel styles.

- [x] **Step 4: Run frontend tests and verify pass**

Run the same Node command.

### Task 4: Documentation, Verification, Commit, Push

**Files:**
- Modify: `README.md`
- Modify: `docs/api.md`
- Modify: `docs/superpowers/plans/2026-09-07-history-insight.md`

- [x] **Step 1: Update docs**

Document product behavior, endpoint contract, and manual testing steps.

- [ ] **Step 2: Run targeted regression**

Run:

```powershell
.\.venv-debug\Scripts\python.exe -m unittest tests.test_history_insight_service tests.test_user_history_api tests.test_user_history_service -v
node --test tests/frontend-api.test.js tests/frontend-visual.test.js tests/frontend-flow.test.js
```

- [ ] **Step 3: Commit**

Commit all tracked feature files.

- [ ] **Step 4: Push**

Push `main` to GitHub.
