import unittest

from generated_task_repository import PostgresGeneratedTaskRepository


class FakeConnection:
    def __init__(self):
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, statement, params=None):
        self.statements.append((statement, params))
        return self

    def fetchone(self):
        return None


class GeneratedTaskRepositoryTests(unittest.TestCase):
    def test_schema_has_session_scope_and_generated_task_payload(self):
        connection = FakeConnection()
        repo = PostgresGeneratedTaskRepository("postgresql://unused", connect=lambda _: connection)
        ddl = "\n".join(statement for statement, _ in connection.statements)
        self.assertIn("CREATE TABLE IF NOT EXISTS ai_generation_runs", ddl)
        self.assertIn("CREATE TABLE IF NOT EXISTS generated_tasks", ddl)
        self.assertIn("REFERENCES sessions(id) ON DELETE CASCADE", ddl)
        self.assertIsNone(repo.get_run("sess_one", "key_one"))
        self.assertEqual(connection.statements[-1][1], ("sess_one", "key_one"))


if __name__ == "__main__":
    unittest.main()
