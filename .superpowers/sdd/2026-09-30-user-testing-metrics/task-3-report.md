# Task 3 Report: Admin Authentication and Metrics Aggregation

## Changed Files

- `admin_metrics_service.py`
  - Completes the database context normally before returning the uniform
    `PermissionError`, so failed-login counters and lockouts commit instead of
    rolling back.
  - Retains the transaction-scoped advisory lock, one-admin constraint,
    UTF-8 constant-time failure handling, and `ANY(%s)` list binding.
  - Limits full-flow success to distinct `session_created` sessions in the
    denominator and distinct `feedback_submitted` sessions in the numerator.
  - Scopes summary and recommendation ratings by `task_test_feedback.created_at`
    and de-duplicates feedback by plan item before averaging.
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
    date bounds, full-flow event types, uneven event counts, and empty metrics.
- `tests/test_database_migrations.py`
  - Covers the ordered 003 upgrade, original 002 contract, replay safety, and
    applying 003 exactly once after version 002 is already recorded.

## Commits

- `47cef5b fix: correct admin metrics transactions and migrations`

## Verification

- PASS: controlled psycopg-boundary `tests.test_admin_metrics` (12 tests).
- PASS: controlled psycopg/FastAPI-boundary `tests.test_database_migrations`
  (7 tests) and Task 2 `tests.test_test_observability` regression (9 tests).
- PASS: `py_compile` for Task 3 service, migration runner, Task 2 service, and
  their tests.
- PASS: `git diff --check` before the code-fix commit.

## Environment Limits

- The available Python runtime does not include `psycopg` or `fastapi`, so the
  controlled unit tests inject only the minimal module names needed to exercise
  the repository's existing connection fakes. Direct test collection cannot
  start without those dependencies.
- No real PostgreSQL instance is available. The following remain unverified:
  executing fresh 002 then 003, applying 003 after recorded 002, PostgreSQL's
  partial unique-index behavior on pre-existing rows, advisory-lock behavior,
  psycopg array adaptation, JSONB aggregation, and timestamp filtering.
