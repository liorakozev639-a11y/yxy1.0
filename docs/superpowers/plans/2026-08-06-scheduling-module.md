# Scheduling Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic, independently runnable Scheduling Module and document its complete MVP workflow.

**Architecture:** Keep scheduling as a pure synchronous domain module between Recommendation and Execution. The module receives already-filtered tasks, a free-time window, density, and locked plan items; it returns an immutable plan draft with scheduled items, a mandatory rest block, and unscheduled task IDs. API and PostgreSQL integration remain a separate follow-up.

**Tech Stack:** Python 3.12, standard-library `dataclasses`, `datetime`, `unittest`, Markdown.

## Global Constraints

- Work directly on `main`; do not create a worktree.
- Do not modify the existing dirty `task_repository.py`.
- Use `light`, `balanced`, and `full` density modes.
- Never overlap items or schedule outside the free-time window.
- Keep completed and explicitly locked items unchanged during replanning.
- Include at least one rest block or return an explicit scheduling error.
- Keep the module synchronous and independent of MQ, Redis, and an LLM.

---

### Task 1: Define scheduling behavior with tests

**Files:**
- Create: `tests/test_scheduling_module.py`

**Interfaces:**
- Consumes: `Task`, `PlanItem`, `build_schedule`, `replan`, `validate_time_change`.
- Produces: executable acceptance tests for density, rest, bounds, conflicts, and locked-item preservation.

- [ ] Write tests for balanced scheduling, density limits, mandatory rest, conflict validation, and replanning.
- [ ] Run `python -m unittest tests.test_scheduling_module -v` and verify failure because `scheduling_module` does not exist.

### Task 2: Implement the Scheduling Module

**Files:**
- Create: `scheduling_module.py`

**Interfaces:**
- Produces: `build_schedule(...) -> PlanDraft`, `replan(...) -> PlanDraft`, and `validate_time_change(...) -> tuple[datetime, datetime]`.

- [ ] Add immutable task, plan-item, density, and plan-draft data models.
- [ ] Add deterministic first-fit scheduling around locked intervals.
- [ ] Add density limits, buffers, mandatory rest insertion, and unscheduled IDs.
- [ ] Add conflict validation and replan behavior that preserves completed items.
- [ ] Add a runnable `demo()` entry point.
- [ ] Run the focused test and keep it green.

### Task 3: Document the complete module

**Files:**
- Modify: `outputs/空闲时间规划Agent-MVP-后端技术方案-工作流与示例.md` section 8.

**Interfaces:**
- Consumes: public interfaces from `scheduling_module.py`.
- Produces: module boundaries, data model, workflow, algorithm, API contract, persistence rules, runnable command, and acceptance criteria.

- [ ] Replace the minimal section with the complete workflow and code reference.
- [ ] Embed the complete runnable Python implementation in the section.

### Task 4: Verify and commit

**Files:**
- Verify: `scheduling_module.py`
- Verify: `tests/test_scheduling_module.py`
- Verify: backend documentation section 8.

- [ ] Run the standalone demo.
- [ ] Run all Python tests.
- [ ] Compile the module with `py_compile`.
- [ ] Confirm the document has no `TODO` or stale minimal-example wording.
- [ ] Stage only the scheduling module, its test, its documentation, and this plan.
- [ ] Commit with `feat: add scheduling module`.
