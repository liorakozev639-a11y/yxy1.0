from __future__ import annotations

import unittest
from unittest.mock import patch

from database_migrations import migration_files
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
        self.assertEqual([path.name for path in files], ["001_initial_schema.sql"])
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

    def test_repository_can_skip_legacy_schema_initialization(self) -> None:
        with patch.object(PostgresSessionRepository, "init_schema") as init_schema:
            PostgresSessionRepository("postgresql://example", schema_init=False)
        init_schema.assert_not_called()


if __name__ == "__main__":
    unittest.main()
