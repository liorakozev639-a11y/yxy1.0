# MVP Core Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将核心 MVP 模块整合为 PostgreSQL-backed FastAPI 闭环，并让前端使用统一 API 展示生成计划。

**Architecture:** 保留现有模块的领域规则，新增 PostgreSQL Profile/Plan repository 和 `mvp_orchestrator.py` 编排层。`main.py` 统一注册路由，前端调用主 API，静态人工审核任务库继续作为 Task Repository 数据源。

**Tech Stack:** Python 3.12+, FastAPI, Pydantic, psycopg 3, PostgreSQL, 原生 HTML/CSS/JavaScript。

## Global Constraints

- 生产数据只使用 PostgreSQL，不使用内存仓储。
- API 同步执行，不使用 MQ、Celery 或异步 Worker。
- 计划交付只使用网页 JSON。
- 保留当前 `main` 分支和已有未提交改动。
- 每个阶段先写失败测试，再写最小实现。

### Task 1: Profile and Plan Persistence Contracts

**Files:**
- Create: `tests/test_mvp_integration.py`
- Create: `mvp_orchestrator.py`
- Modify: `profile_module.py`
- Modify: `delivery_module.py`

**Interfaces:**
- `ProfileRepository.save(profile)` and `get(session_id)`.
- `PlanRepository.save(plan)` and `get(session_id)`.
- `MVPOrchestrator.generate_plan(session_id, request)`.

- [ ] Write tests for profile/plan persistence contracts and generate flow.
- [ ] Run the focused test and confirm it fails because the orchestrator is absent.
- [ ] Add PostgreSQL repositories and the smallest orchestration implementation.
- [ ] Run focused tests and confirm they pass.
- [ ] Commit `feat: add mvp orchestration persistence`.

### Task 2: Unified FastAPI Routes

**Files:**
- Modify: `main.py`
- Modify: `requirements.txt`
- Create: `docs/api.md`

**Interfaces:**
- Add `POST /api/v1/sessions/{session_id}/plan/generate`.
- Add `GET /api/v1/sessions/{session_id}/plan`.
- Add `GET /api/v1/sessions/{session_id}/plan/delivery`.

- [ ] Add route contract tests for successful and invalid generation.
- [ ] Run tests and confirm new routes fail before registration.
- [ ] Register services and routes with PostgreSQL-backed dependencies.
- [ ] Generate static API documentation from the route contract.
- [ ] Run all Python tests and commit `feat: expose integrated mvp api`.

### Task 3: Frontend API Alignment

**Files:**
- Modify: `frontend/api.js`
- Modify: `frontend/app.js`
- Modify: `frontend/logic.js`
- Modify: `frontend/index.html`

**Interfaces:**
- Use `POST /api/v1/sessions/{session_id}/plan/generate` after questionnaire submission.
- Render returned `delivery.payload.items` in the plan view.
- Keep `session_id` recovery in `localStorage`.

- [ ] Add a Node smoke test for the API request sequence.
- [ ] Run it and confirm the new plan flow is not wired.
- [ ] Update frontend API calls and render the real response.
- [ ] Run Node tests and serve the frontend locally.
- [ ] Commit `feat: align frontend with integrated mvp api`.

### Task 4: End-to-End Verification

**Files:**
- Modify: `README.md`
- Modify: `.env.example`
- Create: `tests/live_core_flow.ps1`

- [ ] Run Python unit and integration tests against PostgreSQL.
- [ ] Check `/openapi.json` and verify all core endpoints.
- [ ] Run the live PowerShell flow from session creation to delivery.
- [ ] Start backend and frontend locally and verify both URLs.
- [ ] Commit `docs: document local mvp integration environment`.

