# Demo V2 Task 3 Report

Date: 2026-08-01

## Scope

Updated Task 3 in `outputs/free-time-agent-demo-v2/` to address the Task 3 review:

- Kept recommendation generation inside the existing logic-layer hard constraints
- Added an explicit questionnaire submit action before entering recommendations
- Hardened versioned localStorage payload validation
- Expanded Task 3 tests for the reviewed behaviors

Did not implement scheduling, execution, or Task 4/5 behavior.

## What Changed

### Questionnaire

- `createQuestionnaire(mode, selectedCategories)` remains in `logic.js`
- Quick mode returns 5 questions
- Deep mode returns 30 questions
- Every question still uses the fixed four-level scale and supports `reverse`

### Browser Flow

- Stage flow remains:
  - welcome
  - interests
  - conditions
  - questionnaire
  - recommendations
- Questionnaire now requires an explicit `生成推荐` submit button
- Reaching the last question no longer auto-navigates to recommendations
- Skipping the last question keeps the user on the questionnaire and allows explicit submit

### Recommendation Constraints

- Removed the app-layer fallback that progressively cleared:
  - `outing`
  - `company`
  - `budget`
  - `duration`
- Recommendation generation now only uses the existing `logic.recommendActivities(...)` behavior
- If hard constraints yield fewer than 10 results, the UI shows the actual count and explains that hard constraints were kept intact

### Persistence

- localStorage state is still versioned
- Valid saved state restores on reload
- Invalid JSON clears only the Demo V2 storage key
- Structurally invalid but JSON-valid state now also clears only the Demo V2 storage key
- Validation now checks the basic shape of:
  - `preferences`
  - `questionnaire`
  - `answers`
  - `currentIndex`
  - stage and collection fields

### Tests

- Updated `tests/demo-v2-questionnaire.test.js` to cover:
  - explicit submit before recommendations
  - last-question skip staying on questionnaire
  - hard-constraint preservation in recommendation results
  - structurally invalid saved state reset

## Verification

Ran on 2026-08-01:

- `node tests/demo-v2-smoke.test.js`
- `node tests/demo-v2-logic.test.js`
- `node tests/demo-v2-questionnaire.test.js`
- `node tests/logic.test.js`
- `node --check outputs/free-time-agent-demo-v2/app.js`
- `node --check outputs/free-time-agent-demo-v2/logic.js`
