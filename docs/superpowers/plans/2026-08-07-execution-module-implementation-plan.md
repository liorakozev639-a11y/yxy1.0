# Execution Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add a synchronous Python Execution Module, document its complete MVP workflow, and publish only the related changes to the existing `main` branch.

**Architecture:** Keep execution logic independent from FastAPI and PostgreSQL at the domain layer. The module accepts a plan item, validates time and state transitions, records immutable execution events, and returns the updated item. The MVP document will describe the PostgreSQL transaction/API integration without adding MQ or asynchronous workers.

**Tech Stack:** Python 3.12+, standard-library `dataclasses` and `datetime`, `unittest`, Markdown, Git.

## Global Constraints

- Work directly on `main`; do not create a worktree.
- Do not modify unrelated existing changes in `main.py`, `session_module.py`, or `task_repository.py`.
- Keep the Execution Module synchronous and independent of MQ, Redis, Celery, and an LLM.
- Use the statuses `pending`, `active`, `completed`, `skipped`, `missed`, `overdue`, and `needs_adjustment`.
- Use the database server time supplied by the service layer for timeout decisions.
- Record every accepted or automatic status change as an execution event.

---

### Task 1: Define execution state behavior with tests

**Files:**
- Create: `tests/test_execution_module.py`

**Interfaces:**
- Consumes: `PlanItem`, `ExecutionEvent`, `execute_action`, `expire_if_needed`.
- Produces: executable coverage for normal actions, automatic timeout, invalid transitions, and event recording.

- [ ] **Step 1: Write tests for start and complete.**

```python
item = make_item()
execute_action(item, "start", at("14:05"))
assert item.status == "active"
execute_action(item, "complete", at("14:30"))
assert item.status == "completed"
assert [event.event_type for event in item.events] == ["started", "completed"]
```

- [ ] **Step 2: Write tests for missed and overdue tasks.**

```python
pending = make_item()
execute_action(pending, "start", at("14:41"))
assert pending.status == "needs_adjustment"
assert pending.events[-1].event_type == "missed"

active = make_item()
execute_action(active, "start", at("14:05"))
execute_action(active, "complete", at("14:41"))
assert active.status == "needs_adjustment"
assert active.events[-1].event_type == "overdue"
```

- [ ] **Step 3: Write tests for invalid transitions and skip.**

```python
item = make_item()
with self.assertRaises(ExecutionError):
    execute_action(item, "complete", at("14:05"))

item = make_item()
execute_action(item, "skip", at("14:05"))
assert item.status == "needs_adjustment"
assert item.events[-1].event_type == "skipped"
```

- [ ] **Step 4: Run the focused tests and confirm the missing-module failure.**

Run: `python -m unittest tests.test_execution_module -v`

Expected before implementation: import failure because `execution_module.py` does not exist.

### Task 2: Implement the standalone execution module

**Files:**
- Create: `execution_module.py`

**Interfaces:**
- Produces `PlanItem`, `ExecutionEvent`, `ExecutionError`, `expire_if_needed`, `execute_action`, and `demo`.

- [ ] **Step 1: Add immutable event data and mutable execution item data.**

```python
@dataclass(frozen=True, slots=True)
class ExecutionEvent:
    item_id: str
    event_type: str
    from_status: str
    to_status: str
    occurred_at: datetime

@dataclass(slots=True)
class PlanItem:
    id: str
    title: str
    start_at: datetime
    end_at: datetime
    status: str = "pending"
    events: list[ExecutionEvent] = field(default_factory=list)
```

- [ ] **Step 2: Implement automatic timeout handling.**

Use `current >= end_at`. A pending task becomes `needs_adjustment` with event type `missed`; an active task becomes `needs_adjustment` with event type `overdue`.

- [ ] **Step 3: Implement explicit actions.**

Allow `pending -> active`, `active -> completed`, and `pending/active -> needs_adjustment` through `skip`. Reject all other actions with `ExecutionError`.

- [ ] **Step 4: Add a runnable demo.**

The demo must print one successful start/complete flow and one automatic missed flow using timezone-aware UTC datetimes.

- [ ] **Step 5: Run the focused tests and demo.**

Run: `python -m unittest tests.test_execution_module -v`

Run: `python execution_module.py`

Expected: all tests pass and the demo prints `completed` for the first item and `needs_adjustment`/`missed` for the late item.

### Task 3: Replace the MVP Execution Module document section

**Files:**
- Modify: `outputs/空闲时间规划Agent-MVP-后端技术方案-工作流与示例.md`, section 9

**Interfaces:**
- Consumes: public types and functions from `execution_module.py`.
- Produces: module responsibility, state machine, synchronous workflow, database transaction contract, API response examples, complete runnable implementation, and acceptance criteria.

- [ ] **Step 1: Document the boundary with Scheduling Module.**

Explain that Scheduling creates `PlanItem` time windows while Execution changes status and records events.

- [ ] **Step 2: Document state transitions and timeout rules.**

Include the seven statuses, allowed actions, server-time rule, and `needs_adjustment` behavior.

- [ ] **Step 3: Embed the complete runnable Python module.**

Copy the verified `execution_module.py` implementation into the section without truncating imports or the demo entry point.

- [ ] **Step 4: Document PostgreSQL transaction and API integration.**

Include `SELECT ... FOR UPDATE`, the `plan_items` update, the `execution_events` insert, commit behavior, and example success/timeout JSON responses.

### Task 4: Verify, commit, and publish

**Files:**
- Verify: `execution_module.py`
- Verify: `tests/test_execution_module.py`
- Verify: `outputs/空闲时间规划Agent-MVP后端技术方案-工作流与示例.md`

- [ ] **Step 1: Run focused tests, full Python tests, and compile checks.**

Run: `python -m unittest tests.test_execution_module -v`

Run: `python -m unittest discover -s tests -p "test_*.py"`

Run: `python -m py_compile execution_module.py`

- [ ] **Step 2: Confirm only intended files are staged.**

Run: `git status --short` and stage only the new module, focused test, and updated MVP document. Leave existing modifications untouched.

- [ ] **Step 3: Commit on main.**

Run: `git commit -m "feat: add execution module"`

- [ ] **Step 4: Push main to origin.**

Run: `git push origin main`

Expected: the new commit is visible in `https://github.com/liorakozev639-a11y/yxy1.0`.
