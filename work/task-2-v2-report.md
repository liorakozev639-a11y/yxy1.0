# Task 2 V2 Report

Date: 2026-08-01

## Scope

Implemented only Demo V2 Task 2 for `outputs/free-time-agent-demo-v2/`:

- local generic activity library
- filtering logic
- recommendation ranking and fallback filling
- recommendation-stage preview wiring in `app.js`

Not implemented:

- questionnaire generation or UI flow
- schedule/planning helpers
- execution or adjustment modules
- any root-level prototype changes

## Changes

### `outputs/free-time-agent-demo-v2/logic.js`

- kept browser + CommonJS dual export through `window.FreeTimeDemoV2` and `module.exports`
- expanded initial preference state with Task 2 fields:
  - `outing`
  - `company`
  - `budget`
  - `duration`
  - `restFirst`
- added `getActivityLibrary()`
- added `filterActivities(preferences)`
- added `recommendActivities(preferences, answers, count = 10)`
- added a built-in library of 21 generic activities across:
  - `energy`
  - `calm`
  - `social`
  - `explore`
  - `growth`
- ensured activities do not include specific merchants, distances, prices, or business hours
- implemented ranking rules that prioritize:
  - selected categories
  - matching outing/company/budget/duration
  - `restFirst` low-pressure activities
  - questionnaire answer boosts when present
- tightened fallback behavior so recommendation filling only relaxes `selectedCategories`
- kept `outing`, `company`, `budget`, and `duration` as hard constraints during fallback
- preserved metadata semantics:
  - `totalMatches` remains the count before category-relaxed fallback
  - `fallbackUsed` remains true when the first-pass category-constrained result is smaller than the requested count
- returns short `matchReason` text for each recommendation
- defaults recommendation count to 10 when enough hard-constrained candidates exist
- returns fewer than 10 when the hard constraints themselves leave too few valid activities

### `outputs/free-time-agent-demo-v2/app.js`

- kept the standalone browser bootstrap intact
- added lightweight recommendation preview rendering for `state.candidates`
- added `setCandidates()` on `window.FreeTimeDemoV2` for browser-side inspection during later tasks

### `tests/demo-v2-logic.test.js`

- added Node built-in `node:test` + `assert/strict` coverage for:
  - activity library size and category coverage
  - generic-content constraints
  - filtering by category / outing / company / budget / duration
  - default 10-result recommendations
  - recommendation membership from built-in library
  - returned matching reasons
  - `restFirst` ordering
  - category-first ranking before fallback fill
  - boundary behavior where fallback may relax category but must not relax hard constraints

### `tests/demo-v2-smoke.test.js`

- updated the smoke/runtime contract to match valid Task 2 exports
- kept coverage for:
  - standalone bundle files
  - local script wiring
  - `window.FreeTimeDemoV2` browser exposure
  - CommonJS export surface
  - `createInitialState()` default preference fields
  - `renderStage()` welcome-stage behavior

## TDD Notes

- wrote `tests/demo-v2-logic.test.js` first
- verified the red state with:
  - `node tests/demo-v2-logic.test.js`
- observed the expected red state for this review round after adding the fallback boundary test
- then implemented the minimal production change to satisfy the new tests without widening scope

## Verification

Passed:

- `node tests/demo-v2-smoke.test.js`
- `node tests/demo-v2-logic.test.js`
- `node tests/logic.test.js`
- `node --check outputs/free-time-agent-demo-v2/logic.js`
- `node --check outputs/free-time-agent-demo-v2/app.js`

## Notes

- existing root `logic.js` and `tests/logic.test.js` behavior remained unchanged
- this task intentionally stops before questionnaire, planning, and execution features
