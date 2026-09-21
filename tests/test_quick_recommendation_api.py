from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from main import create_app


class QuickRecommendationApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(create_app())

    def setUp(self) -> None:
        self.session_id = self.client.post("/api/v1/sessions").json()["data"]["session_id"]
        self.user_id = self.client.post("/api/v1/users/anonymous", json={}).json()["data"]["user_id"]
        self.path = f"/api/v1/sessions/{self.session_id}/quick-recommendations"

    def generate(self, minutes: int = 15, energy: str = "low"):
        return self.client.post(
            self.path,
            json={"available_minutes": minutes, "energy_level": energy,
                  "user_id": self.user_id},
        )

    def test_invalid_inputs_are_rejected_before_recommendation(self) -> None:
        for minutes in (0, -1, 481, 999999):
            self.assertEqual(self.generate(minutes).status_code, 422)
        self.assertEqual(self.generate(15, "unknown").status_code, 422)
        latest = self.client.get(self.path + "/latest").json()["data"]
        self.assertIsNone(latest["run_id"])

    def test_unanswered_questionnaire_can_get_one_primary_and_later_restore(self) -> None:
        response = self.generate()
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()["data"]
        self.assertIsNotNone(data["primary_task"])
        self.assertTrue(data["primary_task"]["first_action"])
        self.assertLessEqual(len(data["alternatives"]), 9)
        ids = [data["primary_task"]["id"], *[item["id"] for item in data["alternatives"]]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(data["constraints"], {
            "budget_limit": 0, "outing": "home", "company": "solo",
        })
        latest = self.client.get(self.path + "/latest")
        self.assertEqual(latest.status_code, 200)
        self.assertEqual(latest.json()["data"]["run_id"], data["run_id"])

    def test_feedback_is_bound_to_run_and_dislike_does_not_cycle_back(self) -> None:
        data = self.generate(30).json()["data"]
        task_id = data["primary_task"]["id"]
        feedback_path = f"{self.path}/{data['run_id']}/feedback"
        self.assertIn(
            self.client.post(feedback_path, json={"action": "liked", "task_id": "not_in_run"}).status_code,
            {404, 409},
        )
        other_session = self.client.post("/api/v1/sessions").json()["data"]["session_id"]
        self.assertIn(
            self.client.post(
                f"/api/v1/sessions/{other_session}/quick-recommendations/{data['run_id']}/feedback",
                json={"action": "disliked", "task_id": task_id},
            ).status_code,
            {404, 409},
        )
        self.assertEqual(
            self.client.post(feedback_path, json={"action": "disliked", "task_id": task_id}).status_code,
            200,
        )
        latest = self.client.get(self.path + "/latest").json()["data"]
        self.assertNotEqual((latest["primary_task"] or {}).get("id"), task_id)
        next_run = self.generate(30).json()["data"]
        next_ids = [item["id"] for item in [next_run["primary_task"], *next_run["alternatives"]] if item]
        self.assertNotIn(task_id, next_ids)

    def test_rest_is_idempotent_and_not_completion(self) -> None:
        data = self.generate(1).json()["data"]
        self.assertIsNone(data["primary_task"])
        self.assertEqual(data["alternatives"], [])
        path = f"{self.path}/{data['run_id']}/feedback"
        for _ in range(2):
            response = self.client.post(path, json={"action": "rest_selected"})
            self.assertEqual(response.status_code, 200, response.text)
        latest = self.client.get(self.path + "/latest").json()["data"]
        self.assertEqual(latest["feedback"], [{"action": "rest_selected", "task_id": None}])
        summary = self.client.get(f"/api/v1/users/{self.user_id}/history/summary")
        self.assertEqual(summary.json()["data"]["completed_count"], 0)


if __name__ == "__main__":
    unittest.main()
