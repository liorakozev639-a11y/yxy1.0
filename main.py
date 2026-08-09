"""Unified FastAPI entry point for Session and Questionnaire modules."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Literal, Optional

import psycopg
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from questionnaire_module import (
    PostgresQuestionnaireRepository,
    QuestionnaireService,
)
from delivery_module import PostgreSQLDeliveryRepository, WebDeliveryService
from mvp_orchestrator import (
    GeneratePlanRequest,
    MVPOrchestrator,
    PostgreSQLPlanRepository,
    PostgreSQLProfileRepository,
)
from session_module import PostgresSessionRepository, SessionService
from task_repository import TaskRepository


ALLOWED_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]


class PreferencesInput(BaseModel):
    categories: list[str] = Field(min_length=1, max_length=5)
    duration: str
    budget: str
    outing: Literal["home", "nearby", "city", "any"]
    company: Literal["solo", "group", "both"]
    city_or_campus: Optional[str] = Field(default=None, max_length=128)
    rest_only: bool = False


class StartQuestionnaireInput(BaseModel):
    mode: Literal["quick", "deep"]


class AnswerInput(BaseModel):
    value: int = Field(ge=1, le=4)


class GeneratePlanInput(BaseModel):
    free_start: datetime
    free_end: datetime
    density: Literal["light", "balanced", "full"] = "balanced"


def success(data: Any) -> dict[str, Any]:
    """

    :rtype: dict[str, Any]
    """
    return {"data": data, "error": None}


def error_code(status_code: int) -> str:
    return {
        400: "invalid_request",
        404: "session_not_found",
        409: "questionnaire_conflict",
        410: "session_expired",
        422: "validation_error",
    }.get(status_code, "request_failed")


def build_services() -> tuple[SessionService, QuestionnaireService]:
    database_url = os.getenv("SESSION_DATABASE_URL")
    if not database_url:
        raise RuntimeError("启动服务前必须设置 SESSION_DATABASE_URL")
    session_service = SessionService(PostgresSessionRepository(database_url))
    questionnaire_service = QuestionnaireService(
        session_service,
        PostgresQuestionnaireRepository(database_url),
    )
    return session_service, questionnaire_service


def build_orchestrator(
    session_service: SessionService,
    questionnaire_service: QuestionnaireService,
) -> MVPOrchestrator:
    database_url = os.getenv("SESSION_DATABASE_URL")
    if not database_url:
        raise RuntimeError("启动整合服务前必须设置 SESSION_DATABASE_URL")
    return MVPOrchestrator(
        sessions=session_service,
        questionnaire=questionnaire_service,
        tasks=TaskRepository(),
        profiles=PostgreSQLProfileRepository(database_url),
        plans=PostgreSQLPlanRepository(database_url),
        delivery=WebDeliveryService(
            PostgreSQLDeliveryRepository(database_url),
        ),
    )


def create_app(
    session_service: Optional[SessionService] = None,
    questionnaire_service: Optional[QuestionnaireService] = None,
    orchestrator: Optional[MVPOrchestrator] = None,
) -> FastAPI:
    if (session_service is None) != (questionnaire_service is None):
        raise ValueError("必须同时提供 Session 和 Questionnaire 服务")
    if session_service is None or questionnaire_service is None:
        session_service, questionnaire_service = build_services()
    if orchestrator is None:
        orchestrator = build_orchestrator(session_service, questionnaire_service)

    app = FastAPI(
        title="Free Time Agent API",
        version="1.0.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(_, exc: HTTPException) -> JSONResponse:
        details = exc.detail if isinstance(exc.detail, dict) else None
        message = (
            str(exc.detail.get("message", "请求失败"))
            if details is not None
            else str(exc.detail)
        )
        error: dict[str, Any] = {
            "code": error_code(exc.status_code),
            "message": message,
        }
        if details is not None:
            error["details"] = details
        return JSONResponse(
            status_code=exc.status_code,
            content=jsonable_encoder({"data": None, "error": error}),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder(
                {
                    "data": None,
                    "error": {
                        "code": "validation_error",
                        "message": "请求参数不合法",
                        "details": exc.errors(),
                    },
                }
            ),
        )

    @app.exception_handler(psycopg.Error)
    async def handle_database_error(_, __: psycopg.Error) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "data": None,
                "error": {
                    "code": "database_unavailable",
                    "message": "数据库暂时不可用",
                },
            },
        )

    @app.post("/api/v1/sessions", status_code=201)
    def create_session() -> dict[str, Any]:
        return success(session_service.create())

    @app.get("/api/v1/sessions/{session_id}")
    def get_session(session_id: str) -> dict[str, Any]:
        return success(session_service.restore(session_id))

    @app.put("/api/v1/sessions/{session_id}/preferences")
    def save_preferences(
        session_id: str,
        body: PreferencesInput,
    ) -> dict[str, Any]:
        session = session_service.save_preferences(
            session_id,
            body.model_dump(),
        )
        s1 =  success(
            {
                "saved": True,
                "stage": session.stage,
                "version": session.version,
            }
        )
        return s1

    @app.delete("/api/v1/sessions/{session_id}/data")
    def clear_session_data(session_id: str) -> dict[str, Any]:
        questionnaire_service.clear(session_id)
        session_service.clear_data(session_id)
        return success({"cleared": True})

    @app.post("/api/v1/sessions/{session_id}/questionnaire/start")
    def start_questionnaire(
        session_id: str,
        body: StartQuestionnaireInput,
    ) -> dict[str, Any]:
        return success(questionnaire_service.start(session_id, body.mode))

    @app.patch(
        "/api/v1/sessions/{session_id}/questionnaire/answers/{question_id}"
    )
    def save_answer(
        session_id: str,
        question_id: str,
        body: AnswerInput,
    ) -> dict[str, Any]:
        return success(
            questionnaire_service.save_answer(
                session_id,
                question_id,
                body.value,
            )
        )

    @app.post(
        "/api/v1/sessions/{session_id}/questionnaire/skip/{question_id}"
    )
    def skip_question(session_id: str, question_id: str) -> dict[str, Any]:
        return success(
            questionnaire_service.skip_question(session_id, question_id)
        )

    @app.get("/api/v1/sessions/{session_id}/questionnaire/progress")
    def get_progress(session_id: str) -> dict[str, Any]:
        return success(questionnaire_service.progress(session_id))

    @app.post("/api/v1/sessions/{session_id}/questionnaire/submit")
    def submit_questionnaire(session_id: str) -> dict[str, Any]:
        return success(questionnaire_service.submit(session_id))

    @app.post("/api/v1/sessions/{session_id}/plan/generate")
    def generate_plan(
        session_id: str,
        body: GeneratePlanInput,
    ) -> dict[str, Any]:
        return success(
            orchestrator.generate_plan(
                session_id,
                GeneratePlanRequest(
                    free_start=body.free_start,
                    free_end=body.free_end,
                    density=body.density,
                ),
            )
        )

    @app.get("/api/v1/sessions/{session_id}/plan")
    def get_plan(session_id: str) -> dict[str, Any]:
        plan = orchestrator.get_plan(session_id)
        if plan is None:
            raise HTTPException(status_code=404, detail="计划尚未生成")
        return success(plan)

    return app


app = create_app() if os.getenv("SESSION_DATABASE_URL") else FastAPI(
    title="Free Time Agent API",
    version="1.0.0",
)


if __name__ == "__main__":
    if not os.getenv("SESSION_DATABASE_URL"):
        raise RuntimeError("启动服务前必须设置 SESSION_DATABASE_URL")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
