# Task 1 - Domain contracts and validation

## Scope

Adapt the first task in `outputs/free-time-agent-implementation-plan.md` to this existing plain JavaScript prototype. Do not create a TypeScript build or start later tasks.

## Required behavior

- Add reusable domain constants and validators for questions, tasks, user preferences, and plan items.
- Deep questionnaire scale must be exactly: `非常同意`, `比较同意`, `不太同意`, `完全不同意`.
- Validate question mode and reverse-scoring metadata.
- Validate task direction, duration, budget, outing mode, and company mode where supplied.
- Validate plan item start/end ordering and reject overlap with existing plan items.
- Preserve existing exports and behavior in `logic.js`.

## Implementation constraints

- Use the current CommonJS/browser-compatible style in `logic.js`, unless a small plain-JS module clearly fits better.
- Add focused tests to `tests/logic.test.js` or another test file supported by the current test command.
- Follow test-first development: add failing assertions before implementation, then run the focused and full tests.
- Do not modify unrelated UI behavior and do not implement questionnaire sessions or recommendations yet.

## Required report

Write `work/sdd/free-time-agent-implementation-plan/task-1-report.md` with changed files, tests run, results, and any concerns. No Git commit is required.
