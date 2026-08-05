# Session Module Local Debug Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair and locally validate the FastAPI session module with its in-memory repository before the later PostgreSQL migration.

**Architecture:** Keep the existing `SessionService` and `InMemorySessionRepository` boundaries. Repair the API module in place, add focused service/API smoke coverage, and run the app with Uvicorn on localhost. PostgreSQL remains a documented phase-two backend and is not coupled into this first debugging pass.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, Uvicorn, pytest, FastAPI TestClient/httpx.

## Global Constraints

- The first phase keeps `InMemorySessionRepository` and does not add PostgreSQL persistence.
- Protected endpoints require `Authorization: Bearer <token>`.
- Session tokens are stored only as SHA-256 hashes and checked with constant-time comparison.
- Answer values are restricted to integers 1 through 4.
- Do not delete unrelated files or user data.
- PostgreSQL phase-two target is `127.0.0.1:5433/free_time_agent`.

---

### Task 1: Repair the runnable session module

**Files:**
- Modify: `examples/session_module.py`

**Interfaces:**
- Preserve `SessionService.create`, `require_valid`, `save_preferences`, `save_answer`, `restore`, and `clear_data` signatures.
- Preserve the existing HTTP routes and JSON response envelope.

- [ ] **Step 1: Locate malformed literals and compatibility issues**

Run:

```powershell
Select-String -Path examples/session_module.py -Pattern 'detail=|model_dump|uvicorn.run|if __name__'
```

Expected: identify malformed error strings and confirm the module uses Pydantic v2's `model_dump()`.

- [ ] **Step 2: Repair only the broken literals and startup block**

Use valid Chinese or ASCII messages with complete quoted strings, for example:

```python
raise HTTPException(status_code=401, detail="会话不存在")
raise HTTPException(status_code=401, detail="会话已过期")
raise HTTPException(status_code=400, detail="答案必须是 1、2、3 或 4")
raise HTTPException(status_code=401, detail="需要 Authorization: Bearer <token>")
```

Keep all business logic and route paths unchanged. Ensure the file ends with:

```python
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

- [ ] **Step 3: Run a syntax/import check**

Run:

```powershell
uv run --python 3.12 python -m py_compile examples/session_module.py
```

Expected: command exits with code 0 and produces no syntax error.

- [ ] **Step 4: Commit the focused repair when a Git repository is available**

```powershell
git add examples/session_module.py
git commit -m "fix: repair session module runtime syntax"
```

If the working directory is not a Git repository, record the change without deleting or initializing an unrelated repository.

### Task 2: Add service-level regression coverage

**Files:**
- Create: `tests/test_session_module.py`
- Modify: none

**Interfaces:**
- Consumes: `repository = InMemorySessionRepository()` and `service = SessionService(repository)`.
- Produces: deterministic tests for session state transitions and authentication failures.

- [ ] **Step 1: Add tests for creation and restore**

```python
def test_create_and_restore_round_trip():
    repository = InMemorySessionRepository()
    service = SessionService(repository)
    created = service.create()

    restored = service.restore(created["session_id"], created["token"])

    assert restored["stage"] == SessionStage.INTERESTS
    assert restored["preferences"] == {}
    assert restored["answers"] == {}
```

- [ ] **Step 2: Add tests for state changes and clearing**

```python
def test_preferences_answers_and_clear():
    repository = InMemorySessionRepository()
    service = SessionService(repository)
    created = service.create()
    sid, token = created["session_id"], created["token"]

    service.save_preferences(sid, token, {"categories": ["活力充电"]})
    service.save_answer(sid, token, "q_01", 4)
    restored = service.restore(sid, token)
    assert restored["stage"] == SessionStage.QUESTIONNAIRE
    assert restored["answers"] == {"q_01": 4}

    service.clear_data(sid, token)
    restored = service.restore(sid, token)
    assert restored["stage"] == SessionStage.INTERESTS
    assert restored["preferences"] == {}
    assert restored["answers"] == {}
```

- [ ] **Step 3: Add tests for invalid authentication and values**

```python
import pytest
from fastapi import HTTPException

def test_invalid_token_is_rejected():
    repository = InMemorySessionRepository()
    service = SessionService(repository)
    created = service.create()

    with pytest.raises(HTTPException) as error:
        service.restore(created["session_id"], "wrong-token")

    assert error.value.status_code == 401

def test_answer_must_be_between_one_and_four():
    repository = InMemorySessionRepository()
    service = SessionService(repository)
    created = service.create()

    with pytest.raises(HTTPException) as error:
        service.save_answer(created["session_id"], created["token"], "q_01", 5)

    assert error.value.status_code == 400
```

- [ ] **Step 4: Run the focused tests**

Run:

```powershell
uv run --python 3.12 --with fastapi --with pytest pytest tests/test_session_module.py -q
```

Expected: all focused tests pass.

### Task 3: Verify the HTTP workflow locally

**Files:**
- Modify: none
- Test: running process for `examples/session_module.py`

**Interfaces:**
- Consumes: FastAPI routes `/api/v1/sessions`, `/api/v1/sessions/{session_id}`, `/preferences`, `/questionnaire/answers/{question_id}`, and `/data`.
- Produces: a repeatable manual smoke-test record.

- [ ] **Step 1: Start the API**

Run:

```powershell
uv run --python 3.12 --with fastapi --with uvicorn python examples/session_module.py
```

Expected: Uvicorn listens at `http://127.0.0.1:8000`.

- [ ] **Step 2: Create and restore a session**

In another PowerShell window:

```powershell
$created = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/sessions
$sid = $created.data.session_id
$token = $created.data.token
$headers = @{ Authorization = "Bearer $token" }
Invoke-RestMethod -Headers $headers -Uri "http://127.0.0.1:8000/api/v1/sessions/$sid"
```

Expected: response contains stage `interests`, empty preferences, and empty answers.

- [ ] **Step 3: Save preferences and an answer**

```powershell
$preferences = @{categories=@('活力充电');duration='half_day';budget='low';outing='home';company='solo';rest_only=$false} | ConvertTo-Json
Invoke-RestMethod -Method Put -Headers $headers -ContentType 'application/json' -Body $preferences -Uri "http://127.0.0.1:8000/api/v1/sessions/$sid/preferences"
Invoke-RestMethod -Method Patch -Headers $headers -ContentType 'application/json' -Body '{"value":4}' -Uri "http://127.0.0.1:8000/api/v1/sessions/$sid/questionnaire/answers/q_01"
```

Expected: both responses report `saved: true`.

- [ ] **Step 4: Verify invalid token and clear data**

```powershell
try { Invoke-RestMethod -Headers @{Authorization='Bearer invalid'} -Uri "http://127.0.0.1:8000/api/v1/sessions/$sid" } catch { $_.Exception.Response.StatusCode }
Invoke-RestMethod -Method Delete -Headers $headers -Uri "http://127.0.0.1:8000/api/v1/sessions/$sid/data"
Invoke-RestMethod -Headers $headers -Uri "http://127.0.0.1:8000/api/v1/sessions/$sid"
```

Expected: invalid token returns HTTP 401; the final restore shows empty draft data and stage `interests`.

### Task 4: Define the PostgreSQL migration handoff

**Files:**
- Create: `docs/superpowers/specs/2026-08-05-session-module-postgres-migration-design.md` in a later approved phase
- Modify: `examples/session_module.py` only after the migration design is approved

**Interfaces:**
- Consumes: current `Session` fields and service methods.
- Produces: a repository interface and PostgreSQL implementation selected by configuration.

- [ ] **Step 1: Do not modify PostgreSQL code during the first-phase debug pass**

The acceptance gate is the passing in-memory test and HTTP smoke test from Tasks 2 and 3.

- [ ] **Step 2: Record the phase-two schema before implementation**

The later design must define a `sessions` table containing `id`, `token_hash`, `stage`, timestamps, `version`, and JSONB fields for preferences, answers, profile, and plan. It must also define the unique session ID constraint and expiry query behavior.

- [ ] **Step 3: Use configuration for the phase-two connection**

The later implementation must read a connection URL from an environment variable rather than hard-code the password or connection string.
