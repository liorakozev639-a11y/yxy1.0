"""Questionnaire domain service backed exclusively by PostgreSQL."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Optional, Protocol

from fastapi import HTTPException

from session_module import SessionService
from task_repository import CATEGORIES


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
    mode: Literal["quick", "deep", "both"]
    category: str
    dimension: str
    prompt: str
    reverse_scored: bool = False
    eligible_outing: Optional[str] = None
    eligible_company: Optional[str] = None
    scenario_tags: tuple[str, ...] = ()
    priority: int = 0
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


CATEGORY_ALIASES = {
    "energy": "活力充电",
    "calm": "松弛疗愈",
    "recovery": "松弛疗愈",
    "social": "社交连接",
    "explore": "乐享探索",
    "exploration": "乐享探索",
    "growth": "自我成长",
}


QUESTION_ROWS = [
    ("q_energy", "quick", "活力充电", "energy", "我想通过轻度活动恢复状态。", False, None, None, ("short", "home", "solo"), 95),
    ("q_rest", "quick", "松弛疗愈", "recovery", "我今天更需要放松和休息。", False, None, None, ("rest", "low_pressure", "home"), 95),
    ("q_social", "quick", "社交连接", "social", "我愿意和别人一起度过空闲时间。", False, None, "group", ("group", "nearby"), 95),
    ("q_explore", "quick", "乐享探索", "exploration", "我想尝试一些新鲜的体验。", False, None, None, ("city", "nearby", "high_budget"), 95),
    ("q_growth", "quick", "自我成长", "growth", "我希望利用时间学习或提升自己。", False, "home", "solo", ("solo", "home", "short"), 95),
    ("q_deep_01", "deep", "活力充电", "energy", "我愿意通过轻度运动恢复精力。", True, "home", "solo", ("home", "solo", "short"), 80),
    ("q_deep_02", "deep", "松弛疗愈", "recovery", "我希望今天的安排节奏舒缓一些。", False, None, None, ("rest", "low_pressure"), 80),
    ("q_deep_03", "deep", "社交连接", "social", "我愿意主动联系朋友或同学。", False, None, "group", ("group", "nearby"), 80),
    ("q_deep_04", "deep", "乐享探索", "exploration", "我愿意尝试平时不常做的活动。", False, "nearby", None, ("nearby", "medium_budget"), 80),
    ("q_deep_05", "deep", "自我成长", "growth", "我愿意利用空闲时间完成兴趣学习。", False, "home", "solo", ("home", "solo"), 80),
    ("q_deep_06", "deep", "活力充电", "energy", "短时间拉伸能让我更快进入休息状态。", False, "home", "solo", ("short", "home"), 76),
    ("q_deep_07", "deep", "松弛疗愈", "recovery", "我更喜欢不需要复杂准备的恢复型活动。", False, "home", "solo", ("rest", "home", "short"), 76),
    ("q_deep_08", "deep", "社交连接", "social", "低压力的小范围陪伴比大型聚会更适合我。", False, "nearby", "group", ("group", "low_pressure"), 76),
    ("q_deep_09", "deep", "乐享探索", "exploration", "我愿意为一段轻松体验留出适度预算。", False, None, None, ("medium_budget", "high_budget"), 76),
    ("q_deep_10", "deep", "自我成长", "growth", "我希望空闲安排能兼顾放松和一点成长。", False, "home", "solo", ("solo", "home"), 76),
    ("q_deep_11", "deep", "活力充电", "energy", "我愿意去附近走动，让身体重新活跃起来。", False, "nearby", None, ("nearby", "day"), 72),
    ("q_deep_12", "deep", "松弛疗愈", "recovery", "工作或学习后，我需要先降低刺激再安排活动。", False, "home", "solo", ("rest", "low_pressure"), 72),
    ("q_deep_13", "deep", "社交连接", "social", "我愿意和熟人一起完成轻量任务。", False, None, "group", ("group", "short"), 72),
    ("q_deep_14", "deep", "乐享探索", "exploration", "我喜欢在熟悉范围内找一点新鲜感。", False, "nearby", None, ("nearby", "low_budget"), 72),
    ("q_deep_15", "deep", "自我成长", "growth", "完成一个小型学习目标会让我有掌控感。", False, "home", "solo", ("home", "solo", "short"), 72),
    ("q_deep_16", "deep", "活力充电", "energy", "我能接受在居家环境完成简单训练。", False, "home", "solo", ("home", "solo"), 68),
    ("q_deep_17", "deep", "松弛疗愈", "recovery", "我希望今天的计划不要带来额外压力。", False, None, None, ("rest", "low_pressure"), 68),
    ("q_deep_18", "deep", "社交连接", "social", "我愿意把空闲时间用于维系重要关系。", False, None, "group", ("group", "day"), 68),
    ("q_deep_19", "deep", "乐享探索", "exploration", "轻度外出探索会让我觉得这段时间更有记忆点。", False, "city", None, ("city", "day", "high_budget"), 68),
    ("q_deep_20", "deep", "自我成长", "growth", "我喜欢把兴趣提升拆成短时间可以完成的小任务。", False, "home", "solo", ("home", "solo", "short"), 68),
    ("q_deep_21", "deep", "活力充电", "energy", "我不希望所有空闲时间都坐着或躺着。", False, None, None, ("nearby", "day"), 64),
    ("q_deep_22", "deep", "松弛疗愈", "recovery", "安静独处能帮助我更好地恢复。", False, "home", "solo", ("rest", "solo", "home"), 64),
    ("q_deep_23", "deep", "社交连接", "social", "有人一起行动时，我更容易开始任务。", False, None, "group", ("group",), 64),
    ("q_deep_24", "deep", "乐享探索", "exploration", "我愿意尝试新的吃喝或娱乐选择。", False, None, None, ("medium_budget", "high_budget"), 64),
    ("q_deep_25", "deep", "自我成长", "growth", "阅读、写作或练习技能能让我感到充实。", False, "home", "solo", ("home", "solo"), 64),
    ("q_deep_26", "deep", "活力充电", "energy", "身体活动后，我通常更容易放松下来。", False, None, None, ("nearby", "day"), 60),
    ("q_deep_27", "deep", "松弛疗愈", "recovery", "我愿意安排一段不被打扰的休息时间。", False, "home", "solo", ("rest", "home", "solo"), 60),
    ("q_deep_28", "deep", "社交连接", "social", "我能接受临时加入一次小型互动。", False, "nearby", "group", ("group", "nearby"), 60),
    ("q_deep_29", "deep", "乐享探索", "exploration", "我喜欢给普通周末安排一点变化。", False, None, None, ("day", "nearby"), 60),
    ("q_deep_30", "deep", "自我成长", "growth", "空闲时间不适合做任何需要思考的事情。", True, "home", "solo", ("home", "solo"), 60),
    ("q_energy_02", "both", "活力充电", "energy", "我更喜欢用走路、拉伸这类低门槛活动启动计划。", False, "nearby", None, ("nearby", "short"), 58),
    ("q_energy_03", "both", "活力充电", "energy", "如果只有半天休息，我也愿意安排一小段身体活动。", False, None, None, ("half", "short"), 56),
    ("q_energy_04", "both", "活力充电", "energy", "我希望活动强度可控，而不是一上来就很累。", False, None, None, ("low_pressure", "rest"), 54),
    ("q_recovery_02", "both", "松弛疗愈", "recovery", "当我精力不足时，恢复比效率更重要。", False, "home", "solo", ("rest", "home", "solo"), 58),
    ("q_recovery_03", "both", "松弛疗愈", "recovery", "我喜欢呼吸、冥想、热饮这类安静活动。", False, "home", "solo", ("rest", "home", "short"), 56),
    ("q_recovery_04", "both", "松弛疗愈", "recovery", "我希望计划中保留缓冲，不把时间排得太满。", False, None, None, ("rest", "low_pressure", "day"), 54),
    ("q_social_02", "both", "社交连接", "social", "我更愿意和熟悉的人进行小范围互动。", False, None, "group", ("group", "low_pressure"), 58),
    ("q_social_03", "both", "社交连接", "social", "比起独自完成任务，我有时更需要有人陪伴。", False, None, "group", ("group",), 56),
    ("q_social_04", "both", "社交连接", "social", "临时联系朋友或家人对我来说是可接受的。", False, "home", "group", ("group", "short"), 54),
    ("q_explore_02", "both", "乐享探索", "exploration", "我愿意在预算允许时给自己一点吃喝娱乐奖励。", False, None, None, ("medium_budget", "high_budget"), 58),
    ("q_explore_03", "both", "乐享探索", "exploration", "我喜欢不用提前预约也能完成的轻探索。", False, "nearby", None, ("nearby", "short"), 56),
    ("q_explore_04", "both", "乐享探索", "exploration", "如果有较长空闲，我愿意去更远一点的地方看看。", False, "city", None, ("city", "day"), 54),
    ("q_growth_02", "both", "自我成长", "growth", "我愿意用碎片时间推进一个兴趣项目。", False, "home", "solo", ("home", "solo", "short"), 58),
    ("q_growth_03", "both", "自我成长", "growth", "我喜欢能留下作品、笔记或清单的活动。", False, "home", "solo", ("home", "solo"), 56),
    ("q_growth_04", "both", "自我成长", "growth", "我希望休息结束后能感觉自己有一点进步。", False, None, "solo", ("solo", "day"), 54),
]


EXPANSION_PROMPTS = {
    "活力充电": (
        "十分钟的低冲击有氧对我来说容易开始。",
        "我愿意利用附近空间快走一会儿。",
        "居家活动度练习能让我感觉更舒展。",
        "短时间核心和平衡练习是可接受的。",
        "天气合适时我愿意安排一次轻松骑行。",
        "跟着音乐做节奏运动会让我更有动力。",
        "我更喜欢用短时活动启动休息时间。",
        "恢复精力后，我愿意再安排一点身体训练。",
        "和熟人一起做轻量运动会让我更容易坚持。",
        "晒太阳并走动一会儿能改善我的状态。",
        "我希望运动安排不需要复杂装备。",
        "我能接受把身体活动拆成两个短时段完成。",
        "比起高强度训练，我更在意活动后的轻松感。",
        "我愿意尝试能在室内完成的低门槛运动。",
        "空闲时适度活动能帮助我从久坐中恢复。",
        "我喜欢有明确开始和结束时间的身体活动。",
        "我希望任务强度可以随着当天精力调整。",
        "短距离步行比完全不动更适合我的休息方式。",
        "我愿意为一次轻量活动换上舒适的衣服。",
        "没有同伴时，我也可以独自完成简单运动。",
    ),
    "松弛疗愈": (
        "缓慢呼吸几分钟能让我安定下来。",
        "精力不足时，我更需要低刺激的休息。",
        "给自己泡一杯热饮是一种有效放松。",
        "听舒缓音乐能帮助我从忙碌中抽离。",
        "独处一会儿能让我恢复得更好。",
        "渐进式肌肉放松对我有吸引力。",
        "整理一个很小的区域不会让我感到压力。",
        "在户外安静坐一会儿能让我放松。",
        "我愿意安排睡前的舒缓仪式。",
        "我希望计划里有不追求效率的空白时间。",
        "不看手机地休息十分钟对我有帮助。",
        "我更喜欢不需要和别人沟通的恢复活动。",
        "环境安静会影响我的休息质量。",
        "我愿意尝试热敷或护手这类自我照顾。",
        "我可以接受把任务换成更轻松的版本。",
        "休息日不安排太满会让我更安心。",
        "我希望从紧张状态慢慢过渡到放松状态。",
        "写下情绪或想法能帮助我减轻压力。",
        "我愿意为休息留出一个不被打扰的角落。",
        "偶尔什么都不做对我也是有价值的。",
    ),
    "社交连接": (
        "给熟人发一条近况消息是轻松的社交方式。",
        "和家人短暂联系能让我感觉被支持。",
        "我喜欢没有太多人参与的小范围互动。",
        "和朋友一起吃简单的一餐对我有吸引力。",
        "结伴散步比正式聚会更适合我。",
        "两三个人一起玩桌游不会让我有压力。",
        "我愿意主动约同学或朋友做一件小事。",
        "临时的低压力邀约对我来说可以接受。",
        "分享一首歌或一件小事也是有意义的交流。",
        "表达感谢能让我更愿意维系关系。",
        "我更愿意和熟悉的人待在一起。",
        "社交活动有明确结束时间会让我更安心。",
        "我愿意先在线上联系，再决定是否见面。",
        "有人陪伴时，我更容易开始一项任务。",
        "我希望社交安排可以根据当天精力取消或调整。",
        "短时间聊天也能满足我的连接需求。",
        "我愿意和室友或同学共同完成轻量任务。",
        "我不需要大型聚会也能感受到社交满足。",
        "我愿意为重要的人留出一段空闲时间。",
        "独处时我也不会因为没有社交而焦虑。",
    ),
    "乐享探索": (
        "尝试一杯新口味饮品会让我感到新鲜。",
        "我愿意为一份喜欢的小点心留出预算。",
        "在熟悉街区随便走走也是一种探索。",
        "看轻松的节目能让我享受空闲时间。",
        "玩一会儿休闲游戏对我来说是放松。",
        "拍下有趣的街景会让我更投入外出。",
        "做一份简单的小食是一种有趣体验。",
        "我喜欢不需要预约的临时小探索。",
        "逛书店或文创店会让我有好心情。",
        "免费的公共空间也值得去看看。",
        "我希望探索任务在预算上是可控的。",
        "我愿意为周末安排一点不同于日常的事。",
        "短时间的娱乐也能让我获得满足感。",
        "我更喜欢轻松而不是刺激强烈的体验。",
        "我愿意独自去发现附近的新角落。",
        "和同伴一起尝试新鲜事物会更有趣。",
        "我希望活动结束后能留下一个小记忆点。",
        "我会根据天气决定是否外出探索。",
        "我愿意尝试一个以前没有点过的选项。",
        "普通的一天也可以安排一点小奖励。",
    ),
    "自我成长": (
        "读几页感兴趣的内容会让我感到充实。",
        "写下简短笔记能帮助我整理思路。",
        "整理电脑或手机文件会让我更有掌控感。",
        "练习速写或手工能让我专注下来。",
        "短时间语言练习适合放进空闲安排。",
        "听知识播客后记一两点收获是可行的。",
        "复习课程中的一个小知识点不会压力太大。",
        "学习一个微小技能也值得安排时间。",
        "写一页生活计划能让我对未来更清楚。",
        "练习乐器或创作会让我感觉有进步。",
        "我喜欢把大目标拆成短时间能完成的小步。",
        "空闲时整理待读书单会让我有动力。",
        "我愿意为兴趣项目留下一点可见成果。",
        "我更容易从有明确主题的学习任务开始。",
        "写下三个问题比立刻解决所有问题更轻松。",
        "我愿意在休息日复盘最近学到的内容。",
        "我希望成长类任务也能保留轻松感。",
        "我可以接受只完成学习任务的一小部分。",
        "把知识和日常生活联系起来会让我更愿意学习。",
        "完成一个小练习会让我愿意继续投入时间。",
    ),
}


EXPANSION_DIMENSIONS = {
    "活力充电": "energy",
    "松弛疗愈": "recovery",
    "社交连接": "social",
    "乐享探索": "exploration",
    "自我成长": "growth",
}


def build_expansion_rows() -> list[tuple[Any, ...]]:
    rows: list[tuple[Any, ...]] = []
    for category, prompts in EXPANSION_PROMPTS.items():
        prefix = {
            "活力充电": "energy",
            "松弛疗愈": "recovery",
            "社交连接": "social",
            "乐享探索": "explore",
            "自我成长": "growth",
        }[category]
        for index, prompt in enumerate(prompts, start=1):
            mode = "both" if index <= 4 else "deep"
            eligible_outing = "home" if category in {"松弛疗愈", "自我成长"} and index % 3 == 0 else None
            eligible_company = "group" if category == "社交连接" and index % 3 != 0 else None
            rows.append(
                (
                    f"q_{prefix}_extra_{index:02d}",
                    mode,
                    category,
                    EXPANSION_DIMENSIONS[category],
                    prompt,
                    index == 20,
                    eligible_outing,
                    eligible_company,
                    ("short", "home") if eligible_outing == "home" else ("nearby", "day"),
                    52 - index,
                )
            )
    return rows


QUESTION_ROWS.extend(build_expansion_rows())


def build_question_bank() -> list[Question]:
    return [
        Question(
            id=question_id,
            mode=mode,
            category=category,
            dimension=dimension,
            prompt=prompt,
            reverse_scored=reverse_scored,
            eligible_outing=eligible_outing,
            eligible_company=eligible_company,
            scenario_tags=scenario_tags,
            priority=priority,
        )
        for (
            question_id,
            mode,
            category,
            dimension,
            prompt,
            reverse_scored,
            eligible_outing,
            eligible_company,
            scenario_tags,
            priority,
        ) in QUESTION_ROWS
    ]


QUESTION_BANK = build_question_bank()


def normalize_selected_categories(preferences: dict[str, Any]) -> list[str]:
    categories: list[str] = []
    for raw_category in preferences.get("categories", []):
        category = CATEGORY_ALIASES.get(str(raw_category), str(raw_category))
        if category in CATEGORIES and category not in categories:
            categories.append(category)
    return categories or list(CATEGORIES)


def preference_tags(preferences: dict[str, Any]) -> set[str]:
    tags = {
        str(preferences.get("outing", "any")),
        str(preferences.get("company", "both")),
        str(preferences.get("duration", "half")),
        f"{preferences.get('budget', 'medium')}_budget",
    }
    if preferences.get("rest_only"):
        tags.update({"rest", "low_pressure"})
    if preferences.get("duration") in {"short", "hour"}:
        tags.add("short")
    return tags


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
        expected_count = 5 if mode == "quick" else 30
        selected_categories = normalize_selected_categories(preferences)
        selected_category_index = {
            category: index
            for index, category in enumerate(selected_categories)
        }
        tags = preference_tags(preferences)
        outing = preferences.get("outing", "any")
        company = preferences.get("company", "both")
        allowed_modes = {"quick", "both"} if mode == "quick" else {"deep", "both"}
        candidates = [
            question
            for question in QUESTION_BANK
            if question.status == "approved"
            and question.mode in allowed_modes
            and (
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
        if len(candidates) < expected_count:
            candidate_ids = {question.id for question in candidates}
            candidates.extend(
                question
                for question in QUESTION_BANK
                if question.status == "approved"
                and question.mode in allowed_modes
                and question.id not in candidate_ids
            )
        ranked = sorted(
            candidates,
            key=lambda question: (
                -self.question_score(question, selected_category_index, tags, mode),
                selected_category_index.get(question.category, len(CATEGORIES)),
                question.id,
            ),
        )
        selected: list[Question] = []
        used_ids: set[str] = set()
        for category in selected_categories[:expected_count]:
            match = next(
                (
                    question
                    for question in ranked
                    if question.category == category
                    and question.id not in used_ids
                ),
                None,
            )
            if match is not None:
                selected.append(match)
                used_ids.add(match.id)
        for question in ranked:
            if len(selected) >= expected_count:
                break
            if question.id not in used_ids:
                selected.append(question)
                used_ids.add(question.id)
        return selected

    @staticmethod
    def question_score(
        question: Question,
        selected_category_index: dict[str, int],
        tags: set[str],
        mode: Literal["quick", "deep"],
    ) -> int:
        score = question.priority
        if question.category in selected_category_index:
            score += 100 - selected_category_index[question.category] * 6
        if question.mode == mode:
            score += 12
        elif question.mode == "both":
            score += 8
        score += len(set(question.scenario_tags).intersection(tags)) * 10
        return score

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
