"""Runnable Questionnaire Module example.

Run:
    python -m pip install fastapi uvicorn
    python examples/questionnaire_module.py

Open:
    http://127.0.0.1:8001/docs

This example is synchronous and in-memory. In production, replace the demo
session store and repositories with Session Module and PostgreSQL.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


# 创建 FastAPI 应用，向前端提供问卷相关接口
app = FastAPI(title="Free Time Agent - Questionnaire Module")

# 前端展示的四级问卷量表
SCALE = [
    {"value": 1, "label": "完全不同意"},
    {"value": 2, "label": "不太同意"},
    {"value": 3, "label": "比较同意"},
    {"value": 4, "label": "非常同意"},
]


def utc_now() -> datetime:
    # 统一使用 UTC
    return datetime.now(timezone.utc)


def make_id(prefix: str) -> str:
    # 生成唯一 ID
    return f"{prefix}_{uuid4().hex}"

@dataclass(frozen=True)
class Question:
    # 题目变量，题目所属模式，分类，维度，规则
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
    # 用户对单道题的答案，跳过题的 value 为 None
    session_id: str
    question_id: str
    value: Optional[int]
    skipped: bool
    answered_at: datetime


@dataclass
class QuestionnaireSession:
    # 记录问卷会话，题目范围，提交状态
    session_id: str
    mode: Literal["quick", "deep"]
    question_ids: list[str]
    submitted: bool = False
    started_at: datetime = field(default_factory=utc_now)
    submitted_at: Optional[datetime] = None


@dataclass
class DemoSession:
    # 独立运行示例使用的简化会话对象
    id: str
    preferences: dict[str, Any]


class DemoSessionStore:
    """Standalone replacement for the real Session Module."""

    def __init__(self) -> None:
        self.sessions: dict[str, DemoSession] = {}

    def create(self, preferences: Optional[dict[str, Any]] = None) -> DemoSession:
        # 创建并保存会话
        session = DemoSession(
            id=make_id("sess"),
            preferences=preferences
            or {
                "outing": "home",
                "company": "solo",
                "budget_max": 100,
                "duration_minutes": 180,
            },
        )
        self.sessions[session.id] = session
        return session

    def require(self, session_id: str) -> DemoSession:
        session = self.sessions.get(session_id)
        if session is None:
            raise HTTPException(status_code=401, detail="会话不存在")
        return session


class QuestionnaireRepository:
    """In-memory repository. Production uses questionnaire tables in PostgreSQL."""

    def __init__(self) -> None:
        self.questionnaires: dict[str, QuestionnaireSession] = {}
        self.answers: dict[tuple[str, str], Answer] = {}

    def save_questionnaire(self, item: QuestionnaireSession) -> None:
        self.questionnaires[item.session_id] = item

    def get_questionnaire(
        self,
        session_id: str,
    ) -> Optional[QuestionnaireSession]:
        return self.questionnaires.get(session_id)

    def save_answer(self, answer: Answer) -> None:
        # 相同 session_id + question_id 的后写答案覆盖旧答案
        self.answers[(answer.session_id, answer.question_id)] = answer

    def get_answers(self, session_id: str) -> list[Answer]:
        return [
            answer
            for (stored_session_id, _), answer in self.answers.items()
            if stored_session_id == session_id
        ]

    def clear_answers(self, session_id: str) -> None:
        for key in [key for key in self.answers if key[0] == session_id]:
            del self.answers[key]


def build_question_bank() -> list[Question]:
    # 题库示例
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

    # deep 30 道题
    for index in range(30):
        category, dimension, prompt = deep_templates[index % len(deep_templates)]
        questions.append(
            Question(
                id=f"q_deep_{index + 1:02d}",
                mode="deep",
                category=category,
                dimension=dimension,
                prompt=f"{prompt[:-1]}（第 {index + 1} 题）",
                # 每隔十道题为反向计分题
                reverse_scored=index % 10 == 0,
            )
        )

    return questions


QUESTION_BANK = build_question_bank()


class StartQuestionnaireRequest(BaseModel):
    # 只允许 quick 和 deep 两种问卷模式
    mode: Literal["quick", "deep"]


class AnswerRequest(BaseModel):
    # 答案必须是 1-4，对应 SCALE 中的四个选项
    value: int = Field(ge=1, le=4)


class QuestionnaireService:
    # 问卷业务服务：会话、题目、答案、进度、流程
    def __init__(
        self,
        sessions: DemoSessionStore,
        repository: QuestionnaireRepository,
    ) -> None:
        self.sessions = sessions
        self.repository = repository
        self.questions = {question.id: question for question in QUESTION_BANK}

    def start(
        self,
        session_id: str,
        mode: Literal#限制变量只能取特定的值
        ["quick", "deep"],
    ) -> dict[str, Any]:
        # 先校验会话，再读取会话中的前置偏好
        session = self.sessions.require(session_id)
        existing = self.repository.get_questionnaire(session_id)

        if existing is not None and not existing.submitted:
            # 已开始的问卷直接恢复原先的数据
            if existing.mode != mode:
                raise HTTPException(
                    status_code=409,
                    detail="问卷已经开始，请使用已有模式",
                )
            return self.payload(existing)

        if existing is not None and existing.submitted:
            # 重新开始会清理当前匿名会话的旧答案并创建新问卷
            self.repository.clear_answers(session_id)

        # 根据模式，出行方式和同行方式筛选审核通过的题目
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
        # 保存答案前必须确认会话、问卷和题目归属均有效
        questionnaire = self.require_active(session_id)
        self.require_question(questionnaire, question_id)

        if value not in {1, 2, 3, 4}:
            raise HTTPException(status_code=400, detail="答案必须为 1-4")

        self.repository.save_answer(
            Answer(
                session_id=session_id,
                question_id=question_id,
                value=value,
                skipped=False,
                answered_at=utc_now(),
            )
        )
        return {"saved": True, "question_id": question_id, "value": value}

    def skip_question(
        self,
        session_id: str,
        question_id: str,
    ) -> dict[str, Any]:
        # 跳过也要记录答案状态，提交时不会被视为遗漏题目
        questionnaire = self.require_active(session_id)
        self.require_question(questionnaire, question_id)

        self.repository.save_answer(
            Answer(
                session_id=session_id,
                question_id=question_id,
                value=None,
                skipped=True,
                answered_at=utc_now(),
            )
        )
        return {"saved": True, "question_id": question_id, "skipped": True}

    def progress(self, session_id: str) -> dict[str, Any]:
        # 统计已回答、已跳过和未处理题目
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
                question_id: asdict(answer)
                for question_id, answer in answers.items()
                if question_id in question_ids
            },
        }

    def submit(self, session_id: str) -> dict[str, Any]:
        # 提交前要求每道题都有答案，跳过问题需要有skipped 记录
        questionnaire = self.require_active(session_id)
        answers = {
            answer.question_id: answer
            for answer in self.repository.get_answers(session_id)
        }
        missing = [
            question_id
            for question_id in questionnaire.question_ids
            if question_id not in answers
        ]

        if missing:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "仍有题目未回答或跳过",
                    "missing_question_ids": missing,
                },
            )

        # 问卷提交后进入 Profile Module
        questionnaire.submitted = True
        questionnaire.submitted_at = utc_now()
        self.repository.save_questionnaire(questionnaire)

        return {
            "submitted": True,
            "mode": questionnaire.mode,
            "total": len(questionnaire.question_ids),
            "answered_count": sum(
                not answer.skipped for answer in answers.values()
            ),
            "skipped_count": sum(answer.skipped for answer in answers.values()),
            "next_stage": "profile",
            "profile_input": self.build_profile_input(questionnaire, answers),
        }

    def select_questions(
        self,
        mode: Literal["quick", "deep"],
        preferences: dict[str, Any],
    ) -> list[Question]:
        # 按问卷模式和审核状态筛选候选题
        candidates = [
            question
            for question in QUESTION_BANK
            if question.mode == mode and question.status == "approved"
        ]
        outing = preferences.get("outing", "any")
        company = preferences.get("company", "both")

        # 按用户的居家/外出、独处/结伴偏好过滤题目
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
        # 设置问卷的两个边界为问卷未开始，问卷已经提交
        self.sessions.require(session_id)
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
        # 防止用户提交不属于当前问卷的题目
        if question_id not in questionnaire.question_ids:
            raise HTTPException(status_code=400, detail="该题不属于当前问卷")
        return self.questions[question_id]

    def payload(self, questionnaire: QuestionnaireSession) -> dict[str, Any]:
        # 整理为前端可直接使用的 JSON 数据
        return {
            "session_id": questionnaire.session_id,
            "mode": questionnaire.mode,
            "total": len(questionnaire.question_ids),
            "questions": [
                asdict(self.questions[question_id])
                for question_id in questionnaire.question_ids
            ],
            "scale": SCALE,
        }

    def build_profile_input(
        self,
        questionnaire: QuestionnaireSession,
        answers: dict[str, Answer],
    ) -> dict[str, Any]:
        # 将答案整理为画像维度，提交后交给 Profile Module 处理
        dimensions: dict[str, list[float]] = {}

        for question_id in questionnaire.question_ids:
            question = self.questions[question_id]
            answer = answers[question_id]
            # 跳过题使用中性分，避免跳过行为影响偏好方向
            value = 2.5 if answer.skipped else float(answer.value)

            if question.reverse_scored:
                # 反向题使用 5-value
                value = 5 - value

            dimensions.setdefault(question.dimension, []).append(value)

        # 将 1～4 的平均分标准化到 0～1
        scores = {
            dimension: round((sum(values) / len(values) - 1) / 3, 2)
            for dimension, values in dimensions.items()
        }

        return {
            "session_id": questionnaire.session_id,
            "scores": scores,
            "source": "questionnaire-rule-v1",
        }


session_store = DemoSessionStore()
repository = QuestionnaireRepository()
service = QuestionnaireService(session_store, repository)


# 创建演示会话；正式环境由 Session Module 提供会话接口
@app.post("/api/v1/demo/sessions")
def create_demo_session() -> dict[str, Any]:
    session = session_store.create()
    return {
        "data": {
            "session_id": session.id,
            "preferences": session.preferences,
        },
        "error": None,
    }


# 开始或恢复 quick/deep 问卷
@app.post("/api/v1/sessions/{session_id}/questionnaire/start")
def start_questionnaire(
    session_id: str,
    body: StartQuestionnaireRequest,
) -> dict[str, Any]:
    return {"data": service.start(session_id, body.mode), "error": None}


# 保存或修改答案
@app.patch("/api/v1/sessions/{session_id}/questionnaire/answers/{question_id}")
def save_answer(
    session_id: str,
    question_id: str,
    body: AnswerRequest,
) -> dict[str, Any]:
    return {
        "data": service.save_answer(session_id, question_id, body.value),
        "error": None,
    }


# 跳过
@app.post("/api/v1/sessions/{session_id}/questionnaire/skip/{question_id}")
def skip_question(session_id: str, question_id: str) -> dict[str, Any]:
    return {
        "data": service.skip_question(session_id, question_id),
        "error": None,
    }


# 获取问卷填写进度
@app.get("/api/v1/sessions/{session_id}/questionnaire/progress")
def get_progress(session_id: str) -> dict[str, Any]:
    return {"data": service.progress(session_id), "error": None}


# 提交问卷并生成 Profile Module 的结构化输入
@app.post("/api/v1/sessions/{session_id}/questionnaire/submit")
def submit_questionnaire(session_id: str) -> dict[str, Any]:
    return {"data": service.submit(session_id), "error": None}


if __name__ == "__main__":
    uvicorn.run("questionnaire_module:app", host="127.0.0.1", port=8001)
