import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import HTTPException

from mock_task_service import MockTaskGenerationService
from plan_module import PlanManagementService
from test_mock_task_generation import MockTaskGenerationTests
from test_mock_task_service import FakeGeneratedRepository


class NoOldBank:
    @property
    def public_tasks(self):
        raise AssertionError("mock plan flow must not read public tasks")


class MockPlanFlowTests(unittest.TestCase):
    def setUp(self):
        self.repo = FakeGeneratedRepository()
        self.service = MockTaskGenerationService(self.repo)
        self.context = MockTaskGenerationTests().context(energy="medium")
        recommendation = self.service.recommend(self.context)
        self.original = recommendation["tasks"][0]
        self.start = datetime(2026, 9, 19, 9, tzinfo=timezone.utc)
        self.plan = {
            "plan_id": "plan_1", "session_id": "sess_mock", "version": 1,
            "density": "balanced", "free_start": self.start.isoformat(),
            "free_end": (self.start + timedelta(hours=3)).isoformat(),
            "status": "draft", "unscheduled_task_ids": [],
            "items": [{
                "id": "item_1", "task_id": self.original["id"],
                "title": self.original["title"], "category": self.original["category"],
                "start_at": self.start.isoformat(),
                "end_at": (self.start + timedelta(minutes=20)).isoformat(),
                "kind": "task", "status": "pending", "locked": False,
                "replacement_history": [],
            }],
        }
        manager = object.__new__(PlanManagementService)
        manager.tasks = NoOldBank()
        manager.memory = None
        manager.user_history = None
        manager.sessions = SimpleNamespace(
            require_active=lambda _: SimpleNamespace(preferences={
                "budget": "low", "duration": "half", "outing": "home", "company": "solo"
            })
        )
        manager.orchestrator = SimpleNamespace(
            mock_generation=self.service,
            _build_profile=lambda _: object(),
            _generation_context=lambda *_: self.context,
        )
        manager._require = lambda _session, _plan: self.plan
        manager._save_version = self.save_version
        self.manager = manager

    def save_version(self, old, items):
        self.plan = {**old, "plan_id": f"plan_{old['version'] + 1}", "version": old["version"] + 1, "items": items}
        return self.plan

    def test_two_replacements_never_return_previous_task(self):
        first = self.manager.replace_item("sess_mock", "plan_1", "item_1", 1)
        first_id = first["items"][0]["task_id"]
        second = self.manager.replace_item("sess_mock", first["plan_id"], "item_1", 2)
        second_id = second["items"][0]["task_id"]
        self.assertEqual(len({self.original["id"], first_id, second_id}), 3)
        self.assertEqual(
            second["items"][0]["replacement_history"],
            [self.original["id"], first_id, second_id],
        )

    def test_completed_task_cannot_be_replaced(self):
        self.plan["items"][0]["status"] = "completed"
        with self.assertRaises(HTTPException) as caught:
            self.manager.replace_item("sess_mock", "plan_1", "item_1", 1)
        self.assertEqual(caught.exception.status_code, 409)

    def test_preferred_replacement_must_match_hard_constraints(self):
        preferred = dict(next(
            task for task in self.service.recommend(self.context)["tasks"]
            if task["category"] == self.original["category"]
            and task["id"] != self.original["id"]
        ))
        preferred["outing"] = "city"
        self.repo.tasks[preferred["id"]] = preferred
        with self.assertRaises(HTTPException) as caught:
            self.manager.replace_item(
                "sess_mock", "plan_1", "item_1", 1,
                replacement_task_id=preferred["id"],
            )
        self.assertEqual(caught.exception.status_code, 409)

    def test_recommended_task_is_loaded_from_generated_repository(self):
        task = self.service.recommend(self.context)["tasks"][1]
        added = self.manager.add_recommended_task("sess_mock", "plan_1", task["id"], 1)
        self.assertIn(task["id"], [item["task_id"] for item in added["items"]])

    def test_recommended_task_is_revalidated_before_adding(self):
        task = dict(self.service.recommend(self.context)["tasks"][1])
        task["outing"] = "city"
        self.repo.tasks[task["id"]] = task
        with self.assertRaises(HTTPException) as caught:
            self.manager.add_recommended_task("sess_mock", "plan_1", task["id"], 1)
        self.assertEqual(caught.exception.status_code, 409)

    def test_replan_preserves_active_task_and_does_not_resurrect_skipped_task(self):
        self.plan["items"][0]["status"] = "active"
        self.plan["items"][0]["locked"] = True
        skipped = self.service.recommend(self.context)["tasks"][1]
        self.plan["items"].append({
            **self.plan["items"][0],
            "id": "item_skipped",
            "task_id": skipped["id"],
            "title": skipped["title"],
            "status": "skipped",
            "locked": True,
        })
        replanned = self.manager.replan("sess_mock", "plan_1", 1)
        self.assertTrue(any(
            item["task_id"] == self.original["id"] and item["status"] == "active"
            and item["start_at"] == self.start.isoformat()
            for item in replanned["items"]
        ))
        self.assertFalse(any(item["task_id"] == skipped["id"] for item in replanned["items"]))


if __name__ == "__main__":
    unittest.main()
