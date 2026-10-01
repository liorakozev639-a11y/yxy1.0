from __future__ import annotations

import unittest
from unittest.mock import patch

from database_migrations import _statements, migration_files, run_migrations
from session_module import PostgresSessionRepository


class FakeConnection:
    def __init__(self) -> None:
        self.executions: list[tuple[str, object]] = []
        self.applied_versions: set[int] = set()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def cursor(self):
        return self

    def execute(self, statement, params=None):
        statement = str(statement)
        self.executions.append((statement, params))
        if "INSERT INTO schema_migrations" in statement:
            self.applied_versions.add(int(params[0]))
        return self

    def fetchall(self):
        return [(version,) for version in sorted(self.applied_versions)]


class DatabaseMigrationTests(unittest.TestCase):
    def test_migrations_are_versioned_and_cover_core_tables(self) -> None:
        files = migration_files()
        self.assertEqual(
            [path.name for path in files],
            [
                "001_initial_schema.sql",
                "002_user_testing_metrics.sql",
                "003_admin_security_upgrade.sql",
                "004_user_testing_retention_and_idempotency.sql",
            ],
        )
        sql = files[0].read_text(encoding="utf-8")
        for table in (
            "sessions",
            "questionnaires",
            "plans",
            "plan_items",
            "user_task_history",
            "quick_recommendation_runs",
            "task_feedback",
        ):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", sql)

    def test_user_testing_metrics_migration_defines_the_observability_contract(
        self,
    ) -> None:
        self.assertIn(
            "002_user_testing_metrics.sql",
            [path.name for path in migration_files()],
        )
        migration = next(
            path
            for path in migration_files()
            if path.name == "002_user_testing_metrics.sql"
        )
        sql = migration.read_text(encoding="utf-8")

        for table in (
            "test_users",
            "test_events",
            "task_test_feedback",
            "admin_users",
            "admin_sessions",
        ):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", sql)

        for event_type in (
            "session_created",
            "questionnaire_started",
            "questionnaire_completed",
            "recommendations_viewed",
            "task_started",
            "task_completed",
            "task_skipped",
            "task_replaced",
            "schedule_adjusted",
            "feedback_submitted",
            "flow_error",
        ):
            self.assertIn(f"'{event_type}'", sql)

        for reason_code in (
            "not_interested",
            "low_energy",
            "not_enough_time",
            "over_budget",
            "location_inconvenient",
            "too_difficult",
            "not_matching_current_state",
            "other",
        ):
            self.assertIn(f"'{reason_code}'", sql)

        self.assertIn("CHECK (rating BETWEEN 1 AND 5)", sql)
        self.assertIn(
            "CHECK (reason_code IS NULL OR reason_code IN (",
            sql,
        )
        self.assertIn(
            "reason_code IS NULL OR event_type IN ('task_skipped', 'task_replaced')",
            sql,
        )
        self.assertNotIn("UNIQUE (idempotency_key)", sql)
        self.assertIn(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_test_events_anonymous_idempotency",
            sql,
        )
        self.assertIn("ON test_events(anonymous_id, idempotency_key)", sql)
        self.assertIn("UNIQUE (plan_item_id)", sql)
        self.assertNotIn("failed_login_count", sql)
        self.assertNotIn("locked_until", sql)
        self.assertNotIn("idx_admin_users_single_admin", sql)

        expected_indexes = {
            "idx_test_users_cohort": "ON test_users(cohort)",
            "idx_test_events_anonymous_time": (
                "ON test_events(anonymous_id, occurred_at DESC)"
            ),
            "idx_test_events_type_time": "ON test_events(event_type, received_at DESC)",
            "idx_task_test_feedback_anonymous_time": (
                "ON task_test_feedback(anonymous_id, created_at DESC)"
            ),
            "idx_admin_sessions_expiry": "ON admin_sessions(expires_at)",
        }
        for index, indexed_columns in expected_indexes.items():
            self.assertIn(
                f"CREATE INDEX IF NOT EXISTS {index}\n{indexed_columns}",
                sql,
            )

    def test_user_testing_metrics_migration_is_replay_safe_for_migration_runner(
        self,
    ) -> None:
        migration = next(
            path
            for path in migration_files()
            if path.name == "002_user_testing_metrics.sql"
        )
        statements = list(_statements(migration.read_text(encoding="utf-8")))

        self.assertEqual(len(statements), 11)
        for statement in statements:
            self.assertTrue(
                statement.startswith("CREATE TABLE IF NOT EXISTS")
                or statement.startswith("CREATE INDEX IF NOT EXISTS")
                or statement.startswith("CREATE UNIQUE INDEX IF NOT EXISTS")
                or statement.startswith("ALTER TABLE IF EXISTS"),
                statement,
            )

    def test_admin_security_upgrade_is_replay_safe_and_provides_service_columns(self) -> None:
        migration = next(
            path
            for path in migration_files()
            if path.name == "003_admin_security_upgrade.sql"
        )
        statements = list(_statements(migration.read_text(encoding="utf-8")))

        self.assertEqual(len(statements), 3)
        self.assertIn("ADD COLUMN IF NOT EXISTS failed_login_count INTEGER NOT NULL DEFAULT 0", statements[0])
        self.assertIn("CHECK (failed_login_count >= 0)", statements[0])
        self.assertIn("ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ", statements[1])
        self.assertIn("CREATE UNIQUE INDEX IF NOT EXISTS idx_admin_users_single_admin", statements[2])
        self.assertIn("ON admin_users(role) WHERE role = 'admin'", statements[2])

    def test_migration_runner_skips_002_after_recording_it(self) -> None:
        connection = FakeConnection()

        with patch("database_migrations.psycopg.connect", return_value=connection):
            run_migrations("postgresql://controlled-test")
            run_migrations("postgresql://controlled-test")

        migration_sql = next(
            path.read_text(encoding="utf-8")
            for path in migration_files()
            if path.name == "002_user_testing_metrics.sql"
        )
        migration_statements = list(_statements(migration_sql))
        executed_002_statements = [
            statement
            for statement, _ in connection.executions
            if statement in migration_statements
        ]
        recorded_002_versions = [
            params
            for statement, params in connection.executions
            if "INSERT INTO schema_migrations" in statement
            and params == (2, "002_user_testing_metrics.sql")
        ]

        self.assertEqual(executed_002_statements[: len(migration_statements)], list(migration_statements))
        self.assertEqual(
            executed_002_statements.count(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_test_events_anonymous_idempotency\nON test_events(anonymous_id, idempotency_key)"
            ),
            2,
        )
        self.assertEqual(recorded_002_versions, [(2, "002_user_testing_metrics.sql")])

    def test_migration_runner_upgrades_an_already_applied_002_once(self) -> None:
        connection = FakeConnection()
        connection.applied_versions.update({1, 2})

        with patch("database_migrations.psycopg.connect", return_value=connection):
            run_migrations("postgresql://controlled-test")
            run_migrations("postgresql://controlled-test")

        upgrade_sql = next(
            path.read_text(encoding="utf-8")
            for path in migration_files()
            if path.name == "004_user_testing_retention_and_idempotency.sql"
        )
        upgrade_statements = list(_statements(upgrade_sql))
        executed_upgrade_statements = [
            statement
            for statement, _ in connection.executions
            if statement in upgrade_statements
        ]
        recorded_upgrade_versions = [
            params
            for statement, params in connection.executions
            if "INSERT INTO schema_migrations" in statement
            and params in (
                (3, "003_admin_security_upgrade.sql"),
                (4, "004_user_testing_retention_and_idempotency.sql"),
            )
        ]

        self.assertEqual(executed_upgrade_statements, upgrade_statements)
        self.assertEqual(recorded_upgrade_versions, [(3, "003_admin_security_upgrade.sql"), (4, "004_user_testing_retention_and_idempotency.sql")])

    def test_repository_can_skip_legacy_schema_initialization(self) -> None:
        with patch.object(PostgresSessionRepository, "init_schema") as init_schema:
            PostgresSessionRepository("postgresql://example", schema_init=False)
        init_schema.assert_not_called()


if __name__ == "__main__":
    unittest.main()
