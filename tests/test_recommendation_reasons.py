from __future__ import annotations

import unittest

from recommendation_module import recommend_tasks
from task_repository import Task


class RecommendationReasonTests(unittest.TestCase):
    def test_recommended_tasks_include_rule_based_tags_and_reason_text(self) -> None:
        tasks = [
            Task(
                id="task_home_stretch",
                title="居家拉伸",
                category="活力充电",
                duration=20,
                budget=0,
                outing="home",
                company="solo",
            )
        ]
        profile = {
            "scores": {"活力充电": 0.8},
            "constraints": {
                "outing": "home",
                "company": "solo",
                "budget_limit": 20,
                "max_duration": 30,
            },
        }

        result = recommend_tasks(profile, ["活力充电"], tasks, limit=1)

        [task] = result["tasks"]
        self.assertIn("居家可做", task["reason_tags"])
        self.assertIn("低预算", task["reason_tags"])
        self.assertIn("短时间可完成", task["reason_tags"])
        self.assertIn("适合独处", task["reason_tags"])
        self.assertIn("覆盖活力充电", task["reason_tags"])
        self.assertIn("你选择了「活力充电」", task["reason_text"])
        self.assertIn("无需外出", task["reason_text"])

        [reason] = result["reasons"]
        self.assertEqual(reason["task_id"], "task_home_stretch")
        self.assertEqual(reason["tags"], task["reason_tags"])
        self.assertEqual(reason["text"], task["reason_text"])


if __name__ == "__main__":
    unittest.main()
