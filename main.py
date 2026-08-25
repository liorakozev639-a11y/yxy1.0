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
from execution_service import ExecutionService
from feedback_service import FeedbackService
from review_service import ReviewService
from mvp_orchestrator import (
    GeneratePlanRequest,
    MVPOrchestrator,
    PostgreSQLPlanRepository,
    PostgreSQLProfileRepository,
)
from plan_module import PlanManagementService
from recommendation_memory import RecommendationMemory
from session_module import PostgresSessionRepository, SessionService
from task_repository import TaskRepository
from user_history_service import UserHistoryService


ALLOWED_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]
ALLOWED_ORIGINS.extend(
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", "").split(",")
    if origin.strip()
)


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
    user_id: Optional[str] = None


class AnonymousUserInput(BaseModel):
    user_id: Optional[str] = None


class PlanItemTimeInput(BaseModel):
    expected_version: int = Field(ge=1)
    start_at: datetime
    end_at: datetime


class PlanItemMutationInput(BaseModel):
    expected_version: int = Field(ge=1)
    user_id: Optional[str] = None


class PlanReplaceInput(PlanItemMutationInput):
    replacement_task_id: Optional[str] = Field(default=None, max_length=128)


class CustomTaskInput(BaseModel):
    expected_version: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=128)
    duration_minutes: int = Field(gt=0, le=480)
    category: Optional[str] = None


class PlanConfirmInput(BaseModel):
    expected_version: int = Field(ge=1)


class PlanReplanInput(BaseModel):
    expected_version: int = Field(ge=1)
    density: Optional[Literal["light", "balanced", "full"]] = None


class ExecutionTimeInput(BaseModel):
    now: Optional[datetime] = None
    user_id: Optional[str] = None


class ExecutionPrepareInput(BaseModel):
    user_id: Optional[str] = None
    energy: Literal["high", "medium", "low"]


class FeedbackInput(BaseModel):
    rating: int = Field(ge=1, le=5)
    reasons: list[str] = Field(default_factory=list, max_length=3)


class ReflectionInput(BaseModel):
    sentiment: Literal["satisfied", "neutral", "dissatisfied"]


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


def _session_id_from_plan(manager: PlanManagementService, plan_id: str) -> str:
    return manager.session_id_for_plan(plan_id)


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
    memory: RecommendationMemory | None = None,
    user_history: UserHistoryService | None = None,
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
        memory=memory,
        user_history=user_history,
    )


def create_app(
    session_service: Optional[SessionService] = None,
    questionnaire_service: Optional[QuestionnaireService] = None,
    orchestrator: Optional[MVPOrchestrator] = None,
    plan_service: Optional[PlanManagementService] = None,
    execution_service: Optional[ExecutionService] = None,
    feedback_service: Optional[FeedbackService] = None,
    review_service: Optional[ReviewService] = None,
    memory: Optional[RecommendationMemory] = None,
    user_history: Optional[UserHistoryService] = None,
) -> FastAPI:
    if (session_service is None) != (questionnaire_service is None):
        raise ValueError("必须同时提供 Session 和 Questionnaire 服务")
    if session_service is None or questionnaire_service is None:
        session_service, questionnaire_service = build_services()
    database_url = os.getenv("SESSION_DATABASE_URL")
    if (
        memory is None
        and database_url
        and isinstance(session_service, SessionService)
    ):
        memory = RecommendationMemory(
            database_url,
            session_service,
            TaskRepository(),
        )
    if user_history is None and database_url:
        user_history = UserHistoryService(database_url, TaskRepository())
    if orchestrator is None:
        orchestrator = build_orchestrator(
            session_service,
            questionnaire_service,
            memory,
            user_history,
        )
    if (
        plan_service is None
        and os.getenv("SESSION_DATABASE_URL")
        and isinstance(session_service, SessionService)
    ):
        plan_service = PlanManagementService(
            os.environ["SESSION_DATABASE_URL"],
            session_service,
            orchestrator,
            memory=memory,
            user_history=user_history,
        )
    if (
        execution_service is None
        and os.getenv("SESSION_DATABASE_URL")
        and isinstance(session_service, SessionService)
    ):
        execution_service = ExecutionService(
            os.environ["SESSION_DATABASE_URL"],
            session_service,
            memory=memory,
            user_history=user_history,
        )
    if (
        feedback_service is None
        and os.getenv("SESSION_DATABASE_URL")
        and isinstance(session_service, SessionService)
    ):
        feedback_service = FeedbackService(
            os.environ["SESSION_DATABASE_URL"],
            session_service,
            memory=memory,
        )
    if (
        review_service is None
        and os.getenv("SESSION_DATABASE_URL")
        and isinstance(session_service, SessionService)
        and execution_service is not None
    ):
        review_service = ReviewService(
            os.environ["SESSION_DATABASE_URL"],
            session_service,
            execution_service,
        )

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

    @app.post("/api/v1/users/anonymous")
    def create_anonymous_user(body: AnonymousUserInput) -> dict[str, Any]:
        if user_history is None:
            raise HTTPException(status_code=503, detail="用户历史服务未配置")
        return success(user_history.ensure_user(body.user_id))

    @app.get("/api/v1/users/{user_id}/history/summary")
    def get_user_history_summary(user_id: str) -> dict[str, Any]:
        if user_history is None:
            raise HTTPException(status_code=503, detail="用户历史服务未配置")
        return success(user_history.summary(user_id))

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

    @app.get("/api/v1/sessions/{session_id}/profile/insight")
    def get_profile_insight(session_id: str) -> dict[str, Any]:
        return success(orchestrator.build_profile_insight(session_id))

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
                user_id=body.user_id,
            )
        )

    @app.get("/api/v1/sessions/{session_id}/plan")
    def get_plan(session_id: str) -> dict[str, Any]:
        plan = (
            plan_service.get(session_id)
            if plan_service is not None
            else orchestrator.get_plan(session_id)
        )
        if plan is None:
            raise HTTPException(status_code=404, detail="计划尚未生成")
        return success(plan)

    def require_plan_service() -> PlanManagementService:
        if plan_service is None:
            raise HTTPException(status_code=503, detail="计划管理服务未配置")
        return plan_service

    def require_execution_service() -> ExecutionService:
        if execution_service is None:
            raise HTTPException(status_code=503, detail="执行服务未配置")
        return execution_service

    def require_feedback_service() -> FeedbackService:
        if feedback_service is None:
            raise HTTPException(status_code=503, detail="反馈服务未配置")
        return feedback_service

    def require_review_service() -> ReviewService:
        if review_service is None:
            raise HTTPException(status_code=503, detail="计划复盘服务未配置")
        return review_service

    @app.patch("/api/v1/plans/{plan_id}/items/{item_id}")
    def edit_plan_item(
        plan_id: str,
        item_id: str,
        body: PlanItemTimeInput,
    ) -> dict[str, Any]:
        manager = require_plan_service()
        return success(
            manager.edit_item(
                session_id=_session_id_from_plan(manager, plan_id),
                plan_id=plan_id,
                item_id=item_id,
                expected_version=body.expected_version,
                start_at=body.start_at.isoformat(),
                end_at=body.end_at.isoformat(),
            )
        )

    @app.post("/api/v1/plans/{plan_id}/items/{item_id}/replace")
    def replace_plan_item(
        plan_id: str,
        item_id: str,
        body: PlanReplaceInput,
    ) -> dict[str, Any]:
        manager = require_plan_service()
        session_id = _session_id_from_plan(manager, plan_id)
        return success(
            manager.replace_item(
                session_id,
                plan_id,
                item_id,
                body.expected_version,
                body.replacement_task_id,
                body.user_id,
            )
        )

    @app.post("/api/v1/plans/{plan_id}/items/{item_id}/skip")
    def skip_plan_item(
        plan_id: str,
        item_id: str,
        body: PlanItemMutationInput,
    ) -> dict[str, Any]:
        manager = require_plan_service()
        session_id = _session_id_from_plan(manager, plan_id)
        return success(manager.skip_item(session_id, plan_id, item_id, body.expected_version))

    @app.post("/api/v1/plans/{plan_id}/items/{item_id}/replace-easier")
    def replace_plan_item_easier(
        plan_id: str,
        item_id: str,
        body: PlanItemMutationInput,
    ) -> dict[str, Any]:
        manager = require_plan_service()
        session_id = _session_id_from_plan(manager, plan_id)
        return success(
            manager.replace_item_easier(
                session_id, plan_id, item_id, body.expected_version, body.user_id
            )
        )

    @app.post("/api/v1/plans/{plan_id}/custom-tasks")
    def add_custom_task(plan_id: str, body: CustomTaskInput) -> dict[str, Any]:
        manager = require_plan_service()
        session_id = _session_id_from_plan(manager, plan_id)
        return success(
            manager.add_custom_task(
                session_id,
                plan_id,
                body.expected_version,
                body.title,
                body.duration_minutes,
                body.category,
            )
        )

    @app.post("/api/v1/plans/{plan_id}/confirm")
    def confirm_plan(plan_id: str, body: PlanConfirmInput) -> dict[str, Any]:
        manager = require_plan_service()
        session_id = _session_id_from_plan(manager, plan_id)
        return success(manager.confirm(session_id, plan_id, body.expected_version))

    @app.post("/api/v1/plans/{plan_id}/replan")
    def replan(plan_id: str, body: PlanReplanInput) -> dict[str, Any]:
        manager = require_plan_service()
        session_id = _session_id_from_plan(manager, plan_id)
        return success(manager.replan(session_id, plan_id, body.expected_version, body.density))

    def execute_plan_item(
        plan_id: str,
        item_id: str,
        action: str,
        body: ExecutionTimeInput,
    ) -> dict[str, Any]:
        manager = require_plan_service()
        service = require_execution_service()
        session_id = _session_id_from_plan(manager, plan_id)
        return success(
            service.execute(
                session_id,
                plan_id,
                item_id,
                action,
                now=body.now,
                user_id=body.user_id,
            )
        )

    @app.post("/api/v1/plans/{plan_id}/items/{item_id}/execution/start")
    def start_execution(
        plan_id: str,
        item_id: str,
        body: ExecutionTimeInput,
    ) -> dict[str, Any]:
        return execute_plan_item(plan_id, item_id, "start", body)

    @app.post("/api/v1/plans/{plan_id}/items/{item_id}/execution/prepare")
    def prepare_execution(
        plan_id: str,
        item_id: str,
        body: ExecutionPrepareInput,
    ) -> dict[str, Any]:
        return success({
            "item_id": item_id,
            "energy": body.energy,
            "recommended_action": "replace_easier" if body.energy == "low" else "start",
            "can_start": body.energy in {"high", "medium"},
        })

    @app.post("/api/v1/plans/{plan_id}/items/{item_id}/execution/complete")
    def complete_execution(
        plan_id: str,
        item_id: str,
        body: ExecutionTimeInput,
    ) -> dict[str, Any]:
        return execute_plan_item(plan_id, item_id, "complete", body)

    @app.post("/api/v1/plans/{plan_id}/items/{item_id}/execution/skip")
    def skip_execution(
        plan_id: str,
        item_id: str,
        body: ExecutionTimeInput,
    ) -> dict[str, Any]:
        return execute_plan_item(plan_id, item_id, "skip", body)

    @app.post("/api/v1/plans/{plan_id}/items/{item_id}/execution/check-deadline")
    def check_execution_deadline(
        plan_id: str,
        item_id: str,
        body: ExecutionTimeInput,
    ) -> dict[str, Any]:
        manager = require_plan_service()
        service = require_execution_service()
        session_id = _session_id_from_plan(manager, plan_id)
        return success(
            service.check_deadline(
                session_id,
                plan_id,
                item_id,
                now=body.now,
            )
        )

    @app.get("/api/v1/plans/{plan_id}/execution/events")
    def get_execution_events(
        plan_id: str,
        item_id: Optional[str] = None,
    ) -> dict[str, Any]:
        manager = require_plan_service()
        service = require_execution_service()
        session_id = _session_id_from_plan(manager, plan_id)
        return success(service.events(session_id, plan_id, item_id))

    @app.post("/api/v1/plans/{plan_id}/execution/refresh")
    def refresh_plan_execution(plan_id: str) -> dict[str, Any]:
        manager = require_plan_service()
        service = require_review_service()
        session_id = _session_id_from_plan(manager, plan_id)
        return success(service.refresh_plan(session_id, plan_id))

    @app.post("/api/v1/plans/{plan_id}/items/{item_id}/reflection")
    def save_reflection(
        plan_id: str,
        item_id: str,
        body: ReflectionInput,
    ) -> dict[str, Any]:
        manager = require_plan_service()
        service = require_review_service()
        session_id = _session_id_from_plan(manager, plan_id)
        return success(
            service.save_reflection(
                session_id,
                plan_id,
                item_id,
                body.sentiment,
            )
        )

    @app.get("/api/v1/plans/{plan_id}/review")
    def get_plan_review(plan_id: str) -> dict[str, Any]:
        manager = require_plan_service()
        service = require_review_service()
        session_id = _session_id_from_plan(manager, plan_id)
        return success(service.get_review(session_id, plan_id))

    @app.post("/api/v1/plans/{plan_id}/items/{item_id}/feedback")
    def save_feedback(
        plan_id: str,
        item_id: str,
        body: FeedbackInput,
    ) -> dict[str, Any]:
        manager = require_plan_service()
        service = require_feedback_service()
        session_id = _session_id_from_plan(manager, plan_id)
        return success(
            service.save(
                session_id,
                plan_id,
                item_id,
                rating=body.rating,
                reasons=body.reasons,
            )
        )

    @app.get("/api/v1/plans/{plan_id}/feedback")
    def list_feedback(plan_id: str) -> dict[str, Any]:
        manager = require_plan_service()
        service = require_feedback_service()
        session_id = _session_id_from_plan(manager, plan_id)
        return success(service.list_for_plan(session_id, plan_id))

    return app


app = create_app() if os.getenv("SESSION_DATABASE_URL") else FastAPI(
    title="Free Time Agent API",
    version="1.0.0",
)


if __name__ == "__main__":
    if not os.getenv("SESSION_DATABASE_URL"):
        raise RuntimeError("启动服务前必须设置 SESSION_DATABASE_URL")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
