from __future__ import annotations

import unittest
from unittest.mock import patch

from database_migrations import _statements, migration_files
from session_module import PostgresSessionRepository


class FakeConnection:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def cursor(self):
        return self

    def execute(self, statement, params=None):
        self.statements.append(str(statement))
        return self


class DatabaseMigrationTests(unittest.TestCase):
    def test_migrations_are_versioned_and_cover_core_tables(self) -> None:
        files = migration_files()
        self.assertEqual(
            [path.name for path in files],
            ["001_initial_schema.sql", "002_user_testing_metrics.sql"],
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

        self.assertIn("CHECK (rating BETWEEN 1 AND 5)", sql)
        self.assertIn("UNIQUE (idempotency_key)", sql)
        self.assertIn("UNIQUE (plan_item_id)", sql)

        for index in (
            "idx_test_events_anonymous_time",
            "idx_test_events_type_time",
            "idx_task_test_feedback_anonymous_time",
            "idx_admin_sessions_expiry",
        ):
            self.assertIn(f"CREATE INDEX IF NOT EXISTS {index}", sql)

    def test_user_testing_metrics_migration_is_replay_safe_for_migration_runner(
        self,
    ) -> None:
        migration = next(
            path
            for path in migration_files()
            if path.name == "002_user_testing_metrics.sql"
        )
        statements = list(_statements(migration.read_text(encoding="utf-8")))

        self.assertEqual(len(statements), 9)
        for statement in statements:
            self.assertTrue(
                statement.startswith("CREATE TABLE IF NOT EXISTS")
                or statement.startswith("CREATE INDEX IF NOT EXISTS"),
                statement,
            )

    def test_repository_can_skip_legacy_schema_initialization(self) -> None:
        with patch.object(PostgresSessionRepository, "init_schema") as init_schema:
            PostgresSessionRepository("postgresql://example", schema_init=False)
        init_schema.assert_not_called()


if __name__ == "__main__":
    unittest.main()
