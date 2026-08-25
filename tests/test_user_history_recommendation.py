from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
