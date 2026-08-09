"""Cross-module orchestration for the PostgreSQL-backed MVP core flow."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Optional, Protocol

from fastapi import HTTPException

from delivery_module import Plan as DeliveryPlan
from delivery_module import PlanItem as DeliveryPlanItem
from delivery_module import WebDeliveryService
from profile_module import Answer as ProfileAnswer
from profile_module import Profile, ProfileService, Question as ProfileQuestion
from recommendation_module import recommend_tasks
from scheduling_module import PlanDraft, PlanItem as ScheduleItem
from scheduling_module import Task as ScheduleTask
from scheduling_module import build_schedule
from task_repository import TaskRepository


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class GeneratePlanRequest:
    free_start: datetime
    free_end: datetime
    density: str = "balanced"


class ProfileRepository(Protocol):
    def save(self, profile: Profile) -> None: ...

    def get(self, session_id: str) -> Optional[Profile]: ...

    def next_version(self, session_id: str) -> int: ...


class PlanRepository(Protocol):
    def save(self, plan: PlanDraft) -> PlanDraft: ...

    def get(self, session_id: str) -> Optional[PlanDraft]: ...


class PostgreSQLProfileRepository:
    """Persist deterministic profile snapshots in PostgreSQL."""

    def __init__(self, database_url: str) -> None:
        if not database_url:
            raise ValueError("database_url 不能为空")
        self.database_url = database_url
        self.init_schema()

    def _connect(self):
        import psycopg

        return psycopg.connect(self.database_url)

    def init_schema(self) -> None:
        statement = """
        CREATE TABLE IF NOT EXISTS profiles (
            session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            profile_version INTEGER NOT NULL,
            scores JSONB NOT NULL,
            constraints JSONB NOT NULL,
            confidence DOUBLE PRECISION NOT NULL,
            rule_version TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (session_id, profile_version)
        )
        """
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement)

    def next_version(self, session_id: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(profile_version), 0) + 1 FROM profiles WHERE session_id = %s",
                (session_id,),
            ).fetchone()
        return int(row[0])

    def save(self, profile: Profile) -> None:
        from psycopg.types.json import Jsonb

        statement = """
        INSERT INTO profiles (
            session_id, profile_version, scores, constraints,
            confidence, rule_version, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (session_id, profile_version) DO UPDATE SET
            scores = EXCLUDED.scores,
            constraints = EXCLUDED.constraints,
            confidence = EXCLUDED.confidence,
            rule_version = EXCLUDED.rule_version
        """
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    statement,
                    (
                        profile.session_id,
                        profile.profile_version,
                        Jsonb(profile.scores),
                        Jsonb(profile.constraints),
                        profile.confidence,
                        profile.rule_version,
                        utc_now(),
                    ),
                )

    def get(self, session_id: str) -> Optional[Profile]:
        from psycopg.rows import dict_row

        query = """
        SELECT session_id, profile_version, scores, constraints,
               confidence, rule_version
        FROM profiles
        WHERE session_id = %s
        ORDER BY profile_version DESC
        LIMIT 1
        """
        with self._connect() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(query, (session_id,))
                row = cursor.fetchone()
        if row is None:
            return None
        return Profile(
            session_id=row["session_id"],
            profile_version=int(row["profile_version"]),
            scores=dict(row["scores"] or {}),
            constraints=dict(row["constraints"] or {}),
            confidence=float(row["confidence"]),
            rule_version=row["rule_version"],
        )


class PostgreSQLPlanRepository:
    """Persist plan headers and timeline items in PostgreSQL."""

    def __init__(self, database_url: str) -> None:
        if not database_url:
            raise ValueError("database_url 不能为空")
        self.database_url = database_url
        self.init_schema()

    def _connect(self):
        import psycopg

        return psycopg.connect(self.database_url)

    def init_schema(self) -> None:
        statements = (
            """
            CREATE TABLE IF NOT EXISTS plans (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                density TEXT NOT NULL,
                free_start TIMESTAMPTZ NOT NULL,
                free_end TIMESTAMPTZ NOT NULL,
                version INTEGER NOT NULL,
                parent_plan_id TEXT,
                unscheduled_task_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
                created_at TIMESTAMPTZ NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS plan_items (
                id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
                task_id TEXT,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                start_at TIMESTAMPTZ NOT NULL,
                end_at TIMESTAMPTZ NOT NULL,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                locked BOOLEAN NOT NULL DEFAULT FALSE
            )
            """,
        )
        with self._connect() as connection:
            with connection.cursor() as cursor:
                for statement in statements:
                    cursor.execute(statement)

    def save(self, plan: PlanDraft) -> PlanDraft:
        from psycopg.types.json import Jsonb

        plan_query = """
        INSERT INTO plans (
            id, session_id, density, free_start, free_end, version,
            parent_plan_id, unscheduled_task_ids, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            density = EXCLUDED.density,
            free_start = EXCLUDED.free_start,
            free_end = EXCLUDED.free_end,
            version = EXCLUDED.version,
            parent_plan_id = EXCLUDED.parent_plan_id,
            unscheduled_task_ids = EXCLUDED.unscheduled_task_ids
        """
        item_query = """
        INSERT INTO plan_items (
            id, plan_id, task_id, title, category, start_at, end_at,
            kind, status, locked
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            title = EXCLUDED.title,
            category = EXCLUDED.category,
            start_at = EXCLUDED.start_at,
            end_at = EXCLUDED.end_at,
            kind = EXCLUDED.kind,
            status = EXCLUDED.status,
            locked = EXCLUDED.locked
        """
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    plan_query,
                    (
                        plan.plan_id,
                        plan.session_id,
                        plan.density,
                        plan.free_start,
                        plan.free_end,
                        plan.version,
                        plan.parent_plan_id,
                        Jsonb(list(plan.unscheduled_task_ids)),
                        utc_now(),
                    ),
                )
                for item in plan.items:
                    cursor.execute(
                        item_query,
                        (
                            item.id,
                            plan.plan_id,
                            item.task_id,
                            item.title,
                            item.category,
                            item.start_at,
                            item.end_at,
                            item.kind,
                            item.status,
                            item.locked,
                        ),
                    )
        return plan

    def get(self, session_id: str) -> Optional[PlanDraft]:
        from psycopg.rows import dict_row

        plan_query = """
        SELECT id, session_id, density, free_start, free_end, version,
               parent_plan_id, unscheduled_task_ids
        FROM plans
        WHERE session_id = %s
        ORDER BY version DESC, created_at DESC
        LIMIT 1
        """
        with self._connect() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(plan_query, (session_id,))
                plan_row = cursor.fetchone()
                if plan_row is None:
                    return None
                cursor.execute(
                    """
                    SELECT id, task_id, title, category, start_at, end_at,
                           kind, status, locked
                    FROM plan_items
                    WHERE plan_id = %s
                    ORDER BY start_at, end_at, id
                    """,
                    (plan_row["id"],),
                )
                item_rows = cursor.fetchall()
        items = tuple(
            ScheduleItem(
                id=row["id"],
                task_id=row["task_id"],
                title=row["title"],
                category=row["category"],
                start_at=row["start_at"],
                end_at=row["end_at"],
                kind=row["kind"],
                status=row["status"],
                locked=bool(row["locked"]),
            )
            for row in item_rows
        )
        return PlanDraft(
            plan_id=plan_row["id"],
            session_id=plan_row["session_id"],
            density=plan_row["density"],
            free_start=plan_row["free_start"],
            free_end=plan_row["free_end"],
            items=items,
            unscheduled_task_ids=tuple(plan_row["unscheduled_task_ids"] or []),
            version=int(plan_row["version"]),
            parent_plan_id=plan_row["parent_plan_id"],
        )


class MVPOrchestrator:
    def __init__(self, sessions, questionnaire, tasks, profiles, plans, delivery):
        self.sessions = sessions
        self.questionnaire = questionnaire
        self.tasks = tasks
        self.profiles = profiles
        self.plans = plans
        self.delivery = delivery

    def generate_plan(
        self,
        session_id: str,
        request: GeneratePlanRequest,
    ) -> dict[str, Any]:
        session = self.sessions.require_active(session_id)
        questionnaire = self.questionnaire.repository.get_questionnaire(session_id)
        if questionnaire is None or not questionnaire.submitted:
            raise HTTPException(status_code=409, detail="问卷尚未提交")

        questions = [
            self.questionnaire.questions[question_id]
            for question_id in questionnaire.question_ids
        ]
        answers = self.questionnaire.repository.get_answers(session_id)
        profile_questions = [
            ProfileQuestion(
                id=question.id,
                dimension=question.dimension,
                reverse_scored=question.reverse_scored,
            )
            for question in questions
        ]
        profile_answers = [
            ProfileAnswer(
                question_id=answer.question_id,
                value=answer.value,
                skipped=answer.skipped,
            )
            for answer in answers
        ]
        constraints = self._normalize_preferences(session.preferences)
        profile = ProfileService(self.profiles).build(
            session_id=session_id,
            questions=profile_questions,
            answers=profile_answers,
            preferences=constraints,
        )
        profile_data = asdict(profile)

        selected_categories = list(session.preferences.get("categories", []))
        recommendation = self._recommend(profile_data, selected_categories)
        if recommendation["missing_categories"]:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "当前约束下无法覆盖全部选择分类",
                    "missing_categories": recommendation["missing_categories"],
                },
            )

        schedule_tasks = [
            ScheduleTask(
                id=task["id"],
                title=task["title"],
                category=task["category"],
                duration=task["duration"],
                score=float(profile.scores.get(task["category"], 0)),
            )
            for task in recommendation["tasks"]
        ]
        plan = build_schedule(
            session_id=session_id,
            tasks=schedule_tasks,
            free_start=request.free_start,
            free_end=request.free_end,
            density=request.density,
        )
        self.plans.save(plan)
        web_plan = self._to_delivery_plan(plan)
        delivery = self.delivery.deliver(session_id, web_plan)
        return {
            "profile": profile_data,
            "recommendation": recommendation,
            "plan": plan.to_dict(),
            "delivery": delivery.to_dict() if hasattr(delivery, "to_dict") else delivery,
        }

    def get_plan(self, session_id: str) -> Optional[dict[str, Any]]:
        self.sessions.require_active(session_id)
        plan = self.plans.get(session_id)
        return plan.to_dict() if plan is not None else None

    def _recommend(self, profile: dict[str, Any], categories: list[str]) -> dict[str, Any]:
        constraints = profile["constraints"]
        candidates = self.tasks.search_tasks(
            session_id=profile["session_id"],
            budget_limit=constraints["budget_limit"],
            max_duration=constraints["max_duration"],
            outing=constraints["outing"],
            company=constraints["company"],
            categories=categories,
            scenarios=constraints.get("scenarios"),
        )
        result = recommend_tasks(profile, categories, candidates, limit=10)
        result["candidate_count"] = len(candidates)
        result["constraints"] = constraints
        return result

    @staticmethod
    def _normalize_preferences(preferences: dict[str, Any]) -> dict[str, Any]:
        budget_values = {"low": 20, "medium": 40, "high": 80}
        duration_values = {"half": 270, "day": 480}
        budget = preferences.get("budget", "medium")
        duration = preferences.get("duration", "half")
        return {
            **preferences,
            "budget_limit": budget_values.get(budget, 40),
            "max_duration": duration_values.get(duration, 270),
            "outing": preferences.get("outing", "any"),
            "company": preferences.get("company", "both"),
            "scenarios": preferences.get("scenarios"),
        }

    @staticmethod
    def _to_delivery_plan(plan: PlanDraft) -> DeliveryPlan:
        return DeliveryPlan(
            id=plan.plan_id,
            session_id=plan.session_id,
            title="你的空闲时间安排",
            status="draft",
            version=plan.version,
            items=tuple(
                DeliveryPlanItem(
                    id=item.id,
                    title=item.title,
                    category=item.category,
                    start_at=item.start_at,
                    end_at=item.end_at,
                    status=item.status,
                )
                for item in plan.items
            ),
        )

