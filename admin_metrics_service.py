"""Single-admin authentication and read-only testing-metrics aggregation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import base64
import hashlib
import hmac
import os
import re
import secrets
from typing import Any
import unicodedata
import uuid

import psycopg
from psycopg.rows import dict_row


_ANONYMOUS_ID = re.compile(r"student_\d{3,6}\Z")
_FUNNEL_EVENTS = (
    "session_created",
    "questionnaire_completed",
    "recommendations_viewed",
    "task_started",
    "task_completed",
    "feedback_submitted",
)


@dataclass(frozen=True)
class MetricsFilters:
    """Dashboard filters with values normalized before they reach SQL."""

    from_date: date | None = None
    to_date: date | None = None
    cohort: str | None = None
    anonymous_id: str | None = None
    task_category: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("from_date", "to_date"):
            value = getattr(self, field_name)
            if value is not None and (not isinstance(value, date) or isinstance(value, datetime)):
                raise ValueError(f"{field_name} 必须是日期")
        if self.from_date and self.to_date and self.from_date > self.to_date:
            raise ValueError("from_date 不能晚于 to_date")
        if self.cohort is not None:
            self._safe_filter(self.cohort, "cohort")
        if self.anonymous_id is not None and not _ANONYMOUS_ID.fullmatch(self.anonymous_id):
            raise ValueError("anonymous_id 必须是匿名 student_ 编号")
        if self.task_category is not None:
            self._safe_filter(self.task_category, "task_category")

    @staticmethod
    def _safe_filter(value: str, field_name: str) -> None:
        if (
            not isinstance(value, str)
            or not value
            or len(value) > 64
            or any(unicodedata.category(character) == "Cc" for character in value)
        ):
            raise ValueError(f"{field_name} 必须是长度不超过 64 的安全文本")


class AdminMetricsService:
    """Authenticate one configured administrator and expose aggregate-only data."""

    SESSION_TTL = timedelta(hours=1)
    LOCKOUT_TTL = timedelta(minutes=15)
    MAX_FAILED_LOGINS = 5

    def __init__(self, database_url: str) -> None:
        if not database_url:
            raise ValueError("database_url 不能为空")
        self.database_url = database_url
        self.username = os.environ.get("ADMIN_METRICS_USERNAME", "")
        self.password = os.environ.get("ADMIN_METRICS_PASSWORD", "")
        if not self.username or not self.password:
            raise ValueError("ADMIN_METRICS_USERNAME 和 ADMIN_METRICS_PASSWORD 必须配置")

    def _connect(self):
        return psycopg.connect(self.database_url, row_factory=dict_row)

    @staticmethod
    def _make_id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex}"

    @staticmethod
    def _password_hash(password: str, salt: bytes | None = None) -> str:
        salt = salt or secrets.token_bytes(16)
        digest = hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32
        )
        return "scrypt${}${}".format(
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        )

    @staticmethod
    def _password_matches(password: str, stored_hash: str) -> bool:
        if not isinstance(password, str) or not isinstance(stored_hash, str):
            return False
        try:
            algorithm, encoded_salt, encoded_digest = stored_hash.split("$", 2)
            if algorithm != "scrypt":
                return False
            salt = base64.urlsafe_b64decode(encoded_salt.encode("ascii"))
            expected = base64.urlsafe_b64decode(encoded_digest.encode("ascii"))
            actual = hashlib.scrypt(
                password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=len(expected)
            )
        except (ValueError, UnicodeError):
            return False
        return hmac.compare_digest(actual, expected)

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _constant_time_text_matches(value: object, expected: object) -> bool:
        if not isinstance(value, str) or not isinstance(expected, str):
            return False
        try:
            return hmac.compare_digest(value.encode("utf-8"), expected.encode("utf-8"))
        except UnicodeError:
            return False

    def _ensure_admin(self, connection: Any) -> dict[str, Any]:
        connection.execute("SELECT pg_advisory_xact_lock(9172468021468024)")
        existing_admin = connection.execute(
            """
            SELECT id, username, password_hash, role, failed_login_count, locked_until
            FROM admin_users
            WHERE role = 'admin'
            LIMIT 1
            """
        ).fetchone()
        if existing_admin is not None:
            if not self._constant_time_text_matches(existing_admin["username"], self.username):
                raise RuntimeError("单一管理员账号已初始化，拒绝创建第二个管理员")
            return existing_admin

        connection.execute(
            """
            INSERT INTO admin_users (id, username, password_hash, role)
            VALUES (%s, %s, %s, 'admin')
            ON CONFLICT (username) DO NOTHING
            """,
            (self._make_id("admin"), self.username, self._password_hash(self.password)),
        )
        row = connection.execute(
            """
            SELECT id, username, password_hash, role, failed_login_count, locked_until
            FROM admin_users
            WHERE role = 'admin'
            LIMIT 1
            """,
        ).fetchone()
        if row is None or not self._constant_time_text_matches(row["username"], self.username):
            raise RuntimeError("管理员账号初始化失败")
        return row

    def login(self, username: str, password: str) -> dict[str, Any]:
        """Issue a short-lived opaque token, or return the same failure for all errors."""
        now = datetime.now(timezone.utc)
        login_failed = False
        token = ""
        expires_at = now

        with self._connect() as connection:
            admin = self._ensure_admin(connection)
            locked_until = admin.get("locked_until")
            if locked_until and now < locked_until:
                login_failed = True
            elif locked_until:
                connection.execute(
                    """
                    UPDATE admin_users SET failed_login_count = 0, locked_until = NULL, updated_at = %s
                    WHERE id = %s
                    """,
                    (now, admin["id"]),
                )

            if not login_failed:
                username_matches = self._constant_time_text_matches(username, self.username)
                password_matches = self._password_matches(password, admin["password_hash"])
                if not username_matches or not password_matches:
                    connection.execute(
                        """
                        UPDATE admin_users SET failed_login_count = failed_login_count + 1,
                            locked_until = CASE WHEN failed_login_count + 1 >= %s THEN %s ELSE locked_until END,
                            updated_at = %s
                        WHERE id = %s
                        RETURNING failed_login_count, locked_until
                        """,
                        (self.MAX_FAILED_LOGINS, now + self.LOCKOUT_TTL, now, admin["id"]),
                    ).fetchone()
                    login_failed = True
                else:
                    connection.execute(
                        """
                        UPDATE admin_users SET failed_login_count = 0, locked_until = NULL, updated_at = %s
                        WHERE id = %s
                        """,
                        (now, admin["id"]),
                    )
                    token = secrets.token_urlsafe(32)
                    expires_at = now + self.SESSION_TTL
                    connection.execute(
                        """
                        INSERT INTO admin_sessions (id, admin_user_id, token_hash, expires_at)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (self._make_id("admin_session"), admin["id"], self._token_hash(token), expires_at),
                    )

        if login_failed:
            raise PermissionError("登录失败")
        return {"token": token, "expires_at": expires_at}

    def authenticate(self, token: str) -> dict[str, Any]:
        if not isinstance(token, str) or not token:
            raise PermissionError("未认证")
        now = datetime.now(timezone.utc)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT admin_users.id, admin_users.username, admin_users.role
                FROM admin_sessions
                JOIN admin_users ON admin_users.id = admin_sessions.admin_user_id
                WHERE admin_sessions.token_hash = %s
                  AND admin_sessions.expires_at > %s
                  AND admin_sessions.revoked_at IS NULL
                  AND admin_users.role = 'admin'
                """,
                (self._token_hash(token), now),
            ).fetchone()
        if row is None:
            raise PermissionError("未认证")
        return {"id": row["id"], "username": row["username"], "role": row["role"]}

    def logout(self, token: str) -> None:
        if not isinstance(token, str) or not token:
            return
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE admin_sessions SET revoked_at = %s
                WHERE token_hash = %s AND revoked_at IS NULL
                """,
                (datetime.now(timezone.utc), self._token_hash(token)),
            )

    @staticmethod
    def _event_scope(filters: MetricsFilters) -> tuple[list[str], list[object]]:
        clauses: list[str] = []
        params: list[object] = []
        if filters.from_date:
            clauses.append("e.occurred_at >= %s")
            params.append(datetime.combine(filters.from_date, time.min, tzinfo=timezone.utc))
        if filters.to_date:
            clauses.append("e.occurred_at < %s")
            params.append(datetime.combine(filters.to_date + timedelta(days=1), time.min, tzinfo=timezone.utc))
        if filters.cohort:
            clauses.append("u.cohort = %s")
            params.append(filters.cohort)
        if filters.anonymous_id:
            clauses.append("e.anonymous_id = %s")
            params.append(filters.anonymous_id)
        if filters.task_category:
            clauses.append("e.metadata_json ->> 'task_category' = %s")
            params.append(filters.task_category)
        return clauses, params

    @classmethod
    def _event_where(cls, filters: MetricsFilters) -> tuple[str, tuple[object, ...]]:
        clauses, params = cls._event_scope(filters)
        return (" WHERE " + " AND ".join(clauses) if clauses else "", tuple(params))

    @staticmethod
    def _feedback_where(filters: MetricsFilters) -> tuple[str, tuple[object, ...]]:
        clauses: list[str] = []
        params: list[object] = []
        if filters.from_date:
            clauses.append("f.created_at >= %s")
            params.append(datetime.combine(filters.from_date, time.min, tzinfo=timezone.utc))
        if filters.to_date:
            clauses.append("f.created_at < %s")
            params.append(
                datetime.combine(filters.to_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
            )
        if filters.cohort:
            clauses.append("u.cohort = %s")
            params.append(filters.cohort)
        if filters.anonymous_id:
            clauses.append("f.anonymous_id = %s")
            params.append(filters.anonymous_id)
        return (" WHERE " + " AND ".join(clauses) if clauses else "", tuple(params))

    @staticmethod
    def _rate(numerator: object, denominator: object) -> float:
        if not denominator:
            return 0.0
        return round(float(numerator or 0) * 100 / float(denominator), 2)

    def summary(self, filters: MetricsFilters) -> dict[str, Any]:
        where, params = self._event_where(filters)
        feedback_where, feedback_params = self._feedback_where(filters)
        feedback_category_where = ""
        feedback_category_params: tuple[object, ...] = ()
        if filters.task_category:
            feedback_category_where = "WHERE category_by_plan_item.task_category = %s"
            feedback_category_params = (filters.task_category,)
        statement = f"""
            /* admin_metrics:summary */
            WITH category_by_plan_item AS (
                SELECT DISTINCT ON (e.plan_item_id)
                    e.plan_item_id,
                    e.metadata_json ->> 'task_category' AS task_category
                FROM test_events e
                WHERE e.plan_item_id IS NOT NULL
                  AND e.metadata_json ? 'task_category'
                ORDER BY e.plan_item_id, e.occurred_at DESC, e.id DESC
            ), feedback_records AS (
                SELECT DISTINCT f.plan_item_id, f.rating
                FROM task_test_feedback f
                JOIN test_users u ON u.anonymous_id = f.anonymous_id
                {feedback_where}
            ), scoped_feedback AS (
                SELECT f.plan_item_id, f.rating
                FROM feedback_records f
                {'JOIN category_by_plan_item ON category_by_plan_item.plan_item_id = f.plan_item_id' if filters.task_category else ''}
                {feedback_category_where}
            ), scoped_events AS (
                SELECT e.anonymous_id, e.session_id, e.plan_item_id, e.event_type
                FROM test_events e
                JOIN test_users u ON u.anonymous_id = e.anonymous_id
                {where}
            ), created_sessions AS (
                SELECT DISTINCT e.session_id
                FROM scoped_events e
                WHERE e.event_type = 'session_created' AND e.session_id IS NOT NULL
            ), completed_sessions AS (
                SELECT DISTINCT e.session_id
                FROM scoped_events e
                JOIN created_sessions ON created_sessions.session_id = e.session_id
                WHERE e.event_type = 'feedback_submitted' AND e.session_id IS NOT NULL
            ), event_totals AS (
                SELECT
                    COUNT(DISTINCT e.anonymous_id) AS user_count,
                    COUNT(*) FILTER (WHERE e.event_type = 'task_replaced') AS replacement_count,
                    COUNT(*) FILTER (WHERE e.event_type = 'task_skipped') AS skip_count,
                    COUNT(*) FILTER (WHERE e.event_type = 'recommendations_viewed') AS recommendation_count
                FROM scoped_events e
            ), feedback_totals AS (
                SELECT
                    AVG(f.rating) AS average_rating
                FROM scoped_feedback f
            )
            SELECT
                e.user_count,
                (SELECT COUNT(*) FROM created_sessions) AS session_count,
                (SELECT COUNT(*) FROM completed_sessions) AS completed_sessions,
                f.average_rating,
                e.replacement_count, e.skip_count, e.recommendation_count
            FROM event_totals e
            CROSS JOIN feedback_totals f
        """
        with self._connect() as connection:
            row = connection.execute(
                statement, feedback_params + feedback_category_params + params
            ).fetchone() or {}
        sessions = row.get("session_count", 0)
        recommendations = row.get("recommendation_count", 0)
        return {
            "user_count": int(row.get("user_count") or 0),
            "session_count": int(sessions or 0),
            "full_flow_success_rate": min(
                100.0, self._rate(row.get("completed_sessions"), sessions)
            ),
            "average_rating": round(float(row.get("average_rating") or 0), 2),
            "replacement_rate": self._rate(row.get("replacement_count"), recommendations),
            "skip_rate": self._rate(row.get("skip_count"), recommendations),
        }

    def funnel(self, filters: MetricsFilters) -> dict[str, Any]:
        where, params = self._event_where(filters)
        statement = f"""
            /* admin_metrics:funnel */
            SELECT e.event_type, COUNT(*) AS count
            FROM test_events e
            JOIN test_users u ON u.anonymous_id = e.anonymous_id
            {where}
              {'AND' if where else 'WHERE'} e.event_type = ANY(%s)
            GROUP BY e.event_type
        """
        with self._connect() as connection:
            rows = connection.execute(statement, params + (list(_FUNNEL_EVENTS),)).fetchall()
        counts = {row["event_type"]: int(row["count"]) for row in rows}
        return {
            "steps": [
                {"event_type": event_type, "count": counts.get(event_type, 0)}
                for event_type in _FUNNEL_EVENTS
            ]
        }

    def recommendations(self, filters: MetricsFilters) -> list[dict[str, Any]]:
        where, params = self._event_where(filters)
        feedback_where, feedback_params = self._feedback_where(filters)
        feedback_category_where = ""
        feedback_category_params: tuple[object, ...] = ()
        if filters.task_category:
            feedback_category_where = "WHERE category_by_plan_item.task_category = %s"
            feedback_category_params = (filters.task_category,)
        statement = f"""
            /* admin_metrics:recommendations */
            WITH category_by_plan_item AS (
                SELECT DISTINCT ON (e.plan_item_id)
                    e.plan_item_id,
                    e.metadata_json ->> 'task_category' AS task_category
                FROM test_events e
                WHERE e.plan_item_id IS NOT NULL
                  AND e.metadata_json ? 'task_category'
                ORDER BY e.plan_item_id, e.occurred_at DESC, e.id DESC
            ), feedback_records AS (
                SELECT DISTINCT f.plan_item_id, f.rating
                FROM task_test_feedback f
                JOIN test_users u ON u.anonymous_id = f.anonymous_id
                {feedback_where}
            ), scoped_feedback AS (
                SELECT
                    f.plan_item_id,
                    f.rating,
                    COALESCE(category_by_plan_item.task_category, 'unknown') AS task_category
                FROM feedback_records f
                LEFT JOIN category_by_plan_item
                    ON category_by_plan_item.plan_item_id = f.plan_item_id
                {feedback_category_where}
            ), scoped_events AS (
                SELECT e.plan_item_id, e.event_type, e.metadata_json ->> 'task_category' AS task_category
                FROM test_events e
                JOIN test_users u ON u.anonymous_id = e.anonymous_id
                {where}
                  {'AND' if where else 'WHERE'} e.metadata_json ? 'task_category'
            ), category_events AS (
                SELECT
                    task_category,
                    COUNT(*) FILTER (WHERE event_type = 'recommendations_viewed') AS recommendation_count,
                    COUNT(*) FILTER (WHERE event_type = 'task_replaced') AS replacement_count,
                    COUNT(*) FILTER (WHERE event_type = 'task_skipped') AS skip_count
                FROM scoped_events
                GROUP BY task_category
            ), feedback_by_category AS (
                SELECT task_category, AVG(rating) AS average_rating
                FROM scoped_feedback
                GROUP BY task_category
            ), categories AS (
                SELECT task_category FROM category_events
                UNION
                SELECT task_category FROM feedback_by_category
            )
            SELECT
                categories.task_category,
                COALESCE(category_events.recommendation_count, 0) AS recommendation_count,
                feedback_by_category.average_rating,
                COALESCE(category_events.replacement_count, 0) AS replacement_count,
                COALESCE(category_events.skip_count, 0) AS skip_count
            FROM categories
            LEFT JOIN category_events ON category_events.task_category = categories.task_category
            LEFT JOIN feedback_by_category ON feedback_by_category.task_category = categories.task_category
            ORDER BY categories.task_category ASC
        """
        with self._connect() as connection:
            rows = connection.execute(
                statement, feedback_params + feedback_category_params + params
            ).fetchall()
        return [
            {
                "task_category": row["task_category"],
                "recommendation_count": int(row["recommendation_count"] or 0),
                "average_rating": round(float(row["average_rating"] or 0), 2),
                "replacement_rate": self._rate(row["replacement_count"], row["recommendation_count"]),
                "skip_rate": self._rate(row["skip_count"], row["recommendation_count"]),
            }
            for row in rows
        ]

    def energy_recommendations(self, filters: MetricsFilters) -> list[dict[str, Any]]:
        """Relate the reported energy level to recommended categories and outcomes."""
        where, params = self._event_where(filters)
        feedback_where, feedback_params = self._feedback_where(filters)
        statement = f"""
            /* admin_metrics:energy_recommendations */
            WITH scoped_events AS (
                SELECT
                    e.plan_item_id,
                    e.event_type,
                    e.metadata_json ->> 'energy_level' AS energy_level,
                    e.metadata_json ->> 'task_category' AS task_category
                FROM test_events e
                JOIN test_users u ON u.anonymous_id = e.anonymous_id
                {where}
            ), feedback_records AS (
                SELECT DISTINCT ON (f.plan_item_id) f.plan_item_id, f.rating
                FROM task_test_feedback f
                JOIN test_users u ON u.anonymous_id = f.anonymous_id
                {feedback_where}
                ORDER BY f.plan_item_id, f.created_at DESC, f.id DESC
            )
            SELECT
                COALESCE(e.energy_level, 'unknown') AS energy_level,
                COALESCE(e.task_category, 'unknown') AS task_category,
                COUNT(*) FILTER (WHERE e.event_type = 'recommendations_viewed') AS recommendation_count,
                AVG(f.rating) FILTER (WHERE e.event_type = 'recommendations_viewed') AS average_rating,
                COUNT(*) FILTER (WHERE e.event_type = 'task_replaced') AS replacement_count,
                COUNT(*) FILTER (WHERE e.event_type = 'task_skipped') AS skip_count
            FROM scoped_events e
            LEFT JOIN feedback_records f ON f.plan_item_id = e.plan_item_id
            WHERE e.energy_level IS NOT NULL
            GROUP BY e.energy_level, e.task_category
            ORDER BY e.energy_level ASC, e.task_category ASC
        """
        with self._connect() as connection:
            rows = connection.execute(statement, params + feedback_params).fetchall()
        return [
            {
                "energy_level": row["energy_level"],
                "task_category": row["task_category"],
                "recommendation_count": int(row["recommendation_count"] or 0),
                "average_rating": round(float(row["average_rating"] or 0), 2),
                "replacement_rate": self._rate(row["replacement_count"], row["recommendation_count"]),
                "skip_rate": self._rate(row["skip_count"], row["recommendation_count"]),
            }
            for row in rows
        ]

    def reasons(self, filters: MetricsFilters) -> list[dict[str, Any]]:
        where, params = self._event_where(filters)
        statement = f"""
            /* admin_metrics:reasons */
            SELECT e.reason_code, COUNT(*) AS count
            FROM test_events e
            JOIN test_users u ON u.anonymous_id = e.anonymous_id
            {where}
              {'AND' if where else 'WHERE'} e.reason_code IS NOT NULL
            GROUP BY e.reason_code
            ORDER BY count DESC, e.reason_code ASC
        """
        with self._connect() as connection:
            rows = connection.execute(statement, params).fetchall()
        return [{"reason_code": row["reason_code"], "count": int(row["count"])} for row in rows]

    def reason_details(self, filters: MetricsFilters) -> list[dict[str, Any]]:
        """Return bounded anonymous explanations, without personal identity fields."""
        where, params = self._event_where(filters)
        statement = f"""
            /* admin_metrics:reason_details */
            SELECT
                e.anonymous_id,
                e.reason_code,
                LEFT(e.metadata_json ->> 'reason_detail', 500) AS detail,
                e.occurred_at
            FROM test_events e
            JOIN test_users u ON u.anonymous_id = e.anonymous_id
            {where}
              {'AND' if where else 'WHERE'} e.reason_code IS NOT NULL
              AND NULLIF(BTRIM(e.metadata_json ->> 'reason_detail'), '') IS NOT NULL
            ORDER BY occurred_at DESC
            LIMIT 100
        """
        with self._connect() as connection:
            rows = connection.execute(statement, params).fetchall()
        return [
            {
                "anonymous_id": row["anonymous_id"],
                "reason_code": row["reason_code"],
                "detail": str(row["detail"] or "")[:500],
                "occurred_at": row["occurred_at"],
            }
            for row in rows
        ]

    def errors(self, filters: MetricsFilters) -> list[dict[str, Any]]:
        where, params = self._event_where(filters)
        statement = f"""
            /* admin_metrics:errors */
            SELECT e.metadata_json ->> 'error_code' AS error_code, COUNT(*) AS count
            FROM test_events e
            JOIN test_users u ON u.anonymous_id = e.anonymous_id
            {where}
              {'AND' if where else 'WHERE'} e.event_type = 'flow_error'
            GROUP BY e.metadata_json ->> 'error_code'
            ORDER BY count DESC, error_code ASC
            LIMIT 100
        """
        with self._connect() as connection:
            rows = connection.execute(statement, params).fetchall()
        return [{"error_code": row["error_code"] or "unknown", "count": int(row["count"])} for row in rows]

    def user_detail(self, filters: MetricsFilters) -> list[dict[str, Any]]:
        """Return anonymous per-user behavior totals for an optional anonymous_id filter."""
        where, params = self._event_where(filters)
        feedback_where, feedback_params = self._feedback_where(filters)
        user_clauses: list[str] = []
        user_params: list[object] = []
        if filters.cohort:
            user_clauses.append("u.cohort = %s")
            user_params.append(filters.cohort)
        if filters.anonymous_id:
            user_clauses.append("u.anonymous_id = %s")
            user_params.append(filters.anonymous_id)
        if filters.from_date or filters.to_date or filters.task_category:
            user_clauses.append(
                "(EXISTS (SELECT 1 FROM scoped_events scoped_user_event "
                "WHERE scoped_user_event.anonymous_id = u.anonymous_id) "
                "OR EXISTS (SELECT 1 FROM scoped_feedback scoped_user_feedback "
                "WHERE scoped_user_feedback.anonymous_id = u.anonymous_id))"
            )
        user_where = " WHERE " + " AND ".join(user_clauses) if user_clauses else ""
        statement = f"""
            /* admin_metrics:user_detail */
            WITH scoped_events AS (
                SELECT e.anonymous_id, e.session_id, e.event_type
                FROM test_events e
                JOIN test_users u ON u.anonymous_id = e.anonymous_id
                {where}
            ), scoped_feedback AS (
                SELECT f.anonymous_id, f.rating
                FROM task_test_feedback f
                JOIN test_users u ON u.anonymous_id = f.anonymous_id
                {feedback_where}
            )
            SELECT
                u.anonymous_id,
                u.cohort,
                COUNT(e.anonymous_id) AS event_count,
                COUNT(DISTINCT e.session_id) AS session_count,
                COUNT(*) FILTER (WHERE e.event_type = 'task_completed') AS completed_count,
                COUNT(*) FILTER (WHERE e.event_type = 'task_skipped') AS skipped_count,
                COUNT(*) FILTER (WHERE e.event_type = 'task_replaced') AS replaced_count,
                (SELECT AVG(f.rating) FROM scoped_feedback f WHERE f.anonymous_id = u.anonymous_id) AS average_rating
            FROM test_users u
            LEFT JOIN scoped_events e ON e.anonymous_id = u.anonymous_id
            {user_where}
            GROUP BY u.anonymous_id, u.cohort
            ORDER BY u.anonymous_id ASC
        """
        with self._connect() as connection:
            rows = connection.execute(statement, params + feedback_params + tuple(user_params)).fetchall()
        return [
            {
                "anonymous_id": row["anonymous_id"],
                "cohort": row["cohort"],
                "event_count": int(row["event_count"] or 0),
                "session_count": int(row["session_count"] or 0),
                "completed_count": int(row["completed_count"] or 0),
                "skipped_count": int(row["skipped_count"] or 0),
                "replaced_count": int(row["replaced_count"] or 0),
                "average_rating": round(float(row["average_rating"] or 0), 2),
            }
            for row in rows
        ]
