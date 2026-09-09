import unittest

from fastapi.testclient import TestClient

from main import create_unconfigured_app


class UnconfiguredAppTests(unittest.TestCase):
    def test_health_reports_missing_database_url(self) -> None:
        client = TestClient(create_unconfigured_app())

        response = client.get("/health")

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertIsNone(payload["data"])
        self.assertEqual(payload["error"]["code"], "database_not_configured")
        self.assertIn("SESSION_DATABASE_URL", payload["error"]["message"])

    def test_api_routes_report_missing_database_url(self) -> None:
        client = TestClient(create_unconfigured_app())

        response = client.post("/api/v1/sessions")

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertIsNone(payload["data"])
        self.assertEqual(payload["error"]["code"], "database_not_configured")


if __name__ == "__main__":
    unittest.main()
