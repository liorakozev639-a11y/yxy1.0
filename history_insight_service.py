from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row


class HistoryInsightService:
    """Build user-facing history and preference-learning insight."""

    def __init__(self, database_url: str) -> None:
        if not database_url:
            raise ValueError("database_url 不能为空")
        self.database_url = database_url

    def _connect(self):
        return psycopg.connect(self.database_url)

    def insight(self, user_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            summary = self._summary(connection, user_id)
            completed_tasks = self._this_week_completed_tasks(connection, user_id)
            recent_plans = self._recent_plans(connection, user_id)
            favorite_categories = self._favorite_categories(connection, user_id)
            avoided_groups = self._avoided_groups(connection, user_id)

        has_history = any(
            summary[key] > 0
            for key in ("completed_count", "skipped_count", "replaced_count", "low_rating_count")
        )
        return {
            "user_id": user_id,
            "has_history": has_history,
            "empty_state": "完成或跳过几个任务后，这里会显示系统学到的偏好。",
            "summary": summary,
            "this_week_completed_tasks": completed_tasks,
            "recent_plans": recent_plans,
            "favorite_categories": favorite_categories,
            "avoided_groups": avoided_groups,
            "learning_notes": self._learning_notes(summary, favorite_categories, avoided_groups),
            "next_recommendation_strategy": self._next_strategy(summary, favorite_categories, avoided_groups),
        }

    @staticmethod
    def _week_start() -> datetime:
        now = datetime.now(timezone.utc)
        return (now - timedelta(days=now.weekday())).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

    def _summary(self, connection, user_id: str) -> dict[str, int]:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE h.action = 'completed') AS completed_count,
                    COUNT(*) FILTER (
                        WHERE h.action = 'completed' AND h.occurred_at >= %s
                    ) AS this_week_completed_count,
                    COUNT(*) FILTER (WHERE h.action = 'skipped') AS skipped_count,
                    COUNT(*) FILTER (WHERE h.action = 'replaced_from') AS replaced_count
                FROM user_task_history AS h
                WHERE h.user_id = %s
                """,
                (self._week_start(), user_id),
            )
            row = cursor.fetchone() or {}
        low_rating_count = self._low_rating_count(connection, user_id)
        return {
            "completed_count": int(row.get("completed_count") or 0),
            "this_week_completed_count": int(row.get("this_week_completed_count") or 0),
            "skipped_count": int(row.get("skipped_count") or 0),
            "replaced_count": int(row.get("replaced_count") or 0),
            "low_rating_count": low_rating_count,
        }

    @staticmethod
    def _low_rating_count(connection, user_id: str) -> int:
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.task_feedback')")
            if cursor.fetchone()[0] is None:
                return 0
            cursor.execute(
                """
                WITH user_plans AS (
                    SELECT DISTINCT plan_id
                    FROM user_task_history
                    WHERE user_id = %s
                )
                SELECT COUNT(*)
                FROM task_feedback AS f
                JOIN user_plans ON user_plans.plan_id = f.plan_id
                WHERE f.rating <= 2
                """,
                (user_id,),
            )
            return int(cursor.fetchone()[0] or 0)

    def _this_week_completed_tasks(self, connection, user_id: str) -> list[dict[str, Any]]:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT
                    COALESCE(i.title, h.task_id, '未知任务') AS title,
                    h.category,
                    h.feedback_group,
                    h.occurred_at AS completed_at
                FROM user_task_history AS h
                LEFT JOIN plan_items AS i ON i.id = h.item_id
                WHERE h.user_id = %s
                  AND h.action = 'completed'
                  AND h.occurred_at >= %s
                ORDER BY h.occurred_at DESC
                LIMIT 20
                """,
                (user_id, self._week_start()),
            )
            rows = cursor.fetchall()
        return [
            {
                "title": row["title"],
                "category": row["category"],
                "feedback_group": row["feedback_group"],
                "completed_at": row["completed_at"].isoformat(),
            }
            for row in rows
        ]

    @staticmethod
    def _recent_plans(connection, user_id: str) -> list[dict[str, Any]]:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT
                    p.id AS plan_id,
                    p.created_at,
                    COALESCE(p.status, 'draft') AS status,
                    COUNT(*) FILTER (WHERE h.action = 'completed') AS completed_count,
                    COUNT(*) FILTER (WHERE h.action = 'skipped') AS skipped_count,
                    COUNT(*) FILTER (WHERE h.action = 'replaced_from') AS replaced_count
                FROM plans AS p
                JOIN user_task_history AS h ON h.plan_id = p.id
                WHERE h.user_id = %s
                GROUP BY p.id, p.created_at, p.status
                ORDER BY p.created_at DESC
                LIMIT 5
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
        return [
            {
                "plan_id": row["plan_id"],
                "created_at": row["created_at"].isoformat(),
                "status": row["status"],
                "completed_count": int(row["completed_count"] or 0),
                "skipped_count": int(row["skipped_count"] or 0),
                "replaced_count": int(row["replaced_count"] or 0),
            }
            for row in rows
        ]

    @staticmethod
    def _favorite_categories(connection, user_id: str) -> list[dict[str, Any]]:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT category, COUNT(*) AS completed_count
                FROM user_task_history
                WHERE user_id = %s AND action = 'completed'
                GROUP BY category
                ORDER BY COUNT(*) DESC, category
                LIMIT 5
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
        return [
            {
                "category": row["category"],
                "completed_count": int(row["completed_count"] or 0),
            }
            for row in rows
        ]

    @staticmethod
    def _avoided_groups(connection, user_id: str) -> list[dict[str, Any]]:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT feedback_group, category, COUNT(*) AS negative_count
                FROM user_task_history
                WHERE user_id = %s AND action IN ('skipped', 'replaced_from')
                GROUP BY feedback_group, category
                ORDER BY COUNT(*) DESC, feedback_group
                LIMIT 8
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
        return [
            {
                "feedback_group": row["feedback_group"],
                "category": row["category"],
                "negative_count": int(row["negative_count"] or 0),
            }
            for row in rows
        ]

    @staticmethod
    def _learning_notes(
        summary: dict[str, int],
        favorite_categories: list[dict[str, Any]],
        avoided_groups: list[dict[str, Any]],
    ) -> list[str]:
        notes: list[str] = []
        if favorite_categories:
            category = favorite_categories[0]["category"]
            notes.append(f"你更常完成「{category}」类任务，系统会在同等条件下提高这类任务排序。")
        if avoided_groups:
            group = avoided_groups[0]
            notes.append(
                f"你多次跳过或替换「{group['category']}」中的 {group['feedback_group']} 类型，系统会降低类似任务出现频率。"
            )
        if summary["low_rating_count"]:
            notes.append("你给过 1-2 分的任务会被视为低满意度信号，后续推荐会更谨慎。")
        if not notes:
            notes.append("完成、跳过或反馈任务后，系统会逐步形成你的偏好学习记录。")
        return notes

    @staticmethod
    def _next_strategy(
        summary: dict[str, int],
        favorite_categories: list[dict[str, Any]],
        avoided_groups: list[dict[str, Any]],
    ) -> list[str]:
        strategy = ["继续避开当前会话和历史中反复跳过或替换的细任务组。"]
        if favorite_categories:
            strategy.append(f"优先保留你更常完成的「{favorite_categories[0]['category']}」方向。")
        if summary["replaced_count"]:
            strategy.append("对你主动更换过的任务，会降低相似任务的排序。")
        if summary["low_rating_count"]:
            strategy.append("对低分任务对应的偏好类型，会减少直接推荐。")
        if not avoided_groups and not summary["low_rating_count"]:
            strategy.append("随着反馈增加，系统会把不适合你的任务逐步排到后面。")
        return strategy
