"""Questionnaire domain service backed exclusively by PostgreSQL."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Optional, Protocol

from fastapi import HTTPException

from session_module import SessionService


SCALE = [
    {"value": 1, "label": "完全不同意"},
    {"value": 2, "label": "不太同意"},
    {"value": 3, "label": "比较同意"},
    {"value": 4, "label": "非常同意"},
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Question:
    id: str
    mode: Literal["quick", "deep"]
    category: str
    dimension: str
    prompt: str
    reverse_scored: bool = False
    eligible_outing: Optional[str] = None
    eligible_company: Optional[str] = None
    status: str = "approved"


@dataclass
class Answer:
    session_id: str
    question_id: str
    value: Optional[int]
    skipped: bool
    answered_at: datetime


@dataclass
class QuestionnaireSession:
    session_id: str
    mode: Literal["quick", "deep"]
    question_ids: list[str]
    submitted: bool = False
    started_at: datetime = field(default_factory=utc_now)
    submitted_at: Optional[datetime] = None


@dataclass
class SubmissionSnapshot:
    questionnaire: QuestionnaireSession
    answers: list[Answer]
    missing_question_ids: list[str]


class QuestionnaireRepository(Protocol):
    def save_questionnaire(self, item: QuestionnaireSession) -> None: ...

    def get_questionnaire(
        self,
        session_id: str,
    ) -> Optional[QuestionnaireSession]: ...

    def save_answer_if_active(self, answer: Answer) -> bool: ...

    def get_answers(self, session_id: str) -> list[Answer]: ...

    def clear_answers(self, session_id: str) -> None: ...

    def delete_questionnaire(self, session_id: str) -> None: ...

    def submit_if_complete(
        self,
        session_id: str,
        submitted_at: datetime,
    ) -> Optional[SubmissionSnapshot]: ...


class PostgresQuestionnaireRepository:
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
        questionnaire_schema = """
        CREATE TABLE IF NOT EXISTS questionnaires (
            session_id TEXT PRIMARY KEY
                REFERENCES sessions(id) ON DELETE CASCADE,
            mode TEXT NOT NULL CHECK (mode IN ('quick', 'deep')),
            question_ids JSONB NOT NULL,
            submitted BOOLEAN NOT NULL DEFAULT FALSE,
            started_at TIMESTAMPTZ NOT NULL,
            submitted_at TIMESTAMPTZ
        )
        """
        answer_schema = """
        CREATE TABLE IF NOT EXISTS questionnaire_answers (
            session_id TEXT NOT NULL
                REFERENCES sessions(id) ON DELETE CASCADE,
            question_id TEXT NOT NULL,
            value INTEGER CHECK (value BETWEEN 1 AND 4),
            skipped BOOLEAN NOT NULL DEFAULT FALSE,
            answered_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (session_id, question_id),
            CHECK (
                (skipped = TRUE AND value IS NULL)
                OR (skipped = FALSE AND value IS NOT NULL)
            )
        )
        """
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(questionnaire_schema)
                cursor.execute(answer_schema)

    def save_questionnaire(self, item: QuestionnaireSession) -> None:
        from psycopg.types.json import Jsonb

        statement = """
        INSERT INTO questionnaires (
            session_id, mode, question_ids, submitted, started_at, submitted_at
        ) VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (session_id) DO UPDATE SET
            mode = EXCLUDED.mode,
            question_ids = EXCLUDED.question_ids,
            submitted = EXCLUDED.submitted,
            started_at = EXCLUDED.started_at,
            submitted_at = EXCLUDED.submitted_at
        """
        values = (
            item.session_id,
            item.mode,
            Jsonb(item.question_ids),
            item.submitted,
            item.started_at,
            item.submitted_at,
        )
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, values)

    def get_questionnaire(
        self,
        session_id: str,
    ) -> Optional[QuestionnaireSession]:
        from psycopg.rows import dict_row

        statement = """
        SELECT session_id, mode, question_ids, submitted,
               started_at, submitted_at
        FROM questionnaires
        WHERE session_id = %s
        """
        with self._connect() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(statement, (session_id,))
                row = cursor.fetchone()
        if row is None:
            return None
        return QuestionnaireSession(
            session_id=row["session_id"],
            mode=row["mode"],
            question_ids=list(row["question_ids"]),
            submitted=bool(row["submitted"]),
            started_at=row["started_at"],
            submitted_at=row["submitted_at"],
        )

    def save_answer_if_active(self, answer: Answer) -> bool:
        statement = """
        INSERT INTO questionnaire_answers (
            session_id, question_id, value, skipped, answered_at
        ) VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (session_id, question_id) DO UPDATE SET
            value = EXCLUDED.value,
            skipped = EXCLUDED.skipped,
            answered_at = EXCLUDED.answered_at
        """
        values = (
            answer.session_id,
            answer.question_id,
            answer.value,
            answer.skipped,
            answer.answered_at,
        )
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT submitted
                    FROM questionnaires
                    WHERE session_id = %s
                    FOR UPDATE
                    """,
                    (answer.session_id,),
                )
                row = cursor.fetchone()
                if row is None or bool(row[0]):
                    return False
                cursor.execute(statement, values)
        return True

    def get_answers(self, session_id: str) -> list[Answer]:
        from psycopg.rows import dict_row

        statement = """
        SELECT session_id, question_id, value, skipped, answered_at
        FROM questionnaire_answers
        WHERE session_id = %s
        ORDER BY answered_at, question_id
        """
        with self._connect() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(statement, (session_id,))
                rows = cursor.fetchall()
        return [
            Answer(
                session_id=row["session_id"],
                question_id=row["question_id"],
                value=row["value"],
                skipped=bool(row["skipped"]),
                answered_at=row["answered_at"],
            )
            for row in rows
        ]

    def clear_answers(self, session_id: str) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM questionnaire_answers WHERE session_id = %s",
                    (session_id,),
                )

    def delete_questionnaire(self, session_id: str) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM questionnaires WHERE session_id = %s",
                    (session_id,),
                )

    def submit_if_complete(
        self,
        session_id: str,
        submitted_at: datetime,
    ) -> Optional[SubmissionSnapshot]:
        from psycopg.rows import dict_row

        with self._connect() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT session_id, mode, question_ids, submitted,
                           started_at, submitted_at
                    FROM questionnaires
                    WHERE session_id = %s
                    FOR UPDATE
                    """,
                    (session_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                questionnaire = QuestionnaireSession(
                    session_id=row["session_id"],
                    mode=row["mode"],
                    question_ids=list(row["question_ids"]),
                    submitted=bool(row["submitted"]),
                    started_at=row["started_at"],
                    submitted_at=row["submitted_at"],
                )
                cursor.execute(
                    """
                    SELECT session_id, question_id, value, skipped, answered_at
                    FROM questionnaire_answers
                    WHERE session_id = %s
                    ORDER BY answered_at, question_id
                    """,
                    (session_id,),
                )
                answers = [
                    self._answer_from_row(answer_row)
                    for answer_row in cursor.fetchall()
                ]
                answered_ids = {answer.question_id for answer in answers}
                missing = [
                    question_id
                    for question_id in questionnaire.question_ids
                    if question_id not in answered_ids
                ]
                if not questionnaire.submitted and not missing:
                    cursor.execute(
                        """
                        UPDATE questionnaires
                        SET submitted = TRUE, submitted_at = %s
                        WHERE session_id = %s
                        """,
                        (submitted_at, session_id),
                    )
                    questionnaire.submitted = True
                    questionnaire.submitted_at = submitted_at
        return SubmissionSnapshot(questionnaire, answers, missing)

    @staticmethod
    def _answer_from_row(row: dict[str, Any]) -> Answer:
        return Answer(
            session_id=row["session_id"],
            question_id=row["question_id"],
            value=row["value"],
            skipped=bool(row["skipped"]),
            answered_at=row["answered_at"],
        )


def build_question_bank() -> list[Question]:
    quick_templates = [
        ("q_energy", "活力充电", "energy", "我想通过轻度活动恢复状态。"),
        ("q_rest", "松弛疗愈", "recovery", "我今天更需要放松和休息。"),
        ("q_social", "社交连接", "social", "我愿意和别人一起度过空闲时间。"),
        ("q_explore", "乐享探索", "exploration", "我想尝试一些新鲜的体验。"),
        ("q_growth", "自我成长", "growth", "我希望利用时间学习或提升自己。"),
    ]
    questions = [
        Question(
            id=question_id,
            mode="quick",
            category=category,
            dimension=dimension,
            prompt=prompt,
        )
        for question_id, category, dimension, prompt in quick_templates
    ]
    deep_templates = [
        ("活力充电", "energy", "我愿意通过轻度运动恢复精力。"),
        ("松弛疗愈", "recovery", "我希望今天的安排节奏舒缓一些。"),
        ("社交连接", "social", "我愿意主动联系朋友或同学。"),
        ("乐享探索", "exploration", "我愿意尝试平时不常做的活动。"),
        ("自我成长", "growth", "我愿意利用空闲时间完成兴趣学习。"),
    ]
    for index in range(30):
        category, dimension, prompt = deep_templates[index % len(deep_templates)]
        questions.append(
            Question(
                id=f"q_deep_{index + 1:02d}",
                mode="deep",
                category=category,
                dimension=dimension,
                prompt=f"{prompt[:-1]}（第 {index + 1} 题）",
                reverse_scored=index % 10 == 0,
            )
        )
    return questions


QUESTION_BANK = build_question_bank()


class QuestionnaireService:
    def __init__(
        self,
        sessions: SessionService,
        repository: QuestionnaireRepository,
    ) -> None:
        self.sessions = sessions
        self.repository = repository
        self.questions = {question.id: question for question in QUESTION_BANK}

    def start(
        self,
        session_id: str,
        mode: Literal["quick", "deep"],
    ) -> dict[str, Any]:
        session = self.sessions.require_active(session_id)
        existing = self.repository.get_questionnaire(session_id)
        if existing is not None:
            if existing.mode != mode:
                raise HTTPException(
                    status_code=409,
                    detail="问卷已经开始，请使用已有模式",
                )
            return self.payload(existing)

        questions = self.select_questions(mode, session.preferences)
        expected_count = 5 if mode == "quick" else 30
        if len(questions) < expected_count:
            raise HTTPException(status_code=500, detail="审核题库数量不足")
        questionnaire = QuestionnaireSession(
            session_id=session_id,
            mode=mode,
            question_ids=[question.id for question in questions[:expected_count]],
        )
        self.repository.save_questionnaire(questionnaire)
        return self.payload(questionnaire)

    def save_answer(
        self,
        session_id: str,
        question_id: str,
        value: int,
    ) -> dict[str, Any]:
        questionnaire = self.require_active(session_id)
        self.require_question(questionnaire, question_id)
        if value not in {1, 2, 3, 4}:
            raise HTTPException(status_code=400, detail="答案必须为 1-4")
        stored = self.repository.save_answer_if_active(
            Answer(
                session_id=session_id,
                question_id=question_id,
                value=value,
                skipped=False,
                answered_at=utc_now(),
            )
        )
        if not stored:
            raise HTTPException(status_code=409, detail="问卷已经提交或清除")
        return {"saved": True, "question_id": question_id, "value": value}

    def skip_question(
        self,
        session_id: str,
        question_id: str,
    ) -> dict[str, Any]:
        questionnaire = self.require_active(session_id)
        self.require_question(questionnaire, question_id)
        stored = self.repository.save_answer_if_active(
            Answer(
                session_id=session_id,
                question_id=question_id,
                value=None,
                skipped=True,
                answered_at=utc_now(),
            )
        )
        if not stored:
            raise HTTPException(status_code=409, detail="问卷已经提交或清除")
        return {"saved": True, "question_id": question_id, "skipped": True}

    def progress(self, session_id: str) -> dict[str, Any]:
        self.sessions.require_active(session_id)
        questionnaire = self.repository.get_questionnaire(session_id)
        if questionnaire is None:
            raise HTTPException(status_code=409, detail="问卷尚未开始")
        answers = {
            answer.question_id: answer
            for answer in self.repository.get_answers(session_id)
        }
        question_ids = set(questionnaire.question_ids)
        answered = {
            question_id
            for question_id, answer in answers.items()
            if question_id in question_ids and not answer.skipped
        }
        skipped = {
            question_id
            for question_id, answer in answers.items()
            if question_id in question_ids and answer.skipped
        }
        handled = answered | skipped
        return {
            "session_id": session_id,
            "mode": questionnaire.mode,
            "submitted": questionnaire.submitted,
            "total": len(questionnaire.question_ids),
            "answered_count": len(answered),
            "skipped_count": len(skipped),
            "unanswered_count": len(question_ids - handled),
            "answers": {
                question_id: self.answer_payload(answer)
                for question_id, answer in answers.items()
                if question_id in question_ids
            },
        }

    def submit(self, session_id: str) -> dict[str, Any]:
        self.sessions.require_active(session_id)
        snapshot = self.repository.submit_if_complete(session_id, utc_now())
        if snapshot is None:
            raise HTTPException(status_code=409, detail="问卷尚未开始")
        questionnaire = snapshot.questionnaire
        answers = {
            answer.question_id: answer
            for answer in snapshot.answers
        }
        if snapshot.missing_question_ids:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "仍有题目未回答或跳过",
                    "missing_question_ids": snapshot.missing_question_ids,
                },
            )
        return {
            "submitted": True,
            "mode": questionnaire.mode,
            "total": len(questionnaire.question_ids),
            "answered_count": sum(
                not answer.skipped for answer in answers.values()
            ),
            "skipped_count": sum(
                answer.skipped for answer in answers.values()
            ),
        }

    def clear(self, session_id: str) -> None:
        self.sessions.require_active(session_id)
        self.repository.delete_questionnaire(session_id)

    def select_questions(
        self,
        mode: Literal["quick", "deep"],
        preferences: dict[str, Any],
    ) -> list[Question]:
        candidates = [
            question
            for question in QUESTION_BANK
            if question.mode == mode and question.status == "approved"
        ]
        outing = preferences.get("outing", "any")
        company = preferences.get("company", "both")
        return [
            question
            for question in candidates
            if (
                not question.eligible_outing
                or outing == "any"
                or question.eligible_outing == outing
            )
            and (
                not question.eligible_company
                or company == "both"
                or question.eligible_company == company
            )
        ]

    def require_active(self, session_id: str) -> QuestionnaireSession:
        self.sessions.require_active(session_id)
        questionnaire = self.repository.get_questionnaire(session_id)
        if questionnaire is None:
            raise HTTPException(status_code=409, detail="问卷尚未开始")
        if questionnaire.submitted:
            raise HTTPException(status_code=409, detail="问卷已经提交")
        return questionnaire

    def require_question(
        self,
        questionnaire: QuestionnaireSession,
        question_id: str,
    ) -> Question:
        if question_id not in questionnaire.question_ids:
            raise HTTPException(status_code=400, detail="该题不属于当前问卷")
        return self.questions[question_id]

    def payload(self, questionnaire: QuestionnaireSession) -> dict[str, Any]:
        return {
            "session_id": questionnaire.session_id,
            "mode": questionnaire.mode,
            "submitted": questionnaire.submitted,
            "total": len(questionnaire.question_ids),
            "questions": [
                asdict(self.questions[question_id])
                for question_id in questionnaire.question_ids
            ],
            "scale": SCALE,
        }

    @staticmethod
    def answer_payload(answer: Answer) -> dict[str, Any]:
        return {
            "session_id": answer.session_id,
            "question_id": answer.question_id,
            "value": answer.value,
            "skipped": answer.skipped,
            "answered_at": answer.answered_at.isoformat(),
        }
