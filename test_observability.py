"""Persistence for anonymous user-testing telemetry.

This module deliberately owns only the observability tables introduced by
``002_user_testing_metrics.sql``. API callers can catch database exceptions to
make telemetry non-blocking, while validation errors remain explicit.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any
import unicodedata
import uuid

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


EVENT_TYPES = frozenset(
    {
        "session_created",
        "questionnaire_started",
        "questionnaire_completed",
        "recommendations_viewed",
        "task_started",
        "task_completed",
        "task_skipped",
        "task_replaced",
        "schedule_adjusted",
        "feedback_submitted",
        "flow_error",
    }
)
REASON_CODES = frozenset(
    {
        "not_interested",
        "low_energy",
        "not_enough_time",
        "over_budget",
        "location_inconvenient",
        "too_difficult",
        "not_matching_current_state",
        "other",
    }
)
_ANONYMOUS_ID = re.compile(r"student_\d{3,6}\Z")
_COHORT = re.compile(r"student_[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}\Z")
_MAX_COMMENT_LENGTH = 500


def _make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _is_safe_text(value: str, maximum: int) -> bool:
    return bool(value) and len(value) <= maximum and not any(
        unicodedata.category(character) == "Cc" for character in value
    )


def _contains_control_characters(value: str) -> bool:
    return any(unicodedata.category(character) == "Cc" for character in value)


class TestObservabilityService:
    """Validate and persist isolated, anonymous testing data."""

    def __init__(self, database_url: str) -> None:
        if not database_url:
            raise ValueError("database_url 不能为空")
        self.database_url = database_url

    def _connect(self):
        return psycopg.connect(self.database_url, row_factory=dict_row)

    @staticmethod
    def _validate_anonymous_id(anonymous_id: str) -> str:
        if (
            not isinstance(anonymous_id, str)
            or _contains_control_characters(anonymous_id)
            or not _ANONYMOUS_ID.fullmatch(anonymous_id)
        ):
            raise ValueError("anonymous_id 必须是匿名 student_ 编号")
        return anonymous_id

    @staticmethod
    def _validate_cohort(cohort: str) -> str:
        if (
            not isinstance(cohort, str)
            or _contains_control_characters(cohort)
            or not _COHORT.fullmatch(cohort)
        ):
            raise ValueError("cohort 必须是 student_ 测试批次编号")
        return cohort

    @staticmethod
    def _validate_optional_id(value: str | None, field: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or not _is_safe_text(value, 128):
            raise ValueError(f"{field} 必须是长度不超过 128 的安全文本")
        return value

    @staticmethod
    def _metadata(metadata: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(metadata, dict):
            raise ValueError("metadata 必须是对象")

        cleaned: dict[str, Any] = {}
        category = metadata.get("task_category")
        if category is not None:
            if not isinstance(category, str) or not _is_safe_text(category, 64):
                raise ValueError("task_category 必须是长度不超过 64 的安全文本")
            cleaned["task_category"] = category

        energy_level = metadata.get("energy_level")
        if energy_level is not None:
            if energy_level not in {"low", "medium", "high"}:
                raise ValueError("energy_level 必须是 low、medium 或 high")
            cleaned["energy_level"] = energy_level

        available_minutes = metadata.get("available_minutes")
        if available_minutes is not None:
            if (
                not isinstance(available_minutes, int)
                or isinstance(available_minutes, bool)
                or not 1 <= available_minutes <= 480
            ):
                raise ValueError("available_minutes 必须是 1 到 480 的整数")
            cleaned["available_minutes"] = available_minutes

        error_code = metadata.get("error_code")
        if error_code is not None:
            if not isinstance(error_code, str) or not _is_safe_text(error_code, 64):
                raise ValueError("error_code 必须是长度不超过 64 的安全文本")
            cleaned["error_code"] = error_code
        return cleaned

    @staticmethod
    def _event_payload(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "event_id": row["id"],
            "anonymous_id": row["anonymous_id"],
            "session_id": row["session_id"],
            "plan_id": row["plan_id"],
            "plan_item_id": row["plan_item_id"],
            "event_type": row["event_type"],
            "reason_code": row["reason_code"],
            "metadata": row["metadata_json"],
            "occurred_at": row["occurred_at"],
            "idempotency_key": row["idempotency_key"],
        }

    @staticmethod
    def _feedback_payload(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "feedback_id": row["id"],
            "anonymous_id": row["anonymous_id"],
            "session_id": row["session_id"],
            "plan_item_id": row["plan_item_id"],
            "rating": row["rating"],
            "comment": row["comment"],
            "created_at": row["created_at"],
        }

    @staticmethod
    def _update_last_seen(connection: Any, anonymous_id: str, occurred_at: datetime) -> None:
        connection.execute(
            "UPDATE test_users SET last_seen_at = %s WHERE anonymous_id = %s",
            (occurred_at, anonymous_id),
        )

    def identify(self, anonymous_id: str, cohort: str) -> dict[str, str]:
        anonymous_id = self._validate_anonymous_id(anonymous_id)
        cohort = self._validate_cohort(cohort)
        with self._connect() as connection:
            row = connection.execute(
                """
                INSERT INTO test_users (id, anonymous_id, cohort, last_seen_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (anonymous_id) DO UPDATE SET
                    last_seen_at = EXCLUDED.last_seen_at,
                    deleted_at = NULL
                RETURNING anonymous_id, cohort
                """,
                (_make_id("test_user"), anonymous_id, cohort, datetime.now(timezone.utc)),
            ).fetchone()
        if row is None:
            raise RuntimeError("匿名测试用户保存失败")
        return {"anonymous_id": row["anonymous_id"], "cohort": row["cohort"]}

    def record_event(
        self,
        *,
        anonymous_id: str,
        event_type: str,
        session_id: str | None,
        plan_id: str | None,
        plan_item_id: str | None,
        reason_code: str | None,
        metadata: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        anonymous_id = self._validate_anonymous_id(anonymous_id)
        if event_type not in EVENT_TYPES:
            raise ValueError("不支持的测试事件类型")
        if reason_code is not None and reason_code not in REASON_CODES:
            raise ValueError("不支持的原因代码")
        if reason_code is not None and event_type not in {"task_skipped", "task_replaced"}:
            raise ValueError("原因代码仅适用于跳过或替换任务事件")
        session_id = self._validate_optional_id(session_id, "session_id")
        plan_id = self._validate_optional_id(plan_id, "plan_id")
        plan_item_id = self._validate_optional_id(plan_item_id, "plan_item_id")
        if not isinstance(idempotency_key, str) or not _is_safe_text(idempotency_key, 128):
            raise ValueError("idempotency_key 必须是长度不超过 128 的安全文本")
        cleaned_metadata = self._metadata(metadata)
        occurred_at = datetime.now(timezone.utc)

        with self._connect() as connection:
            row = connection.execute(
                """
                INSERT INTO test_events (
                    id, anonymous_id, session_id, plan_id, plan_item_id, event_type,
                    reason_code, metadata_json, occurred_at, idempotency_key
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (anonymous_id, idempotency_key) DO UPDATE SET
                    id = test_events.id
                RETURNING id, anonymous_id, session_id, plan_id, plan_item_id,
                          event_type, reason_code, metadata_json, occurred_at,
                          idempotency_key
                """,
                (
                    _make_id("test_event"),
                    anonymous_id,
                    session_id,
                    plan_id,
                    plan_item_id,
                    event_type,
                    reason_code,
                    Jsonb(cleaned_metadata),
                    occurred_at,
                    idempotency_key,
                ),
            ).fetchone()
            self._update_last_seen(connection, anonymous_id, occurred_at)
        if row is None:
            raise RuntimeError("测试事件保存失败")
        return self._event_payload(row)

    def save_feedback(
        self,
        *,
        anonymous_id: str,
        session_id: str,
        plan_item_id: str,
        rating: int,
        comment: str | None,
    ) -> dict[str, Any]:
        anonymous_id = self._validate_anonymous_id(anonymous_id)
        session_id = self._validate_optional_id(session_id, "session_id")
        plan_item_id = self._validate_optional_id(plan_item_id, "plan_item_id")
        if not isinstance(rating, int) or isinstance(rating, bool) or not 1 <= rating <= 5:
            raise ValueError("评分必须是 1 到 5 的整数")
        if comment is not None and (
            not isinstance(comment, str) or not _is_safe_text(comment, _MAX_COMMENT_LENGTH)
        ):
            raise ValueError("comment 必须是长度不超过 500 的安全文本")
        now = datetime.now(timezone.utc)

        with self._connect() as connection:
            row = connection.execute(
                """
                INSERT INTO task_test_feedback (
                    id, anonymous_id, session_id, plan_item_id, rating, comment,
                    created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (plan_item_id) DO UPDATE SET
                    rating = EXCLUDED.rating,
                    comment = EXCLUDED.comment
                RETURNING id, anonymous_id, session_id, plan_item_id, rating,
                          comment, created_at
                """,
                (
                    _make_id("test_feedback"),
                    anonymous_id,
                    session_id,
                    plan_item_id,
                    rating,
                    comment,
                    now,
                ),
            ).fetchone()
            self._update_last_seen(connection, anonymous_id, now)
        if row is None:
            raise RuntimeError("测试评价保存失败")
        return self._feedback_payload(row)

    def delete_anonymous_data(self, anonymous_id: str) -> int:
        anonymous_id = self._validate_anonymous_id(anonymous_id)
        with self._connect() as connection:
            result = connection.execute(
                "DELETE FROM test_users WHERE anonymous_id = %s",
                (anonymous_id,),
            )
        return result.rowcount

    RETENTION_DAYS = 90

    def delete_expired_data(self, *, now: datetime | None = None) -> int:
        reference_time = now or datetime.now(timezone.utc)
        cutoff = reference_time - timedelta(days=self.RETENTION_DAYS)
        with self._connect() as connection:
            result = connection.execute(
                "DELETE FROM test_users WHERE last_seen_at < %s",
                (cutoff,),
            )
        return result.rowcount
