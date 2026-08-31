from __future__ import annotations

import unittest

from recommendation_module import recommend_tasks
from task_repository import Task


class RecommendationReasonTests(unittest.TestCase):
    def test_recommendation_excludes_feedback_groups_before_category_coverage(self) -> None:
        tasks = [
            Task(
                id="quiet",
                title="居家呼吸练习",
                category="松弛疗愈",
                duration=10,
                budget=0,
                outing="home",
                company="solo",
                feedback_group="recovery_quiet_home",
            ),
            Task(
                id="outdoor",
                title="公园慢走",
                category="松弛疗愈",
                duration=30,
                budget=0,
                outing="nearby",
                company="solo",
                feedback_group="recovery_quiet_outdoor",
            ),
        ]

        result = recommend_tasks(
            profile={"scores": {"松弛疗愈": 1.0}},
            selected_categories=["松弛疗愈"],
            candidates=tasks,
            excluded_feedback_groups={"recovery_quiet_home"},
        )

        self.assertEqual([task["id"] for task in result["tasks"]], ["outdoor"])
        self.assertEqual(result["recommendation_memory"]["excluded_group_count"], 1)
        self.assertEqual(result["recommendation_memory"]["excluded_task_count"], 1)

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
        self.assertEqual(task["match_score"], 0.8)
        self.assertIn("分类偏好强", task["matched_preferences"])
        self.assertIn("居家可做", task["matched_preferences"])
        self.assertEqual(task["warning_text"], "")

        [reason] = result["reasons"]
        self.assertEqual(reason["task_id"], "task_home_stretch")
        self.assertEqual(reason["tags"], task["reason_tags"])
        self.assertEqual(reason["text"], task["reason_text"])
        self.assertEqual(reason["match_score"], task["match_score"])
        self.assertEqual(reason["matched_preferences"], task["matched_preferences"])
        self.assertEqual(reason["warning_text"], "")

    def test_recommended_tasks_warn_when_budget_or_duration_is_relaxed(self) -> None:
        tasks = [
            Task(
                id="task_city_visit",
                title="城市展览漫游",
                category="乐享探索",
                duration=90,
                budget=80,
                outing="city",
                company="both",
            )
        ]
        profile = {
            "scores": {"乐享探索": 0.42},
            "constraints": {
                "outing": "nearby",
                "company": "solo",
                "budget_limit": 40,
                "max_duration": 60,
            },
        }

        result = recommend_tasks(profile, ["乐享探索"], tasks, limit=1)

        [task] = result["tasks"]
        self.assertLess(task["match_score"], 0.8)
        self.assertIn("预算高于当前档位", task["warning_text"])
        self.assertIn("时长超过当前偏好", task["warning_text"])

    def test_rest_only_recommendation_prioritizes_lighter_tasks(self) -> None:
        tasks = [
            Task(
                id="task_hard_training",
                title="高强度训练",
                category="活力充电",
                duration=20,
                budget=0,
                outing="home",
                company="solo",
                ease_level=1,
                physical_load=5,
                social_pressure=1,
                location_dependency="home",
            ),
            Task(
                id="task_soft_stretch",
                title="温和拉伸",
                category="活力充电",
                duration=25,
                budget=0,
                outing="home",
                company="solo",
                ease_level=5,
                physical_load=1,
                social_pressure=1,
                location_dependency="home",
            ),
        ]
        profile = {
            "scores": {"活力充电": 0.8},
            "constraints": {
                "outing": "home",
                "company": "solo",
                "budget_limit": 20,
                "max_duration": 30,
                "rest_only": True,
            },
        }

        result = recommend_tasks(profile, ["活力充电"], tasks, limit=1)

        [task] = result["tasks"]
        self.assertEqual(task["id"], "task_soft_stretch")
        self.assertEqual(task["load_profile"]["ease_label"], "很轻松")
        self.assertIn("轻松度高", task["reason_tags"])
        self.assertIn("体力消耗低", task["reason_tags"])
        self.assertIn("轻松度较高", task["matched_preferences"])
        self.assertIn("体力消耗较低", task["reason_text"])


if __name__ == "__main__":
    unittest.main()
