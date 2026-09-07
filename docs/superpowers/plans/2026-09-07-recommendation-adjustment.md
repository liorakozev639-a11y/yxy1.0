# Recommendation Adjustment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build session-scoped recommendation adjustment buttons so replacing or tuning a task never cycles back to tasks already shown in the same session.

**Architecture:** Store task-level exclusions in PostgreSQL through `RecommendationMemory`, use `recommendation_module.py` for intent-based candidate ranking, expose backend adjustment endpoints in `main.py`, and wire the pixel frontend to those endpoints. Existing plan versioning remains the source of truth for scheduled items.

**Tech Stack:** Python 3, FastAPI, psycopg/PostgreSQL, browser-native JavaScript, Node test runner.

**Spec:** User-approved Q&A in this thread: six adjustment buttons, session-only memory, direct replacement, keep original when no candidate exists, no category-breaking replacement, and no task1/task2 alternation.

## Global Constraints

- Work directly on `D:\yxy1.0` `main`.
- Persist only to PostgreSQL and current frontend local state; do not add in-memory-only repositories for production flow.
- Each completed local feature change must be committed.
- Push final commits to `https://github.com/liorakozev639-a11y/yxy1.0`.

---

### Task 1: Backend Adjustment Selection And Memory

**Files:**
- Modify: `recommendation_module.py`
- Modify: `recommendation_memory.py`
- Modify: `plan_module.py`
- Modify: `mvp_orchestrator.py`
- Modify: `main.py`
- Test: `tests/test_plan_replacement_rules.py`

**Interfaces:**
- Produces: `select_adjusted_task(candidates, current_task, adjustment, used_task_ids, constraints, excluded_feedback_groups=None) -> Task | None`
- Produces: `RecommendationMemory.record_task_adjustment(session_id, task_id, adjustment) -> dict`
- Produces: `RecommendationMemory.list_excluded_task_ids(session_id) -> set[str]`
- Produces: `PlanManagementService.adjust_item(...) -> dict`
- Produces: `MVPOrchestrator.adjust_recommendation(...) -> dict`

- [x] **Step 1: Write failing tests**

- [x] **Step 2: Run tests and verify missing functions fail**

- [x] **Step 3: Implement minimal backend logic**

- [x] **Step 4: Run backend tests**

- [x] **Step 5: Commit backend change**

### Task 2: Frontend Adjustment Buttons

**Files:**
- Modify: `frontend/api.js`
- Modify: `frontend/app.js`
- Modify: `frontend/styles.css`
- Test: `tests/frontend-api.test.js`
- Test: frontend rendering smoke tests if affected

**Interfaces:**
- Consumes: backend `/adjust` endpoints.
- Produces: visible task-card adjustment buttons and current-pool exclusion payloads.

- [x] **Step 1: Write failing API test**

- [x] **Step 2: Run frontend API test and verify missing functions fail**

- [x] **Step 3: Implement API wrappers and click handling**

- [x] **Step 4: Run frontend tests**

- [x] **Step 5: Commit frontend change**

### Task 3: Documentation And Final Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/api.md`

**Interfaces:**
- Produces: usage notes and API contract for adjustment buttons and session-scoped task exclusions.

- [x] **Step 1: Update docs**

- [x] **Step 2: Run targeted Python and Node tests**

- [x] **Step 3: Commit docs**

- [x] **Step 4: Push to GitHub**
