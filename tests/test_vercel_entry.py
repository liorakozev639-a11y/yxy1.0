import unittest

from fastapi.testclient import TestClient

from api.index import create_startup_error_app


class VercelEntryTests(unittest.TestCase):
    def test_startup_error_app_reports_sanitized_failure(self) -> None:
        app = create_startup_error_app(RuntimeError("bad password: secret-value"))
        client = TestClient(app)

        response = client.get("/health")

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertIsNone(payload["data"])
        self.assertEqual(payload["error"]["code"], "backend_startup_failed")
        self.assertIn("RuntimeError", payload["error"]["message"])
        self.assertNotIn("secret-value", payload["error"]["message"])


if __name__ == "__main__":
    unittest.main()
