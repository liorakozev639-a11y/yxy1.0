from __future__ import annotations

import unittest
from unittest.mock import patch

from plan_module import PlanManagementService


class FakeConnection:
    def __init__(self, statements: list[str]) -> None:
        self.statements = statements

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def execute(self, statement: str) -> None:
        self.statements.append(" ".join(statement.split()))


class PlanSchemaInitTests(unittest.TestCase):
    def test_plan_management_creates_base_tables_before_altering_columns(self) -> None:
        statements: list[str] = []

        with patch(
            "plan_module.psycopg.connect",
            return_value=FakeConnection(statements),
        ):
            PlanManagementService(
                "postgresql://example",
                sessions=object(),
                orchestrator=object(),
            )

        plans_create_index = next(
            index
            for index, statement in enumerate(statements)
            if statement.startswith("CREATE TABLE IF NOT EXISTS plans")
        )
        plan_items_create_index = next(
            index
            for index, statement in enumerate(statements)
            if statement.startswith("CREATE TABLE IF NOT EXISTS plan_items")
        )
        plans_alter_index = next(
            index
            for index, statement in enumerate(statements)
            if statement.startswith("ALTER TABLE plans")
        )

        self.assertLess(plans_create_index, plans_alter_index)
        self.assertLess(plan_items_create_index, plans_alter_index)


if __name__ == "__main__":
    unittest.main()
