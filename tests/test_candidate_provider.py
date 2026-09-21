from __future__ import annotations

import unittest

from candidate_provider import (
    CandidateTask,
    FallbackCandidateProvider,
    RecommendationContext,
    TaskBankProvider,
    is_quick_eligible,
)
from mvp_orchestrator import MVPOrchestrator
from task_repository import Task, TaskRepository


class CandidateProviderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.bank = TaskBankProvider(TaskRepository())
        self.quick = RecommendationContext("quick", "sess_test", None, 30, "low")

    def test_quick_bank_only_returns_curated_immediate_tasks(self) -> None:
        candidates = self.bank.generate(self.quick)
        self.assertTrue(candidates)
        self.assertTrue(all(candidate.source == "task_bank" for candidate in candidates))
        self.assertTrue(all(is_quick_eligible(self.quick, candidate) for candidate in candidates))

    def test_full_bank_preserves_existing_category_filter(self) -> None:
        context = RecommendationContext(
            "full", "sess_test", None, 60, "medium",
            categories=("活力充电",), budget_limit=20, outing="nearby", company="both",
        )
        candidates = self.bank.generate(context)
        self.assertTrue(candidates)
        self.assertTrue(all(item.task.category == "活力充电" for item in candidates))

    def test_primary_timeout_falls_back_to_bank(self) -> None:
        class TimedOut:
            def generate(self, context):
                raise TimeoutError("provider timeout")

        candidates = FallbackCandidateProvider(TimedOut(), self.bank).generate(self.quick)
        self.assertTrue(candidates)
        self.assertTrue(all(item.source == "task_bank" for item in candidates))

    def test_invalid_primary_candidates_fall_back_to_bank(self) -> None:
        class Invalid:
            def generate(self, context):
                return [CandidateTask(
                    Task("remote", "需要出门的任务", "活力充电", 10, 0, "city", "solo"),
                    "走出家门", "fake_model", True,
                )]

        candidates = FallbackCandidateProvider(Invalid(), self.bank).generate(self.quick)
        self.assertTrue(candidates)
        self.assertTrue(all(item.source == "task_bank" for item in candidates))

    def test_full_orchestrator_reads_injected_candidate_provider(self) -> None:
        task = Task("from_provider", "居家舒展", "活力充电", 10, 0, "home", "solo")

        class OneCandidate:
            def generate(self, context):
                return [CandidateTask(task, "", "task_bank")]

        orchestrator = MVPOrchestrator(
            sessions=None, questionnaire=None, tasks=TaskRepository(),
            profiles=None, plans=None, delivery=None,
            candidate_provider=OneCandidate(),
        )
        result = orchestrator._recommend(
            {
                "session_id": "sess_test",
                "scores": {"活力充电": 1},
                "constraints": {
                    "budget_limit": 0, "max_duration": 30,
                    "outing": "home", "company": "solo",
                },
            },
            ["活力充电"],
        )
        self.assertEqual(result["task_ids"], ["from_provider"])


if __name__ == "__main__":
    unittest.main()
