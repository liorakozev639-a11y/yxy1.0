from __future__ import annotations

import unittest

from candidate_provider import CandidateTask, RecommendationContext
from quick_recommendation_service import QuickRecommendationService
from task_repository import Task


class _Sessions:
    def require_active(self, session_id: str) -> None:
        self.session_id = session_id


class _History:
    def ensure_user(self, user_id: str) -> None:
        self.user_id = user_id

    def preference_weights(self, user_id: str) -> dict[str, object]:
        return {}

    def excluded_task_ids(self, user_id: str) -> set[str]:
        return {"strict_task"}


class _Store:
    def save_run(self, *args) -> str:
        self.tasks = args[-1]
        return "quick_run"


def _candidate(task_id: str) -> CandidateTask:
    task = Task(
        task_id, task_id, "松弛疗愈", 10, 0, "home", "solo",
        feedback_group=task_id, ease_level=5, physical_load=1, social_pressure=1,
    )
    return CandidateTask(task, "坐稳，缓慢呼吸一次。", "task_bank", True)


class _Provider:
    def generate(self, context: RecommendationContext) -> list[CandidateTask]:
        return [_candidate("strict_task")]

    def generate_quick_fallback(
        self, context: RecommendationContext,
    ) -> list[CandidateTask]:
        return [_candidate("similar_task")]


class QuickRecommendationServiceTest(unittest.TestCase):
    def test_uses_unseen_similar_candidate_after_strict_pool_is_exhausted(self) -> None:
        service = QuickRecommendationService(
            _Sessions(), _Provider(), _Store(), _History(),
        )

        result = service.generate("session_1", "user_1", 30, "low")

        self.assertEqual(result["recommendation_tier"], "similar")
        self.assertEqual(result["primary_task"]["id"], "similar_task")
        self.assertNotEqual(result["primary_task"]["id"], "strict_task")


if __name__ == "__main__":
    unittest.main()
