# Task 2 Report: Anonymous Testing Telemetry Persistence

## Changed Files

- `test_observability.py`
  - Adds `TestObservabilityService` for anonymous test-user identification,
    allowlisted event persistence, idempotent event writes, feedback upserts,
    and deletion of observability data.
  - Uses `psycopg.connect(..., row_factory=dict_row)`, `Jsonb`, and
    parameterized SQL for every database write.
- `tests/test_test_observability.py`
  - Adds controlled database-boundary tests for anonymous identifier
    validation, event and reason allowlists, metadata filtering, idempotency,
    rating and comment bounds, feedback updates, and anonymous data deletion.

## Commit

- `882206d feat: persist anonymous testing telemetry`

## Verification

- RED: `uv --cache-dir .uv-cache run --with 'psycopg[binary]>=3.3,<3.4' python -m unittest tests.test_test_observability -v`
  - Failed as expected before implementation with
    `ModuleNotFoundError: No module named 'test_observability'`.
- PASS: `uv --cache-dir .uv-cache run --with 'psycopg[binary]>=3.3,<3.4' python -m unittest tests.test_test_observability -v`
  - 7 tests passed.
- PASS: `uv --cache-dir .uv-cache run --with 'psycopg[binary]>=3.3,<3.4' python -m unittest tests.test_test_observability tests.test_database_migrations -v`
  - 12 tests passed.
- PASS: `git diff --check`
  - Exit code 0 before commit.
- Attempted: `uv --cache-dir .uv-cache run --with 'psycopg[binary]>=3.3,<3.4' python -m unittest discover -s tests -p 'test_*.py'`
  - Produced no output for 31 seconds and was stopped. This matches Task 1's
    recorded external database-connection blocking behavior.

## Environment Limits and Follow-up Risk

- The test suite replaces only the `psycopg.connect` boundary with a controlled
  in-memory double. It exercises the real service validation, SQL selection,
  parameter values, `Jsonb` usage, and returned-payload behavior, but it is not
  a substitute for PostgreSQL constraint, transaction, or concurrent UPSERT
  verification.
- Real PostgreSQL was not contacted: the configured connection previously did
  not respond, and the full test discovery again blocked without output.
  Before enabling telemetry, run the Task 2 suite and an integration flow
  against an independent PostgreSQL test database after applying migrations.
- Existing untracked `.superpowers/sdd` artifacts and `.superpowers/sdd-tools`
  were left untouched; they predate Task 2 and are not part of the commit.

## Review Follow-up: Anonymous Telemetry Constraints

### Fixes

- Anonymous IDs now accept only `student_` followed by 3-6 digits, such as
  `student_001`. Cohort validation is unchanged and still accepts
  `student_2026_09`.
- `record_event` and `save_feedback` update `test_users.last_seen_at` through
  the same connection context as their respective writes.
- The controlled database boundary now enforces the `test_users` foreign-key
  contract. Successful event and feedback tests identify the user first, and
  separate tests confirm that an unidentified user raises
  `ForeignKeyViolation` rather than appearing to persist successfully.
- Database write errors intentionally propagate from this storage layer. The
  later API can catch them to make telemetry non-blocking while validation
  errors remain explicit to the caller.

### Commit

- `fix: harden anonymous telemetry constraints`

### Verification

- RED: the expanded Task 2 test suite failed for name-like and formatted-phone
  IDs, an old duplicate-event fixture that violated the real foreign-key
  contract, and the missing feedback `last_seen_at` update.
- PASS: `uv --cache-dir .uv-cache run --with 'psycopg[binary]>=3.3,<3.4' python -m unittest tests.test_test_observability -v`
  - 9 tests passed.
- PASS: `uv --cache-dir .uv-cache run --with 'psycopg[binary]>=3.3,<3.4' python -m unittest tests.test_database_migrations -v`
  - 5 migration regression tests passed.
- Attempted: `uv --cache-dir .uv-cache run --with 'psycopg[binary]>=3.3,<3.4' python -m unittest discover -s tests -p 'test_*.py'`
  - Produced no output after 30 seconds and was stopped, consistent with the
    pre-existing external database-connection blocking behavior.
- PASS: `git diff --check`

### Limitations

- The controlled `psycopg` boundary exercises validation, SQL order,
  parameterized writes, and error propagation, but does not replace PostgreSQL
  integration coverage for transaction rollback or concurrent UPSERT behavior.
- Run Task 2 against an independent PostgreSQL test database before enabling
  telemetry API endpoints.
