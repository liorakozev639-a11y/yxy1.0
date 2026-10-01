# Task 6 Final Review Fix Report

## Status

Implemented all four Important final-review findings without changing recommendation, scheduling, execution, or other core business decisions. The fixes remain limited to anonymous observation storage, its admin boundary, migration safety, the admin dashboard, tests, and documentation.

## Findings fixed

1. **Immutable cohort attribution**
   - `TestObservabilityService.identify()` now preserves the first stored cohort for an existing `anonymous_id`; re-identification only refreshes `last_seen_at` and clears a prior soft-delete marker.
   - Added regression coverage for a second identification with a different cohort.

2. **Anonymous-scoped event idempotency**
   - Fresh schema creation now uses the composite unique index `(anonymous_id, idempotency_key)`.
   - Migration `004_user_testing_retention_and_idempotency.sql` removes the legacy global idempotency constraint, creates the scoped index repeat-safely, and adds the retention lookup index.
   - Service conflict handling uses the same composite key, preserving same-user retries while allowing different anonymous users to reuse a key.
   - Added service, migration, and frontend key-scope regression coverage.

3. **Complete control-character rejection**
   - Observation text validation rejects every Unicode character in category `Cc`, covering ASCII controls, C1 controls, and the remaining Unicode control characters rather than only newline, carriage return, tab, and NUL.
   - Applied to anonymous IDs, cohorts, optional observation IDs, comments, metadata text, and idempotency keys. Admin metric filters use the same category-based rule; allowlisted reason codes reject control-bearing values by construction.
   - Added coverage across identity fields, comments, reason strings, metadata text, filters, and idempotency keys.

4. **90-day retention and authenticated deletion**
   - Added `TestObservabilityService.delete_expired_data()` with a 90-day cutoff based on `last_seen_at`. It deletes only `test_users`, allowing the existing foreign-key cascades to remove `test_events` and `task_test_feedback` while leaving business tables untouched.
   - Added authenticated `DELETE /api/v1/admin/test-users/{anonymous_id}` for explicit per-user removal.
   - Added authenticated `POST /api/v1/admin/test-observations/cleanup` for the documented manual 90-day cleanup path because this app has no background scheduler.
   - Added confirmation controls and API methods to the isolated admin dashboard.
   - Updated README, the metrics guide, and the SDD progress line to describe the actual 90-day/manual deletion behavior.

## Constraints checked

- No AI logic, personal identity fields, recommendation rules, similar-task exclusion, scheduling, execution, or normal business feedback behavior was changed.
- Observation write failures remain non-blocking through the existing `observe()` wrapper.
- Admin authentication continues to run through the existing `require_admin()` boundary.
- Explicit delete and cleanup routes require a valid bearer administrator token before invoking the observation service.
- Migrations are versioned and replay-safe; the compatibility migration handles databases that already applied the old global idempotency constraint.

## Verification

The red-to-green focused runs were observed before this report was finalized:

| Command | Result |
| --- | --- |
| `uv --cache-dir .uv-cache run --offline python -m unittest tests.test_test_observability tests.test_admin_metrics tests.test_database_migrations tests.test_testing_api -v` | **PASS**, 44 tests, 0 failures |
| `node --test tests/frontend-testing.test.js tests/frontend-api.test.js` | **PASS**, 21 tests, 0 failures |
| `uv --cache-dir .uv-cache run --offline python -m py_compile main.py test_observability.py admin_metrics_service.py` | **PASS**, exit code 0 |
| `git diff --check` | **PASS**, exit code 0; Git emitted only existing LF-to-CRLF normalization warnings |

Relevant regression checks also passed:

| Command | Result |
| --- | --- |
| `uv --cache-dir .uv-cache run --offline python -m unittest tests.test_database_migrations tests.test_test_observability tests.test_admin_metrics tests.test_testing_api tests.test_vercel_entry -v` | **PASS**, 45 tests, 0 failures |
| `node --test tests/frontend-testing.test.js tests/frontend-api.test.js` | **PASS**, 21 tests, 0 failures |
| `node --test tests/*.test.js` | **87 passed, 1 failed**. The only failure is environment-dependent `tests/deploy-config.test.js`, which tries to spawn the absent `D:\yxy1.0\\.worktrees\\user-testing-metrics\\.venv\\Scripts\\python.exe` (`ENOENT`). |

The configured PostgreSQL instance at `127.0.0.1:5433` was unavailable in the prior task verification, so live migration execution, PostgreSQL cascade behavior, and live dashboard deletion remain environment-dependent concerns rather than claimed passes.
