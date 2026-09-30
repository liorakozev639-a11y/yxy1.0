# Task 1 Report: Database Migrations and Data Contract

## Changed Files

- `migrations/002_user_testing_metrics.sql`
  - Adds idempotent schema creation for `test_users`, `test_events`,
    `task_test_feedback`, `admin_users`, and `admin_sessions`.
  - Adds event and reason-code allowlists, rating bounds, idempotency and
    feedback uniqueness constraints, and dashboard query indexes.
- `tests/test_database_migrations.py`
  - Verifies migration order, the five-table data contract, required event
    types, rating/idempotency constraints, indexes, and replay-safe SQL
    statements through the existing migration statement splitter.

## Commit

- `7048f37 feat: add user testing metrics schema`

## Verification

- RED check: temporarily removing `002_user_testing_metrics.sql` produced the
  expected two assertion failures for the migration sequence and missing file;
  the file was restored immediately.
- PASS: `uv run --with 'psycopg[binary]>=3.3,<3.4' python -m unittest tests.test_database_migrations -v`
  - 4 tests passed.
- PASS: `git diff --check`
  - Exit code 0. Git reported only expected CRLF conversion warnings.
- Attempted: `uv run --with 'psycopg[binary]>=3.3,<3.4' python -m unittest discover -s tests -p 'test_*.py'`
  - Stopped after about two minutes without output; it appears blocked by an
    external database connection used by live tests.

## Environment Limits and Follow-up Risk

- The normal `python` command is unavailable. The `py` launcher points to a
  missing `C:\\Python314\\python.exe`; verification used `uv` instead.
- `SESSION_DATABASE_URL` is configured, but `uv run --with 'psycopg[binary]>=3.3,<3.4' python migrate.py`
  remained silent while connecting for about 90 seconds and was interrupted.
  Therefore, real PostgreSQL application of the migration twice, including
  checking `schema_migrations` idempotency, remains unverified.
- Before enabling the feature, run `python migrate.py` twice against a known
  independent PostgreSQL test database and confirm both commands complete.

## Review Fix Follow-up

- `migrations/002_user_testing_metrics.sql`
  - Adds the idempotent `idx_test_users_cohort` index on `test_users(cohort)`.
- `tests/test_database_migrations.py`
  - Covers every approved `reason_code` value and the nullable `reason_code`
    CHECK constraint.
  - Verifies each testing-metrics index by its table and indexed columns.
  - Uses a controlled in-memory connection double for `psycopg.connect` to run
    the real `database_migrations.run_migrations()` implementation twice. It
    verifies that 002 SQL and its `schema_migrations` record execute once.

## Review Fix Verification

- PASS: `uv --cache-dir .uv-cache run --with 'psycopg[binary]>=3.3,<3.4' python -m unittest tests.test_database_migrations -v`
  - 5 tests passed.
- PASS: `git diff --check`
  - Exit code 0.

## Review Fix Commit

- `fix: strengthen testing metrics migration checks`

## Review Fix Limits

- The migration runner double deliberately replaces only the PostgreSQL
  connection boundary. It validates runner idempotency without representing a
  real PostgreSQL double-run.
- A real PostgreSQL double-run remains unverified because the configured
  database connection did not complete in the available environment. Run
  `python migrate.py` twice against an independent test database before
  enabling the feature.
