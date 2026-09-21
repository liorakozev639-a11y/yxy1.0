# Mock Task Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the full task-generation-to-execution workflow without an AI key or token spend.

**Architecture:** `TASK_GENERATION_MODE=mock` selects a deterministic two-stage generator. It reads saved session/questionnaire/profile evidence, validates a structured brief and candidate tasks, persists generated tasks, then uses existing scheduling, plan, delivery, execution and feedback services. The default mode remains the existing public-task flow.

**Tech Stack:** Python 3.14, FastAPI, psycopg/PostgreSQL, plain JavaScript, unittest, Node test runner.

**Spec:** `docs/AI智能任务生成前后端技术方案.md` (sections 3-11); mock mode is a test implementation, not real AI.

## Global Constraints

- Never expose mock output as a real model result; production default is the current rule-based flow.
- Mock generation, replacement and adjustment cannot query the public task bank.
- Every accepted task has a concrete first action, prerequisites, two explanations and verified evidence references.
- Hard constraints and prior task identities cannot be relaxed by the generator.
- Preserve unrelated dirty working-tree changes; stage only feature files/hunks.

---

### Task 1: Contracts and deterministic generation

**Files:** Create `mock_task_generation.py`; test `tests/test_mock_task_generation.py`.

**Interfaces:** `build_context(session, questionnaire, questions, answers, profile, request, excluded)` returns source-indexed context. `MockTaskGenerator.write_brief(context)` returns requirements with source references. `MockTaskGenerator.generate_tasks(context, brief, count, excluded_signatures)` returns candidate dictionaries. `validate_brief` and `validate_candidates` accept only supported categories, true evidence IDs, safe actions and hard-constraint-compliant, distinct tasks.

- [x] Write tests that a skipped answer is not treated as a preference and that a fabricated `evidence_ref` is rejected.
- [x] Run `python -m unittest discover -s tests -p test_mock_task_generation.py -v`; verify the tests fail because the implementation is missing.
- [x] Implement the smallest deterministic generator and validators; include fixtures for over-budget, duplicate and invented-evidence responses.
- [x] Run the same tests and inspect the output.

### Task 2: Durable generated tasks and initial plan

**Files:** Create `generated_task_repository.py`; modify `mvp_orchestrator.py` and `main.py`; test `tests/test_mock_orchestrator.py`.

**Interfaces:** Repository `save_tasks(session_id, generation_key, brief, tasks)` and `list_tasks(session_id)`; `MVPOrchestrator` takes an optional mock generation service. `generate_plan` preserves the existing `profile`, `recommendation`, `plan`, `delivery` envelope and task IDs.

- [x] Write a failing orchestration test: 10 generated tasks have evidence and no old-bank ID; invalid candidates are never scheduled.
- [x] Run the focused test and confirm the intended failure.
- [x] Add PostgreSQL schema and a mock-mode branch that uses accepted generated tasks, then checks scheduled total budget.
- [x] Run focused tests plus the existing MVP integration test and review the diff.

### Task 3: Plan mutations and explanation UI

**Files:** Modify `plan_module.py`, `mvp_orchestrator.py`, `frontend/flow.js`, `frontend/app.js`; test `tests/test_mock_plan_flow.py`, `tests/frontend-flow.test.js`.

**Interfaces:** The plan manager resolves mock task IDs through the generated-task repository. Replacement/adjustment requests generate a new validated candidate that excludes current and historical identities; adding a recommended task resolves its persisted ID. Existing execution/feedback endpoints remain unchanged.

- [x] Write failing tests for repeated replacement, adjustment, adding a recommendation and evidence display.
- [x] Run the focused Python and Node tests to observe expected failure.
- [x] Implement mock-mode paths and clearly mark simulation in the result UI; keep the legacy branch unchanged.
- [x] Run focused tests and review each changed branch before committing.

### Task 4: Full verification and deployment

**Files:** Update `README.md` with local mock-mode run/test instructions; add focused API smoke coverage if the database is available.

- [x] Run Python unit/integration tests, Node tests and a local API/DB workflow: create session, answer questionnaire, generate, replace, add, start, finish and feedback.
- [x] Inspect `git diff --check`, `git status`, schema changes, error paths and the final response contract.
- [ ] Commit only this feature's files or hunks, push to `origin/main`, and verify Vercel's new deployment and `/health` response.
- [ ] Report any checks that could not be run. No claim of live mock results: Vercel remains in default rule-based mode unless explicitly configured otherwise.
