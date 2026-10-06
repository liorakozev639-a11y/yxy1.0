# Task 3 Report: Admin Authentication and Metrics Aggregation

## Changed Files

- `admin_metrics_service.py`
  - Completes the database context normally before returning the uniform
    `PermissionError`, so failed-login counters and lockouts commit instead of
    rolling back.
  - Retains the transaction-scoped advisory lock, one-admin constraint,
    UTF-8 constant-time failure handling, and `ANY(%s)` list binding.
  - Builds the full-flow denominator from the filtered distinct
    `session_created` sessions and only counts filtered `feedback_submitted`
    sessions that join that set; the returned rate has a defensive 100% cap.
  - Scopes summary and recommendation ratings directly from
    `task_test_feedback.created_at`, cohort, and anonymous ID. Category lookup
    is independent of the event date window, and each plan item contributes one
    rating; feedback without a category event remains visible as `unknown`.
  - Returns the approved funnel payload contract:
    `{"steps": [{"event_type": ..., "count": ...}]}`.
- `migrations/002_user_testing_metrics.sql`
  - Restored to the original Task 1 observability schema so that its already
    published version remains stable.
- `migrations/003_admin_security_upgrade.sql`
  - Adds `failed_login_count`, `locked_until`, and the one-admin partial unique
    index using replay-safe statements for both fresh databases and databases
    that already recorded migration 002.
- `tests/test_admin_metrics.py`
  - Models transaction commit and rollback at the psycopg boundary; covers
    lockout in the original and a newly constructed service instance, feedback
    date bounds, full-flow session intersection and upper bound, cross-window
    feedback facts, unwindowed category mapping, funnel contract, uneven event
    counts, and empty metrics.
- `tests/test_database_migrations.py`
  - Covers the ordered 003 upgrade, original 002 contract, replay safety, and
    applying 003 exactly once after version 002 is already recorded.

## Commits

- `47cef5b fix: correct admin metrics transactions and migrations`
- `fix: finalize admin metrics scope and contract` (this commit)

## Verification

- PASS: controlled psycopg-boundary `tests.test_admin_metrics` (12 tests).
- PASS: controlled psycopg/FastAPI-boundary `tests.test_database_migrations`
  (7 tests) and Task 2 `tests.test_test_observability` regression (9 tests).
- PASS: `py_compile` for `admin_metrics_service.py`, Task 3 tests,
  `test_observability.py`, Task 1/2 tests, and `migrate.py`.
- PASS: `git diff --check` before the final fix commit.

## Environment Limits

- No real PostgreSQL instance is available. The following remain unverified:
  executing the final summary/recommendation queries against PostgreSQL,
  timezone-aware timestamp filtering, JSONB category lookup, and the session
  intersection on production data. Controlled psycopg-boundary tests cover the
  query scope, parameter binding, and returned contracts without a database.
