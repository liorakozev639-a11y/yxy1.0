"""Session domain service and persistence repositories.

The MVP identifies a browser session only by ``session_id``.  The module is
HTTP-framework friendly, but contains no route registration; ``main.py`` owns
the public API.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from os import name
from typing import Any, Optional, Protocol

from fastapi import HTTPException
from pip._internal.network import session


class SessionStage:
    INTERESTS = "interests"
    PREFERENCES = "preferences"
    QUESTIONNAIRE = "questionnaire"


@dataclass
class Session:
    id: str
    stage: str
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    version: int = 1
    preferences: dict[str, Any] = field(default_factory=dict)



@dataclass
class User:
    id : int
    name : str
class SessionRepository(Protocol):
    def save(self, session: Session) -> None: ...

    def get(self, session_id: str) -> Optional[Session]: ...

    def delete(self, session_id: str) -> None: ...

    def saveUser(self, user):...

    def getUser(self, user_id: str):...

    def save_user_id(self, session: Session, user=None) -> None:

class PostgresSessionRepository:
    """Synchronous PostgreSQL repository for the small MVP data set."""

    def __init__(self, database_url: str) -> None:
        if not database_url:
            raise ValueError("database_url 不能为空")
        self.database_url = database_url
        self.init_schema()

    def _connect(self):
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError(
                "PostgreSQL 模式需要 psycopg，请安装 psycopg[binary]"
            ) from exc
        return psycopg.connect(self.database_url)

    def init_schema(self) -> None:
        statements = (
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                stage TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                preferences JSONB NOT NULL DEFAULT '{}'::jsonb
            )
            """,
            "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS stage TEXT",
            "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ",
            "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ",
            "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ",
            "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1",
            "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS preferences JSONB DEFAULT '{}'::jsonb",
            "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS token_hash TEXT",
            "ALTER TABLE sessions ALTER COLUMN token_hash DROP NOT NULL",
        )
        with self._connect() as connection:
            with connection.cursor() as cursor:
                for statement in statements:
                    cursor.execute(statement)

    def save(self, session: Session) -> None:
        from psycopg.types.json import Jsonb

        statement = """
        INSERT INTO sessions (
            id, stage, created_at, updated_at, expires_at, version, preferences
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            stage = EXCLUDED.stage,
            updated_at = EXCLUDED.updated_at,
            expires_at = EXCLUDED.expires_at,
            version = EXCLUDED.version,
            preferences = EXCLUDED.preferences
        """
        values = (
            session.id,
            session.stage,
            session.created_at,
            session.updated_at,
            session.expires_at,
            session.version,
            Jsonb(session.preferences),
        )
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, values)

    def save_user_id(self, session: Session, user=None) -> None:
        statement = """
        INSERT INTO sessions (
            id, name
        ) VALUES (%s, %s)
        """
        values = (
            user.id,
            user.name,
        )
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, values)

    def get(self, session_id: str) -> Optional[Session]:
        from psycopg.rows import dict_row

        statement = """
        SELECT id, stage, created_at, updated_at, expires_at, version, preferences
        FROM sessions
        WHERE id = %s
        """
        with self._connect() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(statement, (session_id,))
                row = cursor.fetchone()
        if row is None:
            return None

        s = Session(
            id=row["id"],
            stage=row["stage"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            expires_at=row["expires_at"],
            version=int(row["version"]),
            preferences=dict(row["preferences"] or {}),
        )
        return s

    def delete(self, session_id: str) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM sessions WHERE id = %s", (session_id,))


    def saveUser(self, user):
        statement = """
            INSERT INTO sessions (
                id, name
            ) VALUES (%s, %s)"""
        values = (
            user.id,
            user.stage,
        )
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, values)


    def getUser(self, user_id: str):
        from psycopg.rows import dict_row
        statement = """
            SELECT id, name
            FROM users
            WHERE id = %s
            """
        with self._connect() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(statement, (user_id,))
                row = cursor.fetchone()

        if row is None:
            return None

        return User(
            id=row["id"],
            name=row["name"],
        )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"

def make_user_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class SessionService:
    def __init__(self, repository: SessionRepository) -> None:
        self.repository = repository

    def saveUser(self, user: User) -> None:
        self.repository.save(user)

    def getUser(self, user_id: str) -> User:
        return self.repository.get(user_id)

    def create(self, expires_in_hours: int = 24) -> dict[str, Any]:
        if expires_in_hours <= 0:
            raise ValueError("expires_in_hours 必须大于 0")
        current = utc_now()
        session = Session(
            id=make_id("sess"),
            stage=SessionStage.INTERESTS,
            created_at=current,
            updated_at=current,
            expires_at=current + timedelta(hours=expires_in_hours),
        )
        self.repository.save(session)
        return self._payload(session, include_preferences=False)

    def createUser(self) -> dict[str, Any]:
        user = User(
            id = make_user_id("sess"),
            name = name,
        )
        self.repository.save_user_id(session)
        return self.user_payload(user)

    def require_active(self, session_id: str) -> Session:
        session = self.repository.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="会话不存在")
        if utc_now() >= session.expires_at:
            raise HTTPException(status_code=410, detail="会话已过期")
        return session

    def save_preferences(
        self,
        session_id: str,
        preferences: dict[str, Any],
    ) -> Session:
        session = self.require_active(session_id)
        session.preferences = dict(preferences)
        session.stage = SessionStage.QUESTIONNAIRE
        self._touch(session)
        self.repository.save(session)
        return session

    def restore(self, session_id: str) -> dict[str, Any]:
        return self._payload(self.require_active(session_id))

    def clear_data(self, session_id: str) -> None:
        session = self.require_active(session_id)
        session.preferences.clear()
        session.stage = SessionStage.INTERESTS
        self._touch(session)
        self.repository.save(session)

    @staticmethod
    def _touch(session: Session) -> None:
        session.updated_at = utc_now()
        session.version += 1

    @staticmethod
    def _payload(
        session: Session,
        *,
        include_preferences: bool = True,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "session_id": session.id,
            "stage": session.stage,
            "version": session.version,
            "expires_at": session.expires_at.isoformat(),
        }
        if include_preferences:
            payload["preferences"] = dict(session.preferences)
        return payload

    @staticmethod
    def user_payload(user: User) -> dict[str, Any]:
        return {
            "user_id": user.id,
            "user_name": user.name,
        }

def build_session_repository() -> PostgresSessionRepository:
    database_url = os.getenv("SESSION_DATABASE_URL")
    if not database_url:
        raise RuntimeError("必须设置 SESSION_DATABASE_URL")
    return PostgresSessionRepository(database_url)
