# 第二阶段执行闭环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将已生成的计划接入 PostgreSQL 执行状态、超时调整和任务反馈，并在像素正式前端完成可操作的执行闭环。

**Architecture:** 保留现有 `execution_module.py` 的纯状态机作为规则核心，新增 PostgreSQL-backed `ExecutionService` 负责事务、行锁和事件持久化；新增 `FeedbackService` 负责幂等评分。FastAPI 只做参数校验和路由，像素前端通过 `api.js` 调用新接口并刷新当前计划。

**Tech Stack:** Python 3.12、FastAPI、psycopg 3、PostgreSQL、原生 HTML/CSS/JS、Node `node:test`、Python `unittest`。

## Global Constraints

- 仅使用 PostgreSQL，不新增内存生产仓储。
- 执行跳过使用 `needs_adjustment`，计划编辑移出使用已有 `skipped`。
- 任务状态更新必须在事务中锁定目标计划任务，重复请求保持幂等。
- 反馈评分范围为 1 至 5，原因标签可以为空，最多保存三个标签。
- 已完成任务不可再次开始、跳过或覆盖。
- 重新排程不得覆盖已完成任务或已记录的执行事件。
- 像素前端继续使用 `http://127.0.0.1:5173/`，不使用 52341 静态预览作为正式入口。

---

### Task 1: PostgreSQL 执行服务与事件持久化

**Files:**
- Create: `execution_service.py`
- Modify: `execution_module.py` only if shared status helpers need a narrow export
- Test: `tests/test_execution_service.py`

**Interfaces:**
- `ExecutionService(database_url, sessions)`
- `execute(session_id, plan_id, item_id, action, now=None) -> dict[str, Any]`
- `check_deadline(session_id, plan_id, item_id, now=None) -> dict[str, Any]`
- `events(session_id, plan_id, item_id=None) -> list[dict[str, Any]]`

- [ ] Write failing PostgreSQL tests for start, complete, skip, deadline and invalid transitions.
- [ ] Run `python -m unittest tests.test_execution_service -v` and confirm the service is missing.
- [ ] Create `execution_events` in `init_schema()` and load the target `plan_items` row with `FOR UPDATE`.
- [ ] Convert the database row into `execution_module.PlanItem`, call `execute_action()` or `expire_if_needed()`, update the row and insert one event in the same transaction.
- [ ] Return the updated item, plan id, status and latest event; make repeated deadline checks produce no second event.
- [ ] Run the focused tests and commit `feat: persist execution events`.

### Task 2: PostgreSQL feedback service

**Files:**
- Create: `feedback_service.py`
- Test: `tests/test_feedback_service.py`

**Interfaces:**
- `FeedbackService(database_url, sessions)`
- `save(session_id, plan_id, item_id, rating, reasons=None) -> dict[str, Any]`
- `list_for_plan(session_id, plan_id) -> list[dict[str, Any]]`

- [ ] Write failing tests for rating validation, empty reasons and update-on-repeat.
- [ ] Run the focused tests and confirm the table/service is missing.
- [ ] Create `task_feedback` with a unique `(plan_id, item_id)` constraint and JSONB reasons.
- [ ] Verify the plan item belongs to the session and has status `completed` before accepting feedback.
- [ ] Normalize reasons to at most three strings and use `ON CONFLICT` to update the existing row.
- [ ] Run focused tests and commit `feat: add task feedback persistence`.

### Task 3: FastAPI contract and Swagger routes

**Files:**
- Modify: `main.py`
- Modify: `docs/api.md`
- Test: `tests/test_execution_api.py`

**Interfaces:**
- `POST /api/v1/plans/{plan_id}/items/{item_id}/execution/start`
- `POST /api/v1/plans/{plan_id}/items/{item_id}/execution/complete`
- `POST /api/v1/plans/{plan_id}/items/{item_id}/execution/skip`
- `POST /api/v1/plans/{plan_id}/items/{item_id}/execution/check-deadline`
- `POST /api/v1/plans/{plan_id}/items/{item_id}/feedback`
- `GET /api/v1/plans/{plan_id}/feedback`

- [ ] Write a failing API test that creates a real PostgreSQL plan, starts a task, completes it, submits rating and reads feedback.
- [ ] Run the focused API test and confirm the paths are absent.
- [ ] Add `ExecutionService` and `FeedbackService` wiring to `create_app()` without breaking fake-service unit tests.
- [ ] Add request models for optional `now`, `rating` and `reasons`; route errors through the existing JSON error envelope.
- [ ] Add the endpoint table and request/response examples to `docs/api.md`.
- [ ] Run API tests and verify the new paths appear in `/openapi.json`; commit `feat: expose execution and feedback api`.

### Task 4: Pixel frontend execution controls

**Files:**
- Modify: `frontend/api.js`
- Modify: `frontend/app.js`
- Modify: `frontend/styles.css`
- Test: `tests/frontend-execution.test.js`

**Interfaces:**
- `startExecution(planId, itemId)`
- `completeExecution(planId, itemId)`
- `skipExecution(planId, itemId)`
- `checkExecutionDeadline(planId, itemId)`
- `saveFeedback(planId, itemId, payload)`

- [ ] Write failing source-contract tests for new API methods, status labels and rating controls.
- [ ] Run the focused Node test and confirm the methods and markup are absent.
- [ ] Add API helpers using the existing request wrapper and cache-bust `api.js` in `index.html` if needed.
- [ ] Render task-card controls according to `pending`, `active`, `completed` and `needs_adjustment`.
- [ ] Add a five-level pixel rating strip and optional reason chips; after success reload the plan without clearing session or questionnaire state.
- [ ] Add pixel styles for active/completed/adjustment states and run Node tests and syntax checks; commit `feat: add pixel execution controls`.

### Task 5: Full acceptance and synchronization

**Files:**
- Modify: `tests/test_plan_module.py` only if shared setup needs a reusable helper
- Create: `tests/test_phase_two_live.py`
- Modify: `docs/空闲时间规划Agent-MVP-PRD.md` only if acceptance notes need a link to the implemented endpoints

- [ ] Write a live PostgreSQL test covering generate plan -> start -> complete -> feedback -> skip/deadline on another item -> read feedback.
- [ ] Run it against `postgresql://postgres:<local-password>@127.0.0.1:5433/free_time_agent` and verify event/feedback rows exist.
- [ ] Run `node --test tests/*.test.js` and `python -m unittest discover -s tests -p 'test_*.py'`.
- [ ] Verify `http://127.0.0.1:8000/openapi.json` and `http://127.0.0.1:5173/` return 200 and the new routes are listed.
- [ ] Commit the acceptance test and push `main` to GitHub.
