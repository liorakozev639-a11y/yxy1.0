from __future__ import annotations

import unittest

from quick_task_catalog import QUICK_FIRST_ACTIONS, quick_metadata
from task_repository import TaskRepository


class QuickCatalogTest(unittest.TestCase):
    def test_curated_entries_are_real_safe_and_actionable(self) -> None:
        by_id = {task.id: task for task in TaskRepository().public_tasks}
        self.assertGreaterEqual(len(QUICK_FIRST_ACTIONS), 10)
        for task_id, action in QUICK_FIRST_ACTIONS.items():
            task = by_id[task_id]
            self.assertEqual(task.status, "approved")
            self.assertEqual(task.budget, 0)
            self.assertEqual(task.outing, "home")
            self.assertIn(task.company, {"solo", "both"})
            self.assertTrue(action.strip())
            self.assertEqual(quick_metadata(task), action)

    def test_unreviewed_task_does_not_enter_quick_mode(self) -> None:
        task = next(
            task for task in TaskRepository().public_tasks
            if task.id not in QUICK_FIRST_ACTIONS
        )
        self.assertIsNone(quick_metadata(task))


if __name__ == "__main__":
    unittest.main()
