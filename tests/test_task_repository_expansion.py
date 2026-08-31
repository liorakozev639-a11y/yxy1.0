import unittest
from collections import Counter

from task_repository import CATEGORIES, PUBLIC_TASKS, SCENARIOS, Task, TaskRepository


class TaskRepositoryExpansionTests(unittest.TestCase):
    def test_public_task_bank_has_sixty_tasks_per_category_and_feedback_groups(self) -> None:
        counts = Counter(task.category for task in PUBLIC_TASKS)

        self.assertEqual(len(PUBLIC_TASKS), 300)
        self.assertEqual(counts, {category: 60 for category in CATEGORIES})
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
            self.assertIn(task.ease_level, range(1, 6))
            self.assertIn(task.physical_load, range(1, 6))
            self.assertIn(task.social_pressure, range(1, 6))
            self.assertIn(
                task.location_dependency,
                {"home", "nearby", "city", "flexible"},
            )
            self.assertTrue(set(task.scenarios).issubset(SCENARIOS))
            self.assertFalse(any(word in task.title for word in disallowed_words))

    def test_task_intensity_defaults_reflect_existing_task_shape(self) -> None:
        rest_task = next(task for task in PUBLIC_TASKS if task.id == "task_recovery_01")
        social_task = next(task for task in PUBLIC_TASKS if task.id == "task_social_04")
        exercise_task = next(task for task in PUBLIC_TASKS if task.id == "task_energy_18")

        self.assertGreaterEqual(rest_task.ease_level, 4)
        self.assertLessEqual(rest_task.physical_load, 2)
        self.assertGreaterEqual(social_task.social_pressure, 4)
        self.assertGreaterEqual(exercise_task.physical_load, 4)

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
