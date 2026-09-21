import unittest

from fastapi import HTTPException

from mock_task_service import MockTaskGenerationService
from test_mock_task_generation import MockTaskGenerationTests


class FakeGeneratedRepository:
    def __init__(self):
        self.runs = {}
        self.tasks = {}

    def get_run(self, session_id, generation_key):
        return self.runs.get((session_id, generation_key))

    def save_run(self, session_id, generation_key, context, brief, tasks, rejected):
        result = self.runs.setdefault(
            (session_id, generation_key),
            {"tasks": tasks, "rejected": rejected},
        )
        for task in result["tasks"]:
            self.tasks[task["id"]] = task
        return result

    def list_tasks(self, session_id):
        return list(self.tasks.values()) if session_id == "sess_mock" else []

    def get_task(self, session_id, task_id):
        return self.tasks.get(task_id) if session_id == "sess_mock" else None

    def save_task(self, session_id, task):
        self.tasks[task["id"]] = task
        return task


class MockTaskServiceTests(unittest.TestCase):
    def setUp(self):
        self.context = MockTaskGenerationTests().context(energy="medium")
        self.repo = FakeGeneratedRepository()
        self.service = MockTaskGenerationService(self.repo)

    def test_generates_ten_persisted_tasks_without_old_bank(self):
        result = self.service.recommend(self.context)
        self.assertEqual(result["generation_mode"], "mock")
        self.assertEqual(len(result["tasks"]), 10)
        self.assertEqual(len(self.repo.list_tasks("sess_mock")), 10)
        self.assertTrue(all(task["id"].startswith("mock_") for task in result["tasks"]))
        self.assertTrue(all(task["first_action"] and task["recommendation_reason"] for task in result["tasks"]))

    def test_same_context_reuses_task_ids(self):
        first = self.service.recommend(self.context)
        again = self.service.recommend(self.context)
        self.assertEqual(first["task_ids"], again["task_ids"])
        self.assertEqual(len(self.repo.runs), 1)

    def test_new_generation_in_same_session_excludes_previous_tasks(self):
        first = self.service.recommend(self.context)
        changed = {**self.context, "density": "full"}
        second = self.service.recommend(changed)
        self.assertTrue(second["tasks"])
        self.assertFalse(set(first["task_ids"]) & set(second["task_ids"]))
        self.assertFalse(
            {task["semantic_signature"] for task in first["tasks"]}
            & {task["semantic_signature"] for task in second["tasks"]}
        )

    def test_invalid_model_output_never_persists(self):
        from mock_task_generation import MockTaskGenerator

        service = MockTaskGenerationService(
            self.repo, MockTaskGenerator(scenario="invented_evidence")
        )
        result = service.recommend(self.context)
        self.assertTrue(result["rejected_count"])
        self.assertTrue(all(task["evidence_refs"] != ["question:not_answered"] for task in result["tasks"]))

    def test_no_valid_candidates_returns_clear_conflict(self):
        self.context["excluded_signatures"] = [
            __import__("mock_task_generation").semantic_signature(title)
            for rows in __import__("mock_task_generation")._ACTIONS.values()
            for title, _, _ in rows
        ]
        with self.assertRaises(HTTPException) as caught:
            self.service.recommend(self.context)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(caught.exception.detail["code"], "insufficient_valid_tasks")


if __name__ == "__main__":
    unittest.main()
