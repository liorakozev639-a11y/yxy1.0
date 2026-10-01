# SDD ledger — plan: docs/superpowers/plans/2026-09-30-user-testing-metrics.md

## Preflight scan

| Scope | Producer / consumer | Finding | Ruling |
|---|---|---|---|
| Task 1 / Task 2 | Migration tables / `TestObservabilityService` | Task 1 creates the tables and constraints that Task 2 writes. Names and rating/reason constraints match. | Proceed in order. |
| Task 1 / Task 3 | Migration tables / `AdminMetricsService` | Task 3 reads the same tables created by Task 1 and may read only necessary business fields. | Proceed in order. |
| Task 1 / Task 4 | Migration tables / FastAPI services | Task 4 depends on the storage and admin tables but does not alter migration behavior. | Proceed in order. |
| Task 2 / Task 4 | `TestObservabilityService` / observation routes | Task 4 consumes the exact Task 2 method signatures. | Proceed in order. |
| Task 3 / Task 4 | `AdminMetricsService` / admin routes | Task 4 consumes the exact Task 3 authentication and metric method signatures. | Proceed in order. |
| Task 4 / Task 5 | FastAPI endpoints / frontend API calls | Task 5 calls only the endpoints defined by Task 4; event failures are non-blocking. | Proceed in order. |
| Task 5 / Task 6 | Frontend files / final docs and tests | Task 6 validates the completed frontend surface and documents the same commands. | Proceed in order. |
| Task 1 | Own tests and migration file | Migration tests assert tables, indexes, constraints, and repeatability; implementation creates those exact objects. | Internally consistent. |
| Task 2 | Own service and tests | Tests cover all validation and idempotency rules named by the service interfaces. | Internally consistent. |
| Task 3 | Own service and tests | Tests cover authentication lifecycle and all five metric methods. | Internally consistent. |
| Task 4 | Own routes and tests | Tests cover validation, auth, duplicate events, and non-blocking failures. | Internally consistent. |
| Task 5 | Own frontend files and tests | Tests cover local anonymous identity, event hooks, feedback, and dashboard requests. | Internally consistent. |
| Task 6 | Own docs and final checks | Documentation follows the implemented commands and final checks do not mutate business behavior. | Internally consistent. |

No plan conflicts or plan-mandated defects found during preflight. The plan's six tasks are sequential because Tasks 2-5 consume interfaces created earlier.

## Decisions

Ruling: use a linked worktree at `.worktrees/user-testing-metrics` — required by the selected subagent-driven workflow and protects the user's dirty main checkout; cost if wrong is an extra integration step at finish.

## Task status

- Task 1: complete — implementation commits `7048f37` and `719125d`; task review verdict `CLEAN`. The migration unit suite passed 5 tests. Real PostgreSQL double-run remains unverified because the available database connection did not respond.
- Task 2: complete — implementation commits `882206d`, `4f1293b`, and `6cec3e8`; final task review verdict `CLEAN`. The observability and migration regression suite passed 14 tests. Real PostgreSQL FK/CHECK/CASCADE/transaction/concurrency behavior remains unverified.
- Task 3: complete — implementation commits `251db15`, `f095882`, `7010bb3`, `47cef5b`, `8540a8b`, and `0d6688f`; final task review verdict `CLEAN`. Task 3, migration, and Task 2 regression suites passed 28 tests in total. Real PostgreSQL JSONB/array/timezone/transaction/concurrency behavior remains unverified.
- Task 4: complete — implementation commits `d6cc7da` and `f4c5354`; task review findings addressed and scoped re-review clean. Focused API and Task 2–4 regression suites passed 37 tests; full discovery and real PostgreSQL integration remain blocked by unavailable database.
- Task 5: complete — implementation commits `b79b5a4`, `491110e`, and `067de93`; task review findings addressed and final scoped re-review clean. Focused frontend suite passed 10 tests and existing frontend regression suite passed 28 tests; live browser/PostgreSQL E2E remains unverified.
- Task 6: complete — prior documentation and static checks were delivered; the retention wording and deletion workflow were corrected in this final review fix pass.
- Final review fixes: complete — immutable cohort attribution, anonymous-scoped event idempotency, full `Cc` control-character rejection, and authenticated 90-day observation deletion/cleanup are covered by focused regression tests. Live PostgreSQL migration execution remains unverified because the configured database is unavailable.
