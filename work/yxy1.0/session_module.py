"""Session Module runnable example.

Run:
    python -m pip install fastapi uvicorn
    python examples/session_module.py

Open:
    http://127.0.0.1:8000/docs

The example uses an in-memory repository so it is easy to run locally.
Replace the repository with PostgreSQL in production.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(
    title="Free Time Agent - Session Module",
    version="1.0.0",
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


class InMemorySessionRepository:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def save(self, session: Session) -> None:
        self._sessions[session.id] = session

    def get(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_matches(token: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_token(token), expected_hash)


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class SessionService:
    def __init__(self, repository: InMemorySessionRepository) -> None:
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

    def require_valid(
        self,
        session_id: str,
        token: str,
    ) -> Session:
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
        return session

    def save_answer(
        self,
        session_id: str,
        token: str,
        question_id: str,
        value: int,
    ) -> Session:
        if value not in {1, 2, 3, 4}:
            raise HTTPException(
                status_code=400,
                detail="答案必须是 1、2、3 或 4",
            )

        session = self.require_valid(session_id, token)
        session.answers[question_id] = value
        session.stage = SessionStage.QUESTIONNAIRE
        self._touch(session)
        return session

    def restore(
        self,
        session_id: str,
        token: str,
    ) -> dict[str, Any]:
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

    def clear_data(
        self,
        session_id: str,
        token: str,
    ) -> None:
        session = self.require_valid(session_id, token)
        session.preferences.clear()
        session.answers.clear()
        session.profile.clear()
        session.plan.clear()
        session.stage = SessionStage.INTERESTS
        self._touch(session)

    @staticmethod
    def _touch(session: Session) -> None:
        session.updated_at = utc_now()
        session.version += 1


repository = InMemorySessionRepository()
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


def read_bearer_token(authorization: Optional[str]) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="需要 Authorization: Bearer <token>",
        )
    return authorization.removeprefix("Bearer ").strip()


def response(data: Any) -> dict[str, Any]:
    return {
        "requestId": make_id("req"),
        "data": data,
        "error": None,
    }


@app.post("/api/v1/sessions")
def create_session() -> dict[str, Any]:
    return response(service.create())


@app.get("/api/v1/sessions/{session_id}")
def get_session(
    session_id: str,
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    token = read_bearer_token(authorization)
    return response(service.restore(session_id, token))


@app.put("/api/v1/sessions/{session_id}/preferences")
def put_preferences(
    session_id: str,
    body: PreferencesInput,
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    token = read_bearer_token(authorization)
    session = service.save_preferences(
        session_id,
        token,
        body.model_dump(),
    )
    return response({"saved": True, "stage": session.stage})


@app.patch(
    "/api/v1/sessions/{session_id}/questionnaire/answers/{question_id}"
)
def patch_answer(
    session_id: str,
    question_id: str,
    body: AnswerInput,
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    token = read_bearer_token(authorization)
    service.save_answer(session_id, token, question_id, body.value)
    return response({"saved": True, "question_id": question_id})


@app.delete("/api/v1/sessions/{session_id}/data")
def delete_session_data(
    session_id: str,
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    token = read_bearer_token(authorization)
    service.clear_data(session_id, token)
    return response({"deleted": True})


if __name__ == "__main__":
    uvicorn.run(
        "session_module:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )
