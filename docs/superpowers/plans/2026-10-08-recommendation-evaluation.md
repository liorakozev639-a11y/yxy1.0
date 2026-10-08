# Recommendation Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a reproducible 50-case offline evaluation of full and quick recommendations, including hard constraints, repetition, reason consistency, and a manual review sheet.

**Architecture:** A declarative JSON fixture feeds a Python evaluator that calls the existing candidate provider and rankers without database access. The evaluator writes JSON metrics and a CSV review sample; focused tests prove the metric denominators and error behavior.

**Tech Stack:** Python standard library, existing task repository/candidate provider/recommendation modules, unittest.

**Spec:** `docs/superpowers/specs/2026-10-08-recommendation-evaluation-design.md`

## Global Constraints

- Exactly 50 explicit cases: 30 full and 20 quick.
- No API, PostgreSQL, model key, or frontend dependencies.
- Energy is a ranking preference, not a hard filter.
- Keep current API response shape and business flow unchanged unless a real evaluation failure requires a focused fix.
- Report numerators and denominators; an undefined rate is `null`.

## Review Focus

- Expected empty pool: passes the constraint opportunity without inventing a task; unexpected empty pool fails.
- Duplicate task IDs: count both intra-response duplication and repeated prior IDs during replacement.
- Missing reason: contributes a failed reason check.
- Invalid case data: fails fast and identifies the case ID.
- Empty manual-review candidates: output an explicit shortage rather than claiming ten reviewed examples.

---

### Task 1: Fixture and validation

**Files:** Create `data/recommendation_evaluation_cases.json`, `recommendation_evaluation.py`, `tests/test_recommendation_evaluation.py`.

**Interfaces:** `load_cases(path: Path) -> list[dict[str, Any]]` validates exact 50 cases, unique IDs, supported modes/fields and 30/20 split.

- [x] Write failing tests for 50/30/20, duplicate ID and invalid case reporting.
- [x] Run `python -m unittest tests.test_recommendation_evaluation -v` and confirm the expected failure.
- [x] Add the fixed fixture and minimal loader/validator.
- [x] Run the focused tests and confirm pass.

### Task 2: Execute existing recommenders and score results

**Files:** Modify `recommendation_evaluation.py`; test `tests/test_recommendation_evaluation.py`.

**Interfaces:** `evaluate_case(case: dict[str, Any], provider: TaskBankProvider) -> dict[str, Any]`; `summarize(results: list[dict[str, Any]]) -> dict[str, Any]`.

- [x] Write failing tests for full and quick execution, expected and unexpected empty, constraint counts, repeated IDs, missing/contradictory reasons, zero denominators.
- [x] Run the focused test file to verify failure.
- [x] Implement provider/ranker calls and independent checks against returned task fields and input constraints.
- [x] Run focused tests and the 50-case evaluator; save the first baseline report before any recommendation fix.

### Task 3: Repair verified failures and deliver reports

**Files:** Modify only implicated recommendation modules/tests, plus `recommendation_evaluation.py`; create `docs/recommendation-evaluation.md` and report files.

**Interfaces:** `python -m recommendation_evaluation --output <path> --review <path>` writes JSON report and CSV; exits nonzero for evaluation violations.

- [x] Inspect baseline by case and add a regression test for any verified product defect (none found).
- [x] Make focused fixes, or record explicitly if no defect is found (evaluator sampling fixed; production unchanged).
- [x] Rerun the same 50 cases and preserve baseline/final JSON, plus ten-item review CSV.
- [x] Run targeted recommendation tests and `git diff --check`.
- [x] Document commands and metric limits; inspect generated artifact contents.
