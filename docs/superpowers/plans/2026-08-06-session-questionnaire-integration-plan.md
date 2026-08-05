# Session Questionnaire Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a locally runnable frontend-to-PostgreSQL flow for session creation, preferences, quick/deep questionnaires, answer persistence, progress recovery, and submission.

**Architecture:** `main.py` is the only HTTP entry point on port 8000. `session_module.py` and `questionnaire_module.py` keep domain services and provide memory/PostgreSQL repositories; `main.py` composes them with a shared `session_id`. The static frontend calls one API base URL and stores only `free_time_agent_session_id` in `localStorage`.

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, Pydantic, psycopg 3, PostgreSQL 18, vanilla HTML/CSS/JavaScript, Node.js built-in test runner.

## Global Constraints

- Work in `D:\yxy1.0`; do not modify the existing uncommitted root `task_repository.py` change.
- Do not use Token or `Authorization`; all test-version state is keyed by `session_id`.
- Use `SESSION_DATABASE_URL`; never commit the real PostgreSQL password.
- Support both `quick` (5 questions) and `deep` (30 questions).
- Allow CORS only for `http://127.0.0.1:5173` and `http://localhost:5173`.
- Keep Profile, Task Repository, Recommendation, candidate tasks, and planning out of scope.
- Every task ends with verification and its own commit.

---

### Task 1: No-token Session persistence

**Files:**
- Modify: `session_module.py`
- Create: `tests/test_session_service.py`

**Interfaces:**
- Produces: `SessionRepository` protocol with `save(session)`, `get(session_id)`, and `delete(session_id)`.
- Produces: `InMemorySessionRepository` and `PostgresSessionRepository(database_url)`.
- Produces: `SessionService.create()`, `require_active(session_id)`, `save_preferences(session_id, preferences)`, `restore(session_id)`, and `clear_data(session_id)`.

- [ ] **Step 1: Write failing session service tests**

```python
def test_create_returns_no_token_and_restore_uses_session_id():
    service = SessionService(InMemorySessionRepository())
    created = service.create()
    assert set(created) == {"session_id", "stage", "version", "expires_at"}
    restored = service.restore(created["session_id"])
    assert restored["session_id"] == created["session_id"]


def test_preferences_survive_repository_reload(postgres_url):
    first = SessionService(PostgresSessionRepository(postgres_url))
    created = first.create()
    first.save_preferences(created["session_id"], {"categories": ["energy"]})
    second = SessionService(PostgresSessionRepository(postgres_url))
    assert second.restore(created["session_id"])["preferences"]["categories"] == ["energy"]
```

- [ ] **Step 2: Run tests and verify the no-token contract fails**

Run: `python -m unittest tests.test_session_service -v`

Expected: FAIL because the current service returns and requires a Token.

- [ ] **Step 3: Implement the no-token session aggregate**

Remove token generation and validation. Keep expiration validation in `require_active`. Add PostgreSQL schema compatibility:

```sql
CREATE TABLE IF NOT EXISTS sessions (...);
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS stage TEXT;
ALTER TABLE sessions ALTER COLUMN token_hash DROP NOT NULL;
```

Use an upsert that does not write `token_hash`. Preserve existing unrelated columns.

- [ ] **Step 4: Run memory and PostgreSQL tests**

Run: `python -m unittest tests.test_session_service -v`

Expected: PASS; created payload has no Token, and a fresh repository instance restores preferences.

- [ ] **Step 5: Commit Task 1**

```bash
git add session_module.py tests/test_session_service.py
git commit -m "feat: persist no-token sessions"
```

### Task 2: Shared PostgreSQL Questionnaire persistence

**Files:**
- Modify: `questionnaire_module.py`
- Create: `tests/test_questionnaire_service.py`

**Interfaces:**
- Consumes: `SessionService.require_active(session_id)` and its returned `.preferences`.
- Produces: `QuestionnaireRepository` protocol.
- Produces: `InMemoryQuestionnaireRepository` and `PostgresQuestionnaireRepository(database_url)`.
- Produces: existing `QuestionnaireService.start`, `save_answer`, `skip_question`, `progress`, and `submit` against either repository.

- [ ] **Step 1: Write failing questionnaire persistence tests**

```python
def test_quick_and_deep_counts():
    quick = service.start(session_id, "quick")
    assert quick["total"] == 5
    service_for_second_session.start(second_session_id, "deep")
    assert service_for_second_session.progress(second_session_id)["total"] == 30


def test_answer_survives_repository_reload(postgres_url):
    service.start(session_id, "quick")
    service.save_answer(session_id, "q_energy", 4)
    restored = build_service_with_new_repository(postgres_url)
    assert restored.progress(session_id)["answered_count"] == 1
```

- [ ] **Step 2: Run tests and verify PostgreSQL repository is missing**

Run: `python -m unittest tests.test_questionnaire_service -v`

Expected: FAIL because the current repository is memory-only and sessions are stored separately.

- [ ] **Step 3: Implement shared session adapter and PostgreSQL repository**

Create tables:

```sql
CREATE TABLE IF NOT EXISTS questionnaires (
  session_id TEXT PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
  mode TEXT NOT NULL CHECK (mode IN ('quick', 'deep')),
  question_ids JSONB NOT NULL,
  submitted BOOLEAN NOT NULL DEFAULT FALSE,
  started_at TIMESTAMPTZ NOT NULL,
  submitted_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS questionnaire_answers (
  session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  question_id TEXT NOT NULL,
  value INTEGER,
  skipped BOOLEAN NOT NULL DEFAULT FALSE,
  answered_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (session_id, question_id)
);
```

Upsert answers by `(session_id, question_id)` and reject changes after submission.

- [ ] **Step 4: Run quick, deep, update, skip, submit, and restart tests**

Run: `python -m unittest tests.test_questionnaire_service -v`

Expected: PASS with 5/30 counts and restored answers from a new repository instance.

- [ ] **Step 5: Commit Task 2**

```bash
git add questionnaire_module.py tests/test_questionnaire_service.py
git commit -m "feat: persist questionnaire progress"
```

### Task 3: Unified FastAPI application

**Files:**
- Create: `main.py`
- Create: `tests/test_api_flow.py`
- Create: `requirements.txt`
- Create: `.env.example`

**Interfaces:**
- Consumes: `SessionService` and `QuestionnaireService` from Tasks 1 and 2.
- Produces: `create_app(session_service=None, questionnaire_service=None) -> FastAPI`.
- Produces: the Session and Questionnaire endpoints from the approved design on port 8000.

- [ ] **Step 1: Write failing HTTP contract tests**

```python
def test_complete_quick_flow(client):
    session_id = client.post("/api/v1/sessions").json()["data"]["session_id"]
    saved = client.put(
        f"/api/v1/sessions/{session_id}/preferences",
        json={"categories": ["energy"], "duration": "half", "budget": "low", "outing": "home", "company": "solo"},
    )
    assert saved.status_code == 200
    started = client.post(
        f"/api/v1/sessions/{session_id}/questionnaire/start",
        json={"mode": "quick"},
    )
    assert started.json()["data"]["total"] == 5
```

Also assert that an OPTIONS request from `127.0.0.1:5173` receives an allow-origin header, while another origin does not.

- [ ] **Step 2: Run tests and verify `main.py` is missing**

Run: `python -m unittest tests.test_api_flow -v`

Expected: FAIL importing `main`.

- [ ] **Step 3: Implement `create_app` and unified error responses**

Register the approved endpoints, CORS middleware, and handlers returning:

```json
{"data": null, "error": {"code": "session_not_found", "message": "会话不存在"}}
```

Production construction reads `SESSION_DATABASE_URL` and builds PostgreSQL repositories. Tests inject memory repositories.

- [ ] **Step 4: Run HTTP tests and OpenAPI route inventory**

Run: `python -m unittest tests.test_api_flow -v`

Run: `python -c "import main; print(sorted(route.path for route in main.app.routes if route.path.startswith('/api')))"`

Expected: all approved routes are present and tests pass.

- [ ] **Step 5: Commit Task 3**

```bash
git add main.py tests/test_api_flow.py requirements.txt .env.example
git commit -m "feat: add unified session questionnaire api"
```

### Task 4: Frontend API integration

**Files:**
- Create: `frontend/api.js`
- Modify: `frontend/index.html`
- Modify: `frontend/app.js`
- Modify: `frontend/styles.css`
- Create: `tests/frontend-api.test.js`
- Modify: `tests/demo-v2-smoke.test.js`

**Interfaces:**
- Consumes: the unified API at `window.FREE_TIME_API_BASE_URL || 'http://127.0.0.1:8000'`.
- Produces: `window.FreeTimeApi` with `createSession`, `restoreSession`, `savePreferences`, `startQuestionnaire`, `saveAnswer`, `skipQuestion`, `getProgress`, `submitQuestionnaire`, and `clearSession`.

- [ ] **Step 1: Write failing API client and rendered-flow tests**

```javascript
test('createSession stores only the session id', async () => {
  const api = createApi({ fetchImpl, storage });
  const result = await api.createSession();
  assert.equal(storage.getItem('free_time_agent_session_id'), result.session_id);
  assert.equal(storage.getItem('token'), null);
});
```

Smoke tests must assert `api.js` loads before `app.js`, both questionnaire mode buttons exist, and the old candidate/plan actions are absent from the active flow.

- [ ] **Step 2: Run Node tests and verify API module is missing**

Run: `node --test tests/frontend-api.test.js tests/demo-v2-smoke.test.js`

Expected: FAIL because `frontend/api.js` and the new mode/result UI do not exist.

- [ ] **Step 3: Implement API client and async application state**

Replace local question generation with backend responses. Render these states:

```text
booting -> welcome -> profile -> mode -> quiz -> result
```

Disable controls while saving; on failures retain the current question and show a retry action. On boot, restore `session_id`, questionnaire progress, and submitted result.

- [ ] **Step 4: Run JavaScript tests and static syntax checks**

Run: `node --test tests/frontend-api.test.js tests/demo-v2-smoke.test.js`

Run: `node --check frontend/api.js && node --check frontend/app.js`

Expected: all tests and syntax checks pass.

- [ ] **Step 5: Commit Task 4**

```bash
git add frontend tests/frontend-api.test.js tests/demo-v2-smoke.test.js
git commit -m "feat: connect frontend to questionnaire api"
```

### Task 5: Live PostgreSQL recovery and documentation

**Files:**
- Create: `README.md`
- Create: `tests/live_flow.ps1`

**Interfaces:**
- Consumes: `main.py`, PostgreSQL on `127.0.0.1:5433`, and the frontend on port 5173.
- Produces: repeatable startup, PyCharm debugging, and live API verification instructions.

- [ ] **Step 1: Write the live verification script**

The PowerShell script creates a session, saves preferences, starts a quick questionnaire, saves one answer, and prints the session ID without printing database credentials.

- [ ] **Step 2: Run full automated tests**

Run: `python -m unittest discover -s tests -p 'test_*.py' -v`

Run: `node --test tests/*.test.js`

Expected: all Python and JavaScript tests pass.

- [ ] **Step 3: Run live services and recovery check**

Start backend with `SESSION_DATABASE_URL` set, run `tests/live_flow.ps1`, stop and restart `main.py`, then GET the recorded session and questionnaire progress. Expected: saved preferences and one answer remain.

- [ ] **Step 4: Verify browser assets and CORS**

Run the static frontend on 5173 and verify `/`, `/styles.css`, `/api.js`, and `/app.js` return 200. Verify backend OPTIONS preflight returns the configured allow-origin header.

- [ ] **Step 5: Document exact commands and commit Task 5**

```bash
git add README.md tests/live_flow.ps1
git commit -m "docs: add local integration runbook"
```

