import unittest
from collections import Counter

from task_repository import CATEGORIES, PUBLIC_TASKS, SCENARIOS


class TaskRepositoryExpansionTests(unittest.TestCase):
    def test_public_task_bank_has_thirty_tasks_per_category(self) -> None:
        counts = Counter(task.category for task in PUBLIC_TASKS)

        self.assertEqual(len(PUBLIC_TASKS), 150)
        self.assertEqual(counts, {category: 30 for category in CATEGORIES})

    def test_public_tasks_are_generic_and_usable_without_live_api(self) -> None:
        disallowed_words = ("地址", "营业", "实时", "商户", "店名")

        for task in PUBLIC_TASKS:
            self.assertIn(task.category, CATEGORIES)
            self.assertGreater(task.duration, 0)
            self.assertGreaterEqual(task.budget, 0)
            self.assertIn(task.outing, {"home", "nearby", "city"})
            self.assertIn(task.company, {"solo", "group", "both"})
            self.assertTrue(set(task.scenarios).issubset(SCENARIOS))
            self.assertFalse(any(word in task.title for word in disallowed_words))


if __name__ == "__main__":
    unittest.main()
