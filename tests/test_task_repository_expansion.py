import unittest
from collections import Counter

from task_repository import CATEGORIES, PUBLIC_TASKS, SCENARIOS, Task, TaskRepository


class TaskRepositoryExpansionTests(unittest.TestCase):
    def test_public_task_bank_has_forty_tasks_per_category_and_feedback_groups(self) -> None:
        counts = Counter(task.category for task in PUBLIC_TASKS)

        self.assertEqual(len(PUBLIC_TASKS), 200)
        self.assertEqual(counts, {category: 40 for category in CATEGORIES})
        self.assertTrue(all(task.feedback_group for task in PUBLIC_TASKS))
        self.assertTrue(
            all(
                task.feedback_group.startswith(
                    ("energy_", "recovery_", "social_", "explore_", "growth_")
                )
                for task in PUBLIC_TASKS
            )
        )

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

    def test_custom_task_uses_a_group_unique_to_itself(self) -> None:
        task = Task(
            id="custom_test_reading",
            title="阅读测试任务",
            category="自我成长",
            duration=20,
            budget=0,
            outing="home",
            company="solo",
        )

        saved = TaskRepository().add_custom_task("sess_test", task)

        self.assertEqual(saved.feedback_group, "custom:custom_test_reading")


if __name__ == "__main__":
    unittest.main()
