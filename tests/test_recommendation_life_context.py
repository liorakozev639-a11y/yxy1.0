from __future__ import annotations

import unittest

from recommendation_module import recommend_tasks
from task_repository import Task


class RecommendationLifeContextTests(unittest.TestCase):
    def test_rainy_evening_low_energy_anxious_context_prioritizes_home_light_task(self) -> None:
        tasks = [
            Task(
                id="task_fast_outdoor",
                title="去操场快走十分钟",
                category="活力充电",
                duration=10,
                budget=0,
                outing="nearby",
                company="solo",
                ease_level=2,
                physical_load=4,
                social_pressure=2,
                location_dependency="nearby",
            ),
            Task(
                id="task_soft_home",
                title="在家做一组舒缓拉伸",
                category="活力充电",
                duration=30,
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
                "outing": "any",
                "company": "solo",
                "budget_limit": 20,
                "max_duration": 60,
                "weather": "rainy",
                "day_part": "evening",
                "energy_level": "low",
                "mood": "anxious",
            },
        }

        result = recommend_tasks(profile, ["活力充电"], tasks, limit=1)

        self.assertEqual(result["tasks"][0]["id"], "task_soft_home")

    def test_recommendation_reason_explains_life_context(self) -> None:
        task = Task(
            id="task_soft_home",
            title="在家做一组舒缓拉伸",
            category="松弛疗愈",
            duration=20,
            budget=0,
            outing="home",
            company="solo",
            ease_level=5,
            physical_load=1,
            social_pressure=1,
            location_dependency="home",
        )
        profile = {
            "scores": {"松弛疗愈": 0.9},
            "constraints": {
                "outing": "any",
                "company": "solo",
                "budget_limit": 20,
                "max_duration": 60,
                "weather": "rainy",
                "day_part": "evening",
                "energy_level": "low",
                "mood": "anxious",
            },
        }

        result = recommend_tasks(profile, ["松弛疗愈"], [task], limit=1)

        recommended = result["tasks"][0]
        self.assertIn("天气友好", recommended["reason_tags"])
        self.assertIn("低精力友好", recommended["reason_tags"])
        self.assertIn("情绪安抚", recommended["reason_tags"])
        self.assertIn("下雨或天气不稳定", recommended["reason_text"])
        self.assertIn("低精力", recommended["reason_text"])
        self.assertIn("焦虑", recommended["reason_text"])

    def test_life_context_changes_visible_match_score_and_warning(self) -> None:
        outdoor = Task(
            id="task_outdoor_run",
            title="去户外跑步",
            category="活力充电",
            duration=30,
            budget=0,
            outing="nearby",
            company="solo",
            ease_level=2,
            physical_load=5,
            social_pressure=2,
            location_dependency="nearby",
        )
        home = Task(
            id="task_home_stretch",
            title="居家舒缓拉伸",
            category="活力充电",
            duration=30,
            budget=0,
            outing="home",
            company="solo",
            ease_level=5,
            physical_load=1,
            social_pressure=1,
            location_dependency="home",
        )
        profile = {
            "scores": {"活力充电": 0.8},
            "constraints": {
                "outing": "any",
                "company": "solo",
                "budget_limit": 20,
                "max_duration": 60,
                "weather": "rainy",
                "day_part": "evening",
                "energy_level": "low",
                "mood": "anxious",
            },
        }

        result = recommend_tasks(profile, ["活力充电"], [outdoor, home], limit=2)

        by_id = {task["id"]: task for task in result["tasks"]}
        self.assertGreater(
            by_id["task_home_stretch"]["match_score"],
            by_id["task_outdoor_run"]["match_score"],
        )
        self.assertIn("当前天气下外出成本可能偏高", by_id["task_outdoor_run"]["warning_text"])
        self.assertIn("低精力时可能偏累", by_id["task_outdoor_run"]["warning_text"])


if __name__ == "__main__":
    unittest.main()
