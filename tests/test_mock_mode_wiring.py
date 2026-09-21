import os
import unittest
from unittest.mock import patch

from main import build_orchestrator, require_orchestrator


class MockModeWiringTests(unittest.TestCase):
    def test_mock_mode_is_opt_in_and_uses_generated_repository(self):
        with patch.dict(os.environ, {"SESSION_DATABASE_URL": "postgresql://unused", "TASK_GENERATION_MODE": "mock"}):
            with patch("main.PostgreSQLProfileRepository", return_value=object()), patch(
                "main.PostgreSQLPlanRepository", return_value=object()
            ), patch("main.PostgreSQLDeliveryRepository", return_value=object()), patch(
                "main.PostgresGeneratedTaskRepository", return_value=object()
            ) as generated_repo:
                orchestrator = build_orchestrator(object(), object())
            generated_repo.assert_called_once_with(
                "postgresql://unused",
                schema_init=False,
            )
        self.assertIsNotNone(orchestrator.mock_generation)

    def test_default_mode_does_not_create_mock_generator(self):
        with patch.dict(os.environ, {"SESSION_DATABASE_URL": "postgresql://unused"}):
            with patch.dict(os.environ, {"TASK_GENERATION_MODE": "rules"}), patch(
                "main.PostgreSQLProfileRepository", return_value=object()
            ), patch("main.PostgreSQLPlanRepository", return_value=object()), patch(
                "main.PostgreSQLDeliveryRepository", return_value=object()
            ):
                orchestrator = build_orchestrator(object(), object())
        self.assertIsNone(orchestrator.mock_generation)

    def test_adjustment_route_resolver_returns_injected_orchestrator(self):
        selected = object()
        self.assertIs(require_orchestrator(selected), selected)


if __name__ == "__main__":
    unittest.main()
