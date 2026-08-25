from __future__ import annotations

import unittest

from plan_module import select_easier_replacement_task
from recommendation_module import recommend_tasks
from task_repository import Task


class HistoryAwareRecommendationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = {
            "scores": {"活力充电": 0.8},
            "constraints": {"budget_limit": 20, "max_duration": 60},
        }
        self.tasks = [
            Task("task_a", "普通散步", "活力充电", 30, 0, "nearby", "solo", feedback_group="walk_plain"),
            Task("task_b", "熟悉路线慢走", "活力充电", 30, 0, "nearby", "solo", feedback_group="walk_favorite"),
        ]

    def test_completed_group_moves_task_ahead_of_equal_candidate(self) -> None:
        result = recommend_tasks(
            self.profile,
            ["活力充电"],
            self.tasks,
            limit=2,
            history_weights={"group_boosts": {"walk_favorite": 0.4}},
        )

        self.assertEqual(result["tasks"][0]["id"], "task_b")

    def test_history_excluded_group_is_not_returned(self) -> None:
        result = recommend_tasks(
            self.profile,
            ["活力充电"],
            self.tasks,
            limit=2,
            history_excluded_groups={"walk_favorite"},
        )

        self.assertEqual(result["task_ids"], ["task_a"])

    def test_history_exclusions_do_not_change_visible_session_memory_counts(self) -> None:
        result = recommend_tasks(
            self.profile,
            ["活力充电"],
            self.tasks,
            limit=2,
            history_excluded_groups={"walk_favorite"},
        )

        self.assertEqual(result["recommendation_memory"]["excluded_group_count"], 0)
        self.assertEqual(result["recommendation_memory"]["excluded_task_count"], 0)

    def test_easier_replacement_excludes_used_history_and_disliked_groups(self) -> None:
        candidates = [
            Task("current", "当前任务", "活力充电", 5, 0, "home", "solo", feedback_group="current"),
            Task("plan_used", "计划已用", "活力充电", 6, 0, "home", "solo", feedback_group="used"),
            Task("replacement_seen", "替换历史", "活力充电", 7, 0, "home", "solo", feedback_group="seen"),
            Task("session_disliked", "会话排除", "活力充电", 8, 0, "home", "solo", feedback_group="session_disliked"),
            Task("history_disliked", "历史排除", "活力充电", 9, 0, "home", "solo", feedback_group="history_disliked"),
            Task("fresh", "可用任务", "活力充电", 10, 0, "home", "solo", feedback_group="fresh"),
        ]

        replacement = select_easier_replacement_task(
            candidates=candidates,
            category="活力充电",
            used_task_ids={"current", "plan_used", "replacement_seen"},
            excluded_feedback_groups={"session_disliked", "history_disliked"},
        )

        self.assertIsNotNone(replacement)
        self.assertEqual(replacement.id, "fresh")


if __name__ == "__main__":
    unittest.main()
