"""Safety boundary and cleanup for quick-mode database integration tests."""

from __future__ import annotations

import os

import psycopg
from psycopg.conninfo import conninfo_to_dict


def require_test_database() -> str:
    url = os.getenv("SESSION_DATABASE_URL", "")
    if not url:
        raise RuntimeError("极简模式集成测试需要 SESSION_DATABASE_URL 指向独立测试库")
    options = conninfo_to_dict(url)
    name = options.get("dbname", "")
    host = options.get("host", "")
    if host not in {"127.0.0.1", "localhost"} or not (
        name.startswith("test_") or name.endswith("_test")
    ):
        raise RuntimeError("极简模式集成测试只允许连接本机且名称带 test 的数据库")
    return url


def delete_test_user(database_url: str, user_id: str) -> None:
    with psycopg.connect(database_url) as connection:
        connection.execute("DELETE FROM user_profiles WHERE id = %s", (user_id,))
