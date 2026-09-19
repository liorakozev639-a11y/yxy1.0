from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import create_app
from session_module import PostgresSessionRepository


class MockApiFlowLiveTests(unittest.TestCase):
    def setUp(self):
        self.database_url = os.getenv("SESSION_DATABASE_URL")
        if not self.database_url:
            self.skipTest("需要设置 SESSION_DATABASE_URL")
        with patch.dict(os.environ, {"TASK_GENERATION_MODE": "mock"}):
            self.client = TestClient(create_app())
        self.session_repository = PostgresSessionRepository(self.database_url)
        response = self.client.post("/api/v1/sessions")
        self.assertEqual(response.status_code, 201, response.text)
        self.session_id = response.json()["data"]["session_id"]

    def tearDown(self):
        if hasattr(self, "session_id"):
            self.session_repository.delete(self.session_id)
        if hasattr(self, "client"):
            self.client.close()

    def test_full_mock_flow_persists_replaces_and_executes(self):
        session_id = self.session_id
        saved = self.client.put(
            f"/api/v1/sessions/{session_id}/preferences",
            json={
                "categories": ["energy", "recovery"],
                "duration": "half", "budget": "low", "outing": "home",
                "company": "solo", "energy_level": "low",
            },
        )
        self.assertEqual(saved.status_code, 200, saved.text)
        started = self.client.post(
            f"/api/v1/sessions/{session_id}/questionnaire/start",
            json={"mode": "quick"},
        )
        self.assertEqual(started.status_code, 200, started.text)
        for question in started.json()["data"]["questions"]:
            answer = self.client.patch(
                f"/api/v1/sessions/{session_id}/questionnaire/answers/{question['id']}",
                json={"value": 3},
            )
            self.assertEqual(answer.status_code, 200, answer.text)
        submitted = self.client.post(f"/api/v1/sessions/{session_id}/questionnaire/submit")
        self.assertEqual(submitted.status_code, 200, submitted.text)

        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        generated = self.client.post(
            f"/api/v1/sessions/{session_id}/plan/generate",
            json={
                "free_start": now.isoformat(),
                "free_end": (now + timedelta(hours=3)).isoformat(),
                "density": "balanced",
            },
        )
        self.assertEqual(generated.status_code, 200, generated.text)
        result = generated.json()["data"]
        self.assertEqual(result["recommendation"]["generation_mode"], "mock")
        self.assertEqual(len(result["recommendation"]["tasks"]), 10)
        self.assertTrue(all(task["evidence_refs"] for task in result["recommendation"]["tasks"]))
        plan = self.client.get(f"/api/v1/sessions/{session_id}/plan").json()["data"]
        self.assertTrue(any(item.get("first_action") for item in plan["items"] if item["kind"] == "task"))
        item = next(item for item in plan["items"] if item["kind"] == "task")

        replaced = self.client.post(
            f"/api/v1/plans/{plan['plan_id']}/items/{item['id']}/replace",
            json={"expected_version": plan["version"]},
        )
        self.assertEqual(replaced.status_code, 200, replaced.text)
        plan = replaced.json()["data"]
        first_new = next(entry for entry in plan["items"] if entry["kind"] == "task" and entry["task_id"] != item["task_id"])
        self.assertNotEqual(first_new["task_id"], item["task_id"])

        recommended = next(
            task for task in result["recommendation"]["tasks"]
            if task["id"] not in {entry["task_id"] for entry in plan["items"]}
        )
        added = self.client.post(
            f"/api/v1/plans/{plan['plan_id']}/recommended-tasks/{recommended['id']}",
            json={"expected_version": plan["version"]},
        )
        self.assertEqual(added.status_code, 200, added.text)
        plan = added.json()["data"]
        self.assertIn(recommended["id"], [entry["task_id"] for entry in plan["items"]])

        active_item = next(entry for entry in plan["items"] if entry["kind"] == "task")
        start = self.client.post(
            f"/api/v1/plans/{plan['plan_id']}/items/{active_item['id']}/execution/start",
            json={"now": now.isoformat()},
        )
        self.assertEqual(start.status_code, 200, start.text)
        complete = self.client.post(
            f"/api/v1/plans/{plan['plan_id']}/items/{active_item['id']}/execution/complete",
            json={"now": (now + timedelta(minutes=2)).isoformat()},
        )
        self.assertEqual(complete.status_code, 200, complete.text)
        feedback = self.client.post(
            f"/api/v1/plans/{plan['plan_id']}/items/{active_item['id']}/feedback",
            json={"rating": 4, "reasons": ["容易开始"]},
        )
        self.assertEqual(feedback.status_code, 200, feedback.text)

        replanned = self.client.post(
            f"/api/v1/plans/{plan['plan_id']}/replan",
            json={"expected_version": plan["version"]},
        )
        self.assertEqual(replanned.status_code, 200, replanned.text)
        self.assertTrue(any(
            entry["task_id"] == active_item["task_id"] and entry["status"] == "completed"
            for entry in replanned.json()["data"]["items"]
        ))


if __name__ == "__main__":
    unittest.main()
