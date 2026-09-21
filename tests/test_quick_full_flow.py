from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import create_app
from quick_test_support import delete_test_user, require_test_database
from session_module import PostgresSessionRepository


class QuickFullFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.database_url = require_test_database()
        import os
        with patch.dict(os.environ, {"TASK_GENERATION_MODE": "rules"}):
            cls.client = TestClient(create_app())
        cls.sessions = PostgresSessionRepository(cls.database_url)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "client"):
            cls.client.close()

    def setUp(self) -> None:
        self.session_ids: list[str] = []
        self.user_id = self.client.post(
            "/api/v1/users/anonymous", json={},
        ).json()["data"]["user_id"]

    def tearDown(self) -> None:
        for session_id in self.session_ids:
            self.sessions.delete(session_id)
        delete_test_user(self.database_url, self.user_id)

    def new_session(self) -> str:
        response = self.client.post("/api/v1/sessions")
        self.assertEqual(response.status_code, 201, response.text)
        session_id = response.json()["data"]["session_id"]
        self.session_ids.append(session_id)
        return session_id

    def test_quick_feedback_does_not_create_completion_and_full_mode_still_plans(self) -> None:
        quick_id = self.new_session()
        quick_path = f"/api/v1/sessions/{quick_id}/quick-recommendations"
        quick = self.client.post(
            quick_path,
            json={"available_minutes": 15, "energy_level": "low", "user_id": self.user_id},
        )
        self.assertEqual(quick.status_code, 200, quick.text)
        run = quick.json()["data"]
        task_id = run["primary_task"]["id"]
        feedback_path = f"{quick_path}/{run['run_id']}/feedback"
        liked = self.client.post(
            feedback_path, json={"action": "liked", "task_id": task_id},
        )
        self.assertEqual(liked.status_code, 200, liked.text)

        full_id = self.new_session()
        full_path = f"/api/v1/sessions/{full_id}"
        saved = self.client.put(
            full_path + "/preferences",
            json={"categories": ["energy", "recovery"], "duration": "half",
                  "budget": "low", "outing": "home", "company": "solo"},
        )
        self.assertEqual(saved.status_code, 200, saved.text)
        started = self.client.post(full_path + "/questionnaire/start", json={"mode": "quick"})
        self.assertEqual(started.status_code, 200, started.text)
        for question in started.json()["data"]["questions"]:
            answered = self.client.patch(
                full_path + f"/questionnaire/answers/{question['id']}", json={"value": 3},
            )
            self.assertEqual(answered.status_code, 200, answered.text)
        submitted = self.client.post(full_path + "/questionnaire/submit")
        self.assertEqual(submitted.status_code, 200, submitted.text)
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        plan = self.client.post(
            full_path + "/plan/generate",
            json={"free_start": now.isoformat(),
                  "free_end": (now + timedelta(hours=3)).isoformat(),
                  "density": "balanced", "user_id": self.user_id},
        )
        self.assertEqual(plan.status_code, 200, plan.text)
        self.assertTrue(plan.json()["data"]["recommendation"]["tasks"])
        self.assertTrue(plan.json()["data"]["plan"]["items"])

        summary = self.client.get(f"/api/v1/users/{self.user_id}/history/summary")
        self.assertEqual(summary.status_code, 200, summary.text)
        self.assertEqual(summary.json()["data"]["completed_count"], 0)

        disliked = self.client.post(
            feedback_path, json={"action": "disliked", "task_id": task_id},
        )
        self.assertEqual(disliked.status_code, 200, disliked.text)
        next_run = self.client.post(
            quick_path,
            json={"available_minutes": 15, "energy_level": "low", "user_id": self.user_id},
        )
        self.assertEqual(next_run.status_code, 200, next_run.text)
        result = next_run.json()["data"]
        ids = [item["id"] for item in [result["primary_task"], *result["alternatives"]] if item]
        self.assertNotIn(task_id, ids)


if __name__ == "__main__":
    unittest.main()
