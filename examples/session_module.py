"""MVP Session Module.

PostgreSQL mode (recommended for local deployment)::

    $env:SESSION_STORAGE = "postgres"
    $env:SESSION_DATABASE_URL = "postgresql://postgres:<password>@127.0.0.1:5433/free_time_agent"
    uv run --python 3.12 --with fastapi --with uvicorn --with psycopg[binary] python examples/session_module.py

Memory mode is available for isolated unit tests by setting
``SESSION_STORAGE=memory``. PostgreSQL mode creates the ``sessions`` table
automatically on startup.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Protocol

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field


agapp = FastAPI(
    title="Free Time Agent - Session Module",
    version="1.1.0",
)


class SessionStage:
    INTERESTS = "interests"
    PREFERENCES = "preferences"
    QUESTIONNAIRE = "questionnaire"
    RECOMMENDATION = "recommendation"
    PLANNING = "planning"
    CONFIRMED = "confirmed"
    EXECUTING = "executing"


@dataclass
class Session:
    id: str
    token_hash: str
    stage: str
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    version: int = 1
    preferences: dict[str, Any] = field(default_factory=dict)
    answers: dict[str, int] = field(default_factory=dict)
    profile: dict[str, Any] = field(default_factory=dict)
    plan: dict[str, Any] = field(default_factory=dict)


class SessionRepository(Protocol):
    def save(self, session: Session) -> None: ...

    def get(self, session_id: str) -> Optional[Session]: ...


class InMemorySessionRepository:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def save(self, session: Session) -> None:
        self._sessions[session.id] = session

    def get(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)


class PostgresSessionRepository:
    """Synchronous PostgreSQL repository for the MVP session aggregate."""

    def __init__(self, database_url: str) -> None:
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
        schema = """
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            token_hash TEXT NOT NULL,
            stage TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
            answers JSONB NOT NULL DEFAULT '{}'::jsonb,
            profile JSONB NOT NULL DEFAULT '{}'::jsonb,
            plan JSONB NOT NULL DEFAULT '{}'::jsonb
        )
        """
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(schema)

    def save(self, session: Session) -> None:
        from psycopg.types.json import Jsonb

        statement = """
        INSERT INTO sessions (
            id, token_hash, stage, created_at, updated_at, expires_at,
            version, preferences, answers, profile, plan
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            token_hash = EXCLUDED.token_hash,
            stage = EXCLUDED.stage,
            updated_at = EXCLUDED.updated_at,
            expires_at = EXCLUDED.expires_at,
            version = EXCLUDED.version,
            preferences = EXCLUDED.preferences,
            answers = EXCLUDED.answers,
            profile = EXCLUDED.profile,
            plan = EXCLUDED.plan
        """
        values = (
            session.id,
            session.token_hash,
            session.stage,
            session.created_at,
            session.updated_at,
            session.expires_at,
            session.version,
            Jsonb(session.preferences),
            Jsonb(session.answers),
            Jsonb(session.profile),
            Jsonb(session.plan),
        )
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, values)

    def get(self, session_id: str) -> Optional[Session]:
        from psycopg.rows import dict_row

        statement = """
        SELECT id, token_hash, stage, created_at, updated_at, expires_at,
               version, preferences, answers, profile, plan
        FROM sessions
        WHERE id = %s
        """
        with self._connect() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(statement, (session_id,))
                row = cursor.fetchone()

        if row is None:
            return None
        return Session(
            id=row["id"],
            token_hash=row["token_hash"],
            stage=row["stage"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            expires_at=row["expires_at"],
            version=row["version"],
            preferences=dict(row["preferences"] or {}),
            answers={key: int(value) for key, value in (row["answers"] or {}).items()},
            profile=dict(row["profile"] or {}),
            plan=dict(row["plan"] or {}),
        )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_matches(token: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_token(token), expected_hash)


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class SessionService:
    def __init__(self, repository: SessionRepository) -> None:
        self.repository = repository

    def create(self, expires_in_hours: int = 24) -> dict[str, Any]:
        session_id = make_id("sess")
        token = secrets.token_urlsafe(32)
        current = utc_now()
        session = Session(
            id=session_id,
            token_hash=hash_token(token),
            stage=SessionStage.INTERESTS,
            created_at=current,
            updated_at=current,
            expires_at=current + timedelta(hours=expires_in_hours),
        )
        self.repository.save(session)
        return {
            "session_id": session_id,
            "token": token,
            "stage": session.stage,
            "version": session.version,
            "expires_at": session.expires_at.isoformat(),
        }

    def require_valid(self, session_id: str, token: str) -> Session:
        session = self.repository.get(session_id)
        if session is None:
            raise HTTPException(status_code=401, detail="会话不存在")
        if utc_now() >= session.expires_at:
            raise HTTPException(status_code=401, detail="会话已过期")
        if not token_matches(token, session.token_hash):
            raise HTTPException(status_code=401, detail="会话 token 无效")
        return session

    def save_preferences(
        self,
        session_id: str,
        token: str,
        preferences: dict[str, Any],
    ) -> Session:
        session = self.require_valid(session_id, token)
        session.preferences = preferences
        session.stage = SessionStage.QUESTIONNAIRE
        self._touch(session)
        self.repository.save(session)
        return session

    def save_answer(
        self,
        session_id: str,
        token: str,
        question_id: str,
        value: int,
    ) -> Session:
        if value not in {1, 2, 3, 4}:
            raise HTTPException(status_code=400, detail="答案必须是 1、2、3 或 4")
        session = self.require_valid(session_id, token)
        session.answers[question_id] = value
        session.stage = SessionStage.QUESTIONNAIRE
        self._touch(session)
        self.repository.save(session)
        return session

    def restore(self, session_id: str, token: str) -> dict[str, Any]:
        session = self.require_valid(session_id, token)
        return {
            "session_id": session.id,
            "stage": session.stage,
            "version": session.version,
            "preferences": session.preferences,
            "answers": session.answers,
            "profile": session.profile,
            "plan": session.plan,
            "expires_at": session.expires_at.isoformat(),
        }

    def clear_data(self, session_id: str, token: str) -> None:
        session = self.require_valid(session_id, token)
        session.preferences.clear()
        session.answers.clear()
        session.profile.clear()
        session.plan.clear()
        session.stage = SessionStage.INTERESTS
        self._touch(session)
        self.repository.save(session)

    @staticmethod
    def _touch(session: Session) -> None:
        session.updated_at = utc_now()
        session.version += 1


def build_repository() -> SessionRepository:
    storage = os.getenv("SESSION_STORAGE", "memory").lower()
    if storage == "postgres":
        database_url = os.getenv("SESSION_DATABASE_URL")
        if not database_url:
            raise RuntimeError("PostgreSQL 模式需要设置 SESSION_DATABASE_URL")
        return PostgresSessionRepository(database_url)
    if storage == "memory":
        return InMemorySessionRepository()
    raise RuntimeError("SESSION_STORAGE 只能是 postgres 或 memory")


repository = build_repository()
service = SessionService(repository)


class PreferencesInput(BaseModel):
    categories: list[str] = Field(min_length=1, max_length=5)
    duration: str
    budget: str
    outing: str
    company: str
    city_or_campus: Optional[str] = Field(default=None, max_length=128)
    rest_only: bool = False


class AnswerInput(BaseModel):
    value: int = Field(ge=1, le=4)


bearer_scheme = HTTPBearer(auto_error=False)


def read_bearer_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="需要 Authorization: Bearer <token>",
        )
    token = credentials.credentials.strip()
    if not token:
        raise HTTPException(status_code=401, detail="Bearer token 不能为空")
    return token


def response(data: Any) -> dict[str, Any]:
    return {"requestId": make_id("req"), "data": data, "error": None}


@app.post("/api/v1/sessions")
def create_session() -> dict[str, Any]:
    return response(service.create())


@app.get("/api/v1/sessions/{session_id}")
def get_session(
    session_id: str,
    token: str = Depends(read_bearer_token),
) -> dict[str, Any]:
    return response(service.restore(session_id, token))


@app.put("/api/v1/sessions/{session_id}/preferences")
def put_preferences(
    session_id: str,
    body: PreferencesInput,
    token: str = Depends(read_bearer_token),
) -> dict[str, Any]:
    session = service.save_preferences(
        session_id,
        token,
        body.model_dump(),
    )
    return response({"saved": True, "stage": session.stage})


@app.patch("/api/v1/sessions/{session_id}/questionnaire/answers/{question_id}")
def patch_answer(
    session_id: str,
    question_id: str,
    body: AnswerInput,
    token: str = Depends(read_bearer_token),
) -> dict[str, Any]:
    service.save_answer(session_id, token, question_id, body.value)
    return response({"saved": True, "question_id": question_id})


@app.delete("/api/v1/sessions/{session_id}/data")
def delete_session_data(
    session_id: str,
    token: str = Depends(read_bearer_token),
) -> dict[str, Any]:
    service.clear_data(session_id, token)
    return response({"deleted": True})


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
