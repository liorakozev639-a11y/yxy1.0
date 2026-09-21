"""Versioned PostgreSQL schema migrations for the production application."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import psycopg


MIGRATIONS_DIR = Path(__file__).with_name("migrations")


def migration_files() -> list[Path]:
    """Return migration files in execution order."""
    return sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))


def _version(path: Path) -> int:
    return int(path.name.split("_", 1)[0])


def _statements(sql: str) -> Iterator[str]:
    for statement in sql.split(";"):
        cleaned = statement.strip()
        if cleaned:
            yield cleaned


def run_migrations(database_url: str) -> None:
    """Apply each unapplied migration exactly once."""
    if not database_url:
        raise ValueError("database_url 不能为空")
    files = migration_files()
    versions = [_version(path) for path in files]
    if versions != sorted(set(versions)):
        raise RuntimeError("数据库迁移版本必须唯一且递增")

    with psycopg.connect(database_url) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        applied = {
            int(row[0])
            for row in connection.execute(
                "SELECT version FROM schema_migrations"
            ).fetchall()
        }
        for path in files:
            version = _version(path)
            if version in applied:
                continue
            for statement in _statements(path.read_text(encoding="utf-8")):
                connection.execute(statement)
            connection.execute(
                """
                INSERT INTO schema_migrations (version, name)
                VALUES (%s, %s)
                """,
                (version, path.name),
            )


@contextmanager
def schema_migrations_managed() -> Iterator[None]:
    """Compatibility hook for callers that need a migration-owned startup."""
    yield
