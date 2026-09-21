from __future__ import annotations

import unittest

from candidate_provider import CandidateTask, RecommendationContext
from quick_recommendation import rank_quick
from task_repository import Task


def candidate(
    task_id: str,
    duration: int = 10,
    budget: int = 0,
    outing: str = "home",
    company: str = "solo",
    ease: int = 4,
    physical: int = 1,
    action: str = "站稳，伸展一下。",
    startup_cost: int = 0,
    social_pressure: int = 1,
) -> CandidateTask:
    task = Task(
        task_id, task_id, "松弛疗愈", duration, budget, outing, company,
        feedback_group=task_id, ease_level=ease, physical_load=physical,
        social_pressure=social_pressure,
    )
    return CandidateTask(task, action, "task_bank", True, startup_cost)


class RankQuickTest(unittest.TestCase):
    def test_rejects_unsafe_unprepared_and_duplicate_candidates(self) -> None:
        context = RecommendationContext("quick", "sess", None, 15, "low")
        ranked = rank_quick(context, [
            candidate("ok"), candidate("ok"), candidate("paid", budget=2),
            candidate("out", outing="nearby"), candidate("group", company="group"),
            candidate("long", duration=20), candidate("missing", action=""),
        ])
        self.assertEqual([task["id"] for task in ranked], ["ok"])
        self.assertEqual(ranked[0]["first_action"], "站稳，伸展一下。")
        self.assertIn("在家", ranked[0]["reason"])

    def test_low_energy_prefers_easy_task_not_just_shortest(self) -> None:
        context = RecommendationContext("quick", "sess", None, 20, "low")
        ranked = rank_quick(context, [
            candidate("short_hard", 5, ease=1, physical=5, social_pressure=3),
            candidate("easy", 15, ease=5, physical=1),
        ])
        self.assertEqual(ranked[0]["id"], "easy")

    def test_equal_fit_prefers_lower_preparation_cost(self) -> None:
        context = RecommendationContext("quick", "sess", None, 20, "medium")
        ranked = rank_quick(context, [
            candidate("needs_setup", 5, startup_cost=2),
            candidate("instant", 15, startup_cost=0),
        ])
        self.assertEqual(ranked[0]["id"], "instant")

    def test_history_and_disliked_task_affect_choice(self) -> None:
        context = RecommendationContext("quick", "sess", "user", 20, "medium")
        ranked = rank_quick(
            context,
            [candidate("avoid"), candidate("liked"), candidate("neutral")],
            history_weights={"group_boosts": {"liked": 0.5}},
            excluded_task_ids={"avoid"},
        )
        self.assertEqual([task["id"] for task in ranked], ["liked", "neutral"])

    def test_empty_pool_does_not_relax_constraints(self) -> None:
        context = RecommendationContext("quick", "sess", None, 5, "low")
        self.assertEqual(rank_quick(context, [candidate("too_long", duration=20)]), [])

    def test_returns_at_most_ten_distinct_tasks(self) -> None:
        context = RecommendationContext("quick", "sess", None, 20, "medium")
        ranked = rank_quick(context, [candidate(f"task_{index}") for index in range(20)])
        self.assertEqual(len(ranked), 10)
        self.assertEqual(len({task["id"] for task in ranked}), 10)


if __name__ == "__main__":
    unittest.main()
