"""Run PostgreSQL migrations for the MVP backend."""

from __future__ import annotations

import os

from database_migrations import run_migrations


def main() -> None:
    database_url = os.getenv("SESSION_DATABASE_URL")
    if not database_url:
        raise SystemExit("请先设置 SESSION_DATABASE_URL")
    run_migrations(database_url)
    print("数据库迁移已完成")


if __name__ == "__main__":
    main()
