from __future__ import annotations

import unittest
from types import SimpleNamespace

from fastapi import HTTPException

from plan_module import PlanManagementService


class FakeUpdateResult:
    rowcount = 0


class FakeConnection:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def execute(self, statement, params=None):
        self.statements.append(" ".join(str(statement).split()))
        return FakeUpdateResult()


class PlanConcurrencyTests(unittest.TestCase):
    def test_save_version_rejects_a_stale_plan_without_creating_a_new_version(self) -> None:
        connection = FakeConnection()
        manager = PlanManagementService.__new__(PlanManagementService)
        manager._connect = lambda: connection
        manager.sessions = SimpleNamespace(require_active=lambda session_id: None)
        manager.get = lambda session_id, plan_id: {"plan_id": plan_id}
        plan = {
            "plan_id": "plan_old",
            "session_id": "session_one",
            "density": "light",
            "free_start": "2026-09-21T09:00:00+00:00",
            "free_end": "2026-09-21T12:00:00+00:00",
            "version": 3,
            "parent_plan_id": None,
            "unscheduled_task_ids": [],
        }

        with self.assertRaises(HTTPException) as context:
            manager._save_version(plan, [])

        self.assertEqual(context.exception.status_code, 409)
        self.assertIn("计划版本已变化", str(context.exception.detail))
        self.assertEqual(len(connection.statements), 1)
        self.assertIn("version = %s", connection.statements[0])


if __name__ == "__main__":
    unittest.main()
