# Render Supabase Web Deploy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare the project for a free Render + Supabase web deployment without storing real secrets in Git.

**Architecture:** Render runs the FastAPI backend as a Python web service and serves the frontend as a static site. Supabase provides the PostgreSQL connection string through Render environment variables, while a small build-time script writes the public frontend API URL into `frontend/config.js`.

**Tech Stack:** FastAPI, Uvicorn, PostgreSQL/Supabase, Render Blueprint, static HTML/CSS/JavaScript, PowerShell local scripts.

**Spec:** User selected the free "Render backend + Supabase PostgreSQL + static frontend" deployment path.

## Global Constraints

- Work directly in `D:\yxy1.0` on `main`.
- Do not commit real database passwords or `.env.production`.
- Keep the current local PostgreSQL and frontend debugging flow usable.
- Deployment must preserve PWA behavior and live API reads from PostgreSQL.

---

### Task 1: Deployment Configuration Tests

**Files:**
- Create: `tests/deploy-config.test.js`

**Interfaces:**
- Consumes: repository root files.
- Produces: a regression test that proves Render deployment configuration exists and the frontend config writer does not leak secrets.

- [x] **Step 1: Write the failing test**

Run:

```powershell
node --test tests\deploy-config.test.js
```

Expected before implementation: FAIL because `render.yaml` and `deploy/write_frontend_config.py` do not exist.

### Task 2: Render Blueprint and Config Writer

**Files:**
- Create: `render.yaml`
- Create: `deploy/write_frontend_config.py`
- Modify: `deploy/README-deploy.md`
- Modify: `README.md`
- Modify: `docs/api.md`

**Interfaces:**
- Consumes: Render environment variables `SESSION_DATABASE_URL`, `FRONTEND_ORIGINS`, and `FREE_TIME_API_BASE_URL`.
- Produces: a Render backend service, a Render static frontend service, and a build-time generated `frontend/config.js`.

- [ ] **Step 1: Create `render.yaml`**

Define `free-time-agent-api` with:

```yaml
runtime: python
buildCommand: pip install -r requirements.txt
startCommand: python -m uvicorn main:app --host 0.0.0.0 --port $PORT
```

Define `free-time-agent-web` with:

```yaml
runtime: static
buildCommand: python deploy/write_frontend_config.py
staticPublishPath: ./frontend
```

- [ ] **Step 2: Create frontend config writer**

The script reads `FREE_TIME_API_BASE_URL` and writes only the public URL to `frontend/config.js`.

- [ ] **Step 3: Run deployment tests**

Run:

```powershell
node --test tests\deploy-config.test.js
```

Expected: PASS.

### Task 3: Full Verification and Commit

**Files:**
- Modify: Git index only.

**Interfaces:**
- Consumes: all updated code and docs.
- Produces: one local commit and one GitHub push.

- [ ] **Step 1: Run full frontend tests**

```powershell
node --test tests\*.test.js
```

Expected: all tests pass.

- [ ] **Step 2: Run full Python tests**

```powershell
$env:SESSION_DATABASE_URL='postgresql://postgres:yxy050621@127.0.0.1:5433/free_time_agent'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

Expected: all tests pass.

- [ ] **Step 3: Commit and push**

```powershell
git add render.yaml deploy/write_frontend_config.py tests/deploy-config.test.js README.md docs/api.md deploy/README-deploy.md docs/superpowers/plans/2026-09-09-render-supabase-web-deploy.md
git commit -m "chore: prepare render supabase deployment"
git push origin main
```

Expected: GitHub `main` contains the deployment preparation.

