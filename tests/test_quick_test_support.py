from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from quick_test_support import require_test_database


class QuickTestDatabaseGuardTest(unittest.TestCase):
    def test_rejects_missing_or_non_test_database(self) -> None:
        for url in (
            "",
            "postgresql://postgres@127.0.0.1:5433/free_time_agent",
            "postgresql://postgres@db.example.com:5432/free_time_agent_test",
        ):
            with self.subTest(url=url), patch.dict(os.environ, {"SESSION_DATABASE_URL": url}):
                with self.assertRaises(RuntimeError):
                    require_test_database()

    def test_accepts_local_test_database(self) -> None:
        url = "postgresql://postgres@127.0.0.1:5544/free_time_agent_quick_test"
        with patch.dict(os.environ, {"SESSION_DATABASE_URL": url}):
            self.assertEqual(require_test_database(), url)
