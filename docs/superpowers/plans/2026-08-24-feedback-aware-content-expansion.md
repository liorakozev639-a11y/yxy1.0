# 反馈驱动推荐与内容扩充 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 1–2 分和跳过操作在当前会话内永久排除同组任务，并将正式任务库扩展为 200 条、正式问卷库扩展为 105 题。

**Architecture:** 新建 `recommendation_memory.py` 作为唯一的会话级负向偏好存储边界；推荐、替换和重排只读取它提供的细分组集合。正式题目只由 `questionnaire_module.py` 提供，`task_repository.py` 只维护公共任务与任务筛选。

**Tech Stack:** Python 3.12、FastAPI、Pydantic、psycopg 3、PostgreSQL、原生 JavaScript、Node `node:test`、Python `unittest`。

**Spec:** `docs/superpowers/specs/2026-08-24-feedback-aware-content-expansion-design.md`

## Global Constraints

- 仅使用 PostgreSQL；不新增 MQ、异步任务、地图、商户、活动或大模型 API。
- 排除规则只存在于当前 `session_id` 及其后续生成的计划；不新增登录或跨会话记忆。
- 评分阈值固定为 `1`、`2`；评分 `3`、`4`、`5` 只保存反馈。
- 相似任务按细分 `feedback_group` 排除，不能按五大 `category` 整类排除。
- 公共任务总数必须为 200、每类 40；正式问卷总数必须为 105、每类 21。
- 快速版只可抽取 `quick`、`both`；深度版只可抽取 `deep`、`both`。
- 保持现有 API 路径、无 Token 会话方式与像素前端风格；新增字段必须向后兼容。
- 每个任务先写失败测试，再写最小实现，验证通过后单独提交；不得提交 `backup-before-github-20260814-1/`。

---

## 文件结构与责任

| 文件 | 修改类型 | 责任 |
| --- | --- | --- |
| `task_repository.py` | 修改 | 200 条公共任务、`feedback_group`、删除未使用的重复问卷库 |
| `questionnaire_module.py` | 修改 | 105 条正式题目、模式硬过滤与偏好排序 |
| `recommendation_memory.py` | 新建 | `session_task_exclusions` 初始化、记录、读取和统计 |
| `feedback_service.py` | 修改 | 低分反馈写入排除记忆 |
| `execution_service.py` | 修改 | 执行阶段跳过写入排除记忆 |
| `recommendation_module.py` | 修改 | 统一过滤已排除细分组并返回统计 |
| `mvp_orchestrator.py` | 修改 | 首次生成计划读取会话排除组 |
| `plan_module.py` | 修改 | 编辑跳过、替换、重排读写排除记忆 |
| `main.py` | 修改 | 服务依赖装配、响应传递 |
| `frontend/app.js` | 修改 | 展示避开数量与负向反馈提示 |
| `tests/` | 修改/新建 | 内容数量、排除规则与主链路回归 |
| `README.md`、`docs/api.md` | 修改 | 内容数量、行为、响应字段与本地测试说明 |

## Task 1: 扩充公共任务库并清理重复题库

**Files:**
- Modify: `task_repository.py:39-413`
- Modify: `tests/test_task_repository_expansion.py`
- Modify: `tests/test_plan_replacement_rules.py`

**Interfaces:**
- Consumes: `TaskRepository.public_tasks`、`TaskRepository.search_tasks(session_id, budget_limit, max_duration, outing, company, categories=None, scenarios=None)`。
- Produces: `Task.feedback_group: str`，公共任务总数 200，每个任务都有非空细分组；`task_repository.py` 不再导出运行时问卷题库。

- [ ] **Step 1: 写入任务库数量与细分组的失败测试**

```python
from collections import Counter

from task_repository import CATEGORIES, PUBLIC_TASKS


def test_public_task_bank_has_forty_tasks_per_category_and_feedback_groups():
    counts = Counter(task.category for task in PUBLIC_TASKS)
    assert len(PUBLIC_TASKS) == 200
    assert counts == {category: 40 for category in CATEGORIES}
    assert all(task.feedback_group for task in PUBLIC_TASKS)
    assert all(task.feedback_group.startswith((
        "energy_", "recovery_", "social_", "explore_", "growth_",
    )) for task in PUBLIC_TASKS)
```

在 `tests/test_plan_replacement_rules.py` 的构造任务中显式传入 `feedback_group="recovery_quiet_home"`，确保位置参数兼容不掩盖新字段。

- [ ] **Step 2: 运行失败测试确认红灯**

Run:

```powershell
& ".\.venv-debug\Scripts\python.exe" -m unittest tests.test_task_repository_expansion -v
```

Expected: `len(PUBLIC_TASKS) == 200` 断言失败，或 `Task` 尚无 `feedback_group` 属性。

- [ ] **Step 3: 为任务模型与 200 条内容实现最小变更**

将 `Task` 新字段置于现有可选字段之后，保持旧构造调用可运行：

```python
@dataclass(frozen=True)
class Task:
    id: str
    title: str
    category: str
    duration: int
    budget: int
    outing: str
    company: str
    status: str = "approved"
    owner_session_id: Optional[str] = None
    scenarios: tuple[str, ...] = ()
    feedback_group: str = ""
```

把 `_ACTIVITY_ROWS` 改为包含第九列 `feedback_group`，`PUBLIC_TASKS` 构造时传入该字段。保留现有 150 条并分组；再为每类追加以下 10 条，且每条使用列出的组名：

| 分类 | 新任务（标题 -> feedback_group） |
| --- | --- |
| 活力充电 | 晨间八分钟关节唤醒 -> `energy_mobility_home`；室内踏步听播客 -> `energy_low_impact_home`；在公园做一轮拉伸 -> `energy_mobility_outdoor`；练习平衡与核心动作 -> `energy_core_balance`；骑共享单车短途绕行 -> `energy_light_cycling`；做十分钟拳击操 -> `energy_rhythm_cardio`；在楼下走一段上坡路 -> `energy_brisk_walk`；跟练坐姿拉伸 -> `energy_mobility_home`；尝试一轮轻器械训练 -> `energy_strength_light`；完成一次散步打卡 -> `energy_brisk_walk` |
| 松弛疗愈 | 做一杯热可可慢慢喝 -> `recovery_warm_drink`；给眼睛做十分钟闭目休息 -> `recovery_quiet_home`；听一张完整的轻音乐专辑 -> `recovery_music_rest`；做一次香氛或护手护理 -> `recovery_self_care`；看窗外发呆十分钟 -> `recovery_quiet_home`；整理床铺后休息 -> `recovery_light_tidy`；去附近长椅坐一会 -> `recovery_quiet_outdoor`；完成一段渐进式肌肉放松 -> `recovery_body_relax`；泡一次温水澡 -> `recovery_self_care`；写下三件今天不必完成的事 -> `recovery_pressure_release` |
| 社交连接 | 给老朋友发一条近况消息 -> `social_light_contact`；和同学约一次校园散步 -> `social_small_group`；与家人视频通话十五分钟 -> `social_family_contact`；和朋友分享一首歌 -> `social_light_contact`；约人一起吃简单早餐 -> `social_meal_together`；参加一次两三人的桌游 -> `social_small_group`；向朋友表达一次感谢 -> `social_light_contact`；和室友做一顿简单晚饭 -> `social_meal_together`；约熟人一起逛校园或街区 -> `social_walk_together`；和家人聊一件开心的小事 -> `social_family_contact` |
| 乐享探索 | 去附近买一份喜欢的小点心 -> `explore_food_drink`；尝试一款新口味茶饮 -> `explore_food_drink`；看一集轻松综艺 -> `explore_screen_entertainment`；逛一次书店或文创店 -> `explore_local_browse`；玩二十分钟休闲游戏 -> `explore_game_relax`；在街区拍三张有趣照片 -> `explore_photo_walk`；尝试做一份水果酸奶碗 -> `explore_food_make`；看一场线上直播回放 -> `explore_screen_entertainment`；去便利店选一件没买过的小零食 -> `explore_food_drink`；参观一个免费的校园展览或公共空间 -> `explore_local_browse` |
| 自我成长 | 抄写一段喜欢的文字 -> `growth_reading_writing`；整理十个常用电脑文件 -> `growth_digital_organize`；练习十分钟速写 -> `growth_creative_practice`；学一个常用快捷键 -> `growth_skill_micro`；写一页旅行或生活计划 -> `growth_planning`；听一节短知识播客并记笔记 -> `growth_learning_audio`；完成一轮单词复习 -> `growth_language_practice`；为正在学的课程列三个问题 -> `growth_learning_review`；练习一首简单乐器片段 -> `growth_creative_practice`；整理一本待读书单 -> `growth_reading_writing` |

为原有 150 条按其动作填入与上述命名一致的组；每类至少有 4 个不同组。删除 `Question`、`_QUESTION_ROWS`、`QUESTION_BANK`、`search_questions` 和仅用于旧题库的断言、打印信息，使此模块只承担任务库职责。

- [ ] **Step 4: 运行任务库与替换规则测试确认绿灯**

Run:

```powershell
& ".\.venv-debug\Scripts\python.exe" -m unittest tests.test_task_repository_expansion tests.test_plan_replacement_rules -v
```

Expected: 两个测试模块全部通过，公共任务统计为 200 / 每类 40。

- [ ] **Step 5: 提交任务内容边界**

```powershell
git add task_repository.py tests/test_task_repository_expansion.py tests/test_plan_replacement_rules.py
git commit -m "feat: expand task library with feedback groups"
```

## Task 2: 扩充正式问卷库并强制模式过滤

**Files:**
- Modify: `questionnaire_module.py:350-676`
- Modify: `tests/test_questionnaire_selection.py`
- Modify: `tests/test_questionnaire_service.py`

**Interfaces:**
- Consumes: `QuestionnaireService.select_questions(mode, preferences)`。
- Produces: 105 条 `QUESTION_BANK`、每类 21 条；快速版只含 `quick/both`，深度版只含 `deep/both`。

- [ ] **Step 1: 写入题库数量、分类分布、模式边界的失败测试**

```python
def test_question_bank_contains_one_hundred_and_five_approved_questions():
    assert len(QUESTION_BANK) == 105
    assert {
        category: sum(question.category == category for question in QUESTION_BANK)
        for category in CATEGORIES
    } == {category: 21 for category in CATEGORIES}
    assert all(question.status == "approved" for question in QUESTION_BANK)


def test_questionnaire_modes_are_hard_filtered():
    preferences = {
        "categories": ["活力充电", "松弛疗愈", "社交连接"],
        "outing": "nearby", "company": "both",
        "duration": "day", "budget": "medium",
    }
    quick = service.select_questions("quick", preferences)
    deep = service.select_questions("deep", preferences)
    assert len(quick) == 5
    assert len(deep) == 30
    assert all(question.mode in {"quick", "both"} for question in quick)
    assert all(question.mode in {"deep", "both"} for question in deep)
```

- [ ] **Step 2: 运行问卷选择测试确认红灯**

Run:

```powershell
& ".\.venv-debug\Scripts\python.exe" -m unittest tests.test_questionnaire_selection -v
```

Expected: 题库数量断言失败；现有候选逻辑会允许错误模式的题目进入集合。

- [ ] **Step 3: 扩展 `QUESTION_ROWS` 并实现模式硬过滤**

向 `QUESTION_ROWS` 每个分类追加 10 条，使每类从 11 条到 21 条。新增题目分别覆盖下列主题：活力充电覆盖低冲击有氧、户外走动、居家活动度、核心平衡、骑行、节奏运动、短时启动、恢复后训练、同伴轻运动、晒太阳走动；松弛疗愈覆盖呼吸放松、低刺激休息、热饮仪式、音乐休息、独处、肌肉放松、轻整理、户外静坐、睡前放松、压力卸载；社交连接覆盖熟人互动、家人联系、轻量消息、共同进餐、结伴散步、桌游、同学联系、低压力邀约、分享兴趣、感谢表达；乐享探索覆盖咖啡茶饮、轻食、街区漫游、屏幕娱乐、轻游戏、拍照、免费公共空间、简单制作、书店文创、短时尝鲜；自我成长覆盖阅读笔记、文件整理、速写手工、语言练习、知识播客、课程复习、微技能、生活计划、乐器练习、作品清单。

在 `select_questions` 中首先限定模式，再执行出行和同行过滤：

```python
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
```

候选不足的补足分支必须同样加上 `question.mode in allowed_modes`。保留原有分类覆盖、`question_score` 和去重循环；删去旧的 “50 / 每类 10” 断言。

- [ ] **Step 4: 运行问卷选择与服务回归测试确认绿灯**

Run:

```powershell
& ".\.venv-debug\Scripts\python.exe" -m unittest tests.test_questionnaire_selection tests.test_questionnaire_service -v
```

Expected: 快速版固定返回 5 条且只含 `quick/both`；深度版固定返回 30 条且只含 `deep/both`；无重复题目。

- [ ] **Step 5: 提交问卷内容与选择逻辑**

```powershell
git add questionnaire_module.py tests/test_questionnaire_selection.py tests/test_questionnaire_service.py
git commit -m "feat: expand questionnaire bank and enforce modes"
```


## Task 3: 建立会话级推荐记忆模块

**Files:**
- Create: recommendation_memory.py
- Create: tests/test_recommendation_memory.py

**Interfaces:**
- Consumes: database_url、SessionService、计划项 task_id 与 TaskRepository。
- Produces:

~~~python
class RecommendationMemory:
    def record_plan_item_exclusion(
        self, session_id: str, plan_id: str, item_id: str, source: Literal["low_rating", "skipped"]
    ) -> dict[str, Any]:
        raise NotImplementedError

    def list_excluded_groups(self, session_id: str) -> set[str]:
        raise NotImplementedError

    def summary(self, session_id: str) -> dict[str, int]:
        raise NotImplementedError
~~~

- [ ] **Step 1: 写入 PostgreSQL 记忆模块的失败测试**

~~~python
def test_recording_same_group_is_idempotent_and_session_scoped(self):
    first = self.memory.record_plan_item_exclusion(
        self.session_id, self.plan_id, self.item_id, "low_rating"
    )
    second = self.memory.record_plan_item_exclusion(
        self.session_id, self.plan_id, self.sibling_item_id, "skipped"
    )
    self.assertEqual(first["feedback_group"], "growth_reading_writing")
    self.assertEqual(second["feedback_group"], "growth_reading_writing")
    self.assertEqual(self.memory.list_excluded_groups(self.session_id), {
        "growth_reading_writing"
    })
    self.assertEqual(self.memory.summary(self.session_id)["excluded_group_count"], 1)
~~~

测试准备两个不同 item_id，但都使用任务库中同一个 feedback_group 的 task_id；另建第二个 session，确认其集合为空。

- [ ] **Step 2: 运行记忆模块测试确认红灯**

Run:

~~~powershell
& ".\.venv-debug\Scripts\python.exe" -m unittest tests.test_recommendation_memory -v
~~~

Expected: 因 recommendation_memory 模块不存在而失败。

- [ ] **Step 3: 新建 recommendation_memory.py 与数据库表**

实现 RecommendationMemory，构造函数接收 database_url、sessions、tasks，并创建表和索引：

~~~python
connection.execute("""
    CREATE TABLE IF NOT EXISTS session_task_exclusions (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
        task_id TEXT NOT NULL,
        feedback_group TEXT NOT NULL,
        source TEXT NOT NULL CHECK (source IN ('low_rating', 'skipped')),
        created_at TIMESTAMPTZ NOT NULL,
        UNIQUE (session_id, feedback_group)
    )
""")
connection.execute("""
    CREATE INDEX IF NOT EXISTS idx_session_task_exclusions_session
    ON session_task_exclusions(session_id, created_at)
""")
~~~

record_plan_item_exclusion 的查询必须用 plan_id + session_id + item_id 查找计划项，拒绝跨会话计划项；再用 TaskRepository().public_tasks 找到任务。公共任务不存在时用 f"custom:{task_id}"。使用：

~~~sql
INSERT INTO session_task_exclusions
    (id, session_id, task_id, feedback_group, source, created_at)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (session_id, feedback_group) DO NOTHING
RETURNING id, session_id, task_id, feedback_group, source, created_at
~~~

若冲突没有 RETURNING 行，查询并返回已存在行。summary 以行数作为 excluded_group_count，并使用任务库统计这些组当前覆盖的公共任务数作为 excluded_task_count。

- [ ] **Step 4: 运行记忆模块测试确认绿灯**

Run:

~~~powershell
& ".\.venv-debug\Scripts\python.exe" -m unittest tests.test_recommendation_memory -v
~~~

Expected: 同一 session 同组写入仅有一条；不同 session 不共享排除组；统计数字正确。

- [ ] **Step 5: 提交会话级推荐记忆模块**

~~~powershell
git add recommendation_memory.py tests/test_recommendation_memory.py
git commit -m "feat: add session recommendation memory"
~~~

## Task 4: 让推荐与首次生成计划尊重排除组

**Files:**
- Modify: recommendation_module.py:10-85
- Modify: mvp_orchestrator.py:335-450
- Modify: tests/test_recommendation_reasons.py
- Modify: tests/test_mvp_integration.py

**Interfaces:**
- Consumes: RecommendationMemory.list_excluded_groups(session_id)。
- Produces: `recommend_tasks(profile, selected_categories, candidates, limit=10, excluded_feedback_groups=None)` 与响应字段 `recommendation_memory`。

- [ ] **Step 1: 写入推荐过滤与首次生成计划的失败测试**

~~~python
def test_recommendation_excludes_feedback_groups_before_category_coverage():
    result = recommend_tasks(
        profile={"scores": {"松弛疗愈": 1.0}},
        selected_categories=["松弛疗愈"],
        candidates=[
            Task("quiet", "呼吸练习", "松弛疗愈", 10, 0, "home", "solo", feedback_group="recovery_quiet_home"),
            Task("outdoor", "公园慢走", "松弛疗愈", 30, 0, "nearby", "solo", feedback_group="recovery_quiet_outdoor"),
        ],
        excluded_feedback_groups={"recovery_quiet_home"},
    )
    assert [task["id"] for task in result["tasks"]] == ["outdoor"]
    assert result["recommendation_memory"]["excluded_group_count"] == 1
~~~

在 tests/test_mvp_integration.py 的 fake memory 中让 list_excluded_groups 返回一组，断言 MVPOrchestrator.generate_plan 的推荐和计划任务没有该组。

- [ ] **Step 2: 运行推荐与集成测试确认红灯**

Run:

~~~powershell
& ".\.venv-debug\Scripts\python.exe" -m unittest tests.test_recommendation_reasons tests.test_mvp_integration -v
~~~

Expected: recommend_tasks 尚不接受 excluded_feedback_groups 参数。

- [ ] **Step 3: 在推荐与编排层接入会话排除组**

修改签名并在排序前过滤：

~~~python
def recommend_tasks(
    profile: dict[str, Any],
    selected_categories: list[str],
    candidates: list[Task],
    limit: int = 10,
    excluded_feedback_groups: set[str] | None = None,
) -> dict[str, Any]:
    excluded = excluded_feedback_groups or set()
    usable = [
        task for task in candidates
        if task.status == "approved"
        and task.category in selected_category_set
        and task.feedback_group not in excluded
    ]
~~~

返回：

~~~python
"recommendation_memory": {
    "excluded_group_count": len(excluded),
    "excluded_task_count": sum(task.feedback_group in excluded for task in candidates),
}
~~~

为 MVPOrchestrator.__init__ 新增可选 memory=None，使旧 fake 构造保持兼容；_recommend 读取 self.memory.list_excluded_groups(profile["session_id"])，并将集合传入 recommend_tasks。没有 memory 时使用空集合。保留既有 “无法覆盖全部选择分类” 409 行为，并让其 detail 增加 excluded_group_count，帮助前端解释约束不足的原因。

- [ ] **Step 4: 运行推荐与集成测试确认绿灯**

Run:

~~~powershell
& ".\.venv-debug\Scripts\python.exe" -m unittest tests.test_recommendation_reasons tests.test_mvp_integration -v
~~~

Expected: 被排除组不参与分类覆盖和后续排序；没有 memory 的既有集成 fake 仍能运行。

- [ ] **Step 5: 提交推荐链路变更**

~~~powershell
git add recommendation_module.py mvp_orchestrator.py tests/test_recommendation_reasons.py tests/test_mvp_integration.py
git commit -m "feat: filter recommendations by session feedback"
~~~

## Task 5: 将低分和两类跳过操作写入推荐记忆

**Files:**
- Modify: feedback_service.py:19-150
- Modify: execution_service.py:21-190
- Modify: plan_module.py:176-506
- Modify: main.py:132-555
- Modify: tests/test_feedback_service.py
- Modify: tests/test_execution_service.py
- Modify: tests/test_phase_two_api.py

**Interfaces:**
- Consumes: `RecommendationMemory.record_plan_item_exclusion(session_id, plan_id, item_id, source)` 与 `RecommendationMemory.summary(session_id)`。
- Produces: 低分、计划跳过、执行跳过响应中的 recommendation_memory。

- [ ] **Step 1: 写入三种触发方式的失败测试**

~~~python
def test_low_rating_records_an_exclusion_but_high_rating_does_not(self):
    low = self.service.save(self.session_id, self.plan_id, self.item_id, 1, [])
    self.assertEqual(low["recommendation_memory"]["excluded_group_count"], 1)
    high = self.service.save(self.session_id, self.plan_id, self.second_item_id, 5, [])
    self.assertEqual(high["recommendation_memory"]["excluded_group_count"], 1)


def test_execution_skip_records_an_exclusion(self):
    payload = self.execution.execute(self.session_id, self.plan_id, self.item_id, "skip")
    self.assertEqual(payload["recommendation_memory"]["excluded_group_count"], 1)
~~~

为 PlanManagementService.skip_item 编写测试：跳过返回的新计划版本仍为 skipped，同时 memory 有该计划项的组。测试数据的 task_id 选用 PUBLIC_TASKS 中真实任务，不能使用不存在的测试任务 id。

- [ ] **Step 2: 运行反馈、执行、计划测试确认红灯**

Run:

~~~powershell
& ".\.venv-debug\Scripts\python.exe" -m unittest tests.test_feedback_service tests.test_execution_service tests.test_plan_module tests.test_phase_two_api -v
~~~

Expected: 响应没有 recommendation_memory，或构造函数不接收 memory。

- [ ] **Step 3: 在服务层按成功后的顺序写入排除记忆**

为三个服务构造函数增加可选 memory=None：

~~~python
class FeedbackService:
    def __init__(self, database_url: str, sessions: Any, memory: Any | None = None) -> None:
        self.memory = memory
~~~

FeedbackService.save 先完成反馈 upsert；仅当 rating <= 2 and self.memory is not None 时调用：

~~~python
self.memory.record_plan_item_exclusion(session_id, plan_id, item_id, "low_rating")
payload["recommendation_memory"] = self.memory.summary(session_id)
~~~

ExecutionService.execute 仅当 action == "skip" 且状态更新、事件保存和 UPDATE plan_items 已成功后调用 self.memory.record_plan_item_exclusion(session_id, plan_id, item_id, "skipped")。PlanManagementService.skip_item 先调用 _save_version，取得新版本计划后再记录原计划项对应的排除；失败时不返回新版本。

在 main.build_services 中只创建一个 RecommendationMemory(database_url, session_service, TaskRepository())，并把同一实例注入 orchestrator、plan、execution 与 feedback 服务。保持 create_app(...) 的可选依赖参数，测试用 fake 仍可传入。

- [ ] **Step 4: 运行反馈、执行、计划与 API 测试确认绿灯**

Run:

~~~powershell
& ".\.venv-debug\Scripts\python.exe" -m unittest tests.test_feedback_service tests.test_execution_service tests.test_plan_module tests.test_phase_two_api -v
~~~

Expected: 低分与两个跳过入口都会产生会话排除；高分不会；现有执行状态机和版本化计划仍通过。

- [ ] **Step 5: 提交反馈触发链路**

~~~powershell
git add feedback_service.py execution_service.py plan_module.py main.py tests/test_feedback_service.py tests/test_execution_service.py tests/test_plan_module.py tests/test_phase_two_api.py
git commit -m "feat: learn exclusions from ratings and skips"
~~~


## Task 6: 让替换和重排也避开负向偏好

**Files:**
- Modify: plan_module.py:398-530
- Modify: tests/test_plan_replacement_rules.py
- Modify: tests/test_plan_module.py

**Interfaces:**
- Consumes: `PlanManagementService(database_url, sessions, orchestrator, memory=None)`、`memory.list_excluded_groups(session_id)`。
- Produces: replace_item 与 replan 的任务均不属于排除组，并包含 recommendation_memory。

- [ ] **Step 1: 写入替换历史与负向偏好同时生效的失败测试**

~~~python
def test_select_replacement_excludes_history_and_feedback_group():
    tasks = [
        Task("seen", "已替换过", "乐享探索", 20, 0, "home", "solo", feedback_group="explore_game_relax"),
        Task("disliked", "不喜欢的同组", "乐享探索", 20, 0, "home", "solo", feedback_group="explore_food_drink"),
        Task("fresh", "新任务", "乐享探索", 20, 0, "home", "solo", feedback_group="explore_local_browse"),
    ]
    replacement = select_replacement_task(
        candidates=tasks, category="乐享探索", used_task_ids={"seen"},
        budget_limit=20, max_duration=30, outing="home", company="solo",
        excluded_feedback_groups={"explore_food_drink"},
    )
    self.assertEqual(replacement.id, "fresh")
~~~

为 replan 增加 fake memory，断言新计划中的每个公共任务 feedback_group 不在 fake 返回集合；再增加候选全被排除时的断言：抛出 409，消息为 当前偏好与约束下该分类没有未排除任务。

- [ ] **Step 2: 运行计划替换与重排测试确认红灯**

Run:

~~~powershell
& ".\.venv-debug\Scripts\python.exe" -m unittest tests.test_plan_replacement_rules tests.test_plan_module -v
~~~

Expected: select_replacement_task 不接受 excluded_feedback_groups 参数。

- [ ] **Step 3: 统一替换与重排的候选过滤**

给 PlanManagementService 注入 memory=None，新建私有方法：

~~~python
def _excluded_groups(self, session_id: str) -> set[str]:
    return self.memory.list_excluded_groups(session_id) if self.memory is not None else set()
~~~

给 select_replacement_task 增加默认参数 excluded_feedback_groups: set[str] | None = None，在现有分类、任务历史、预算、时长、出行、同行筛选之外增加：

~~~python
and task.feedback_group not in (excluded_feedback_groups or set())
~~~

replace_item 读取当前会话集合并传入；没有候选时抛出上述 409 中文信息。replan 不自行复制候选筛选，而是让已经注入 memory 的 MVPOrchestrator.generate_plan 负责过滤；返回 payload 补充 recommendation_memory。避免在两个地方实现两套推荐过滤。

- [ ] **Step 4: 运行计划替换与重排测试确认绿灯**

Run:

~~~powershell
& ".\.venv-debug\Scripts\python.exe" -m unittest tests.test_plan_replacement_rules tests.test_plan_module -v
~~~

Expected: 连续替换不重复历史任务，也不会出现已低分或跳过组；候选耗尽时得到受控 409。

- [ ] **Step 5: 提交计划变更链路**

~~~powershell
git add plan_module.py tests/test_plan_replacement_rules.py tests/test_plan_module.py
git commit -m "feat: apply feedback memory to plan changes"
~~~

## Task 7: 对齐像素前端、文档与完整回归

**Files:**
- Modify: frontend/app.js:242-760
- Modify: tests/frontend-execution.test.js
- Modify: tests/frontend-api.test.js
- Modify: README.md
- Modify: docs/api.md

**Interfaces:**
- Consumes: 后端响应中的 recommendation_memory。
- Produces: 已避开 N 组不想做的相似任务 状态文本，以及低分/跳过成功提示。

- [ ] **Step 1: 写入前端文案与响应使用的失败测试**

~~~javascript
test('frontend explains feedback exclusions in the plan experience', () => {
  const source = fs.readFileSync(path.join(__dirname, '../frontend/app.js'), 'utf8');
  assert.match(source, /已避开.*组不想做的相似任务/);
  assert.match(source, /之后会避开这类任务/);
  assert.match(source, /任务已跳过，之后会避开相似任务/);
});
~~~

在 frontend-api.test.js 中让 saveFeedback、skipPlanItem、skipExecution mock 返回 recommendation_memory，断言 API 包装不会丢弃该字段。

- [ ] **Step 2: 运行前端测试确认红灯**

Run:

~~~powershell
node --test tests/frontend-api.test.js tests/frontend-execution.test.js
~~~

Expected: 新文案正则无法匹配。

- [ ] **Step 3: 渲染记忆状态并调整提示文案**

在 state.plan 或 state.recommendationMemory 保存每次成功响应的 recommendation_memory。增加一个纯函数，便于测试：

~~~javascript
function exclusionSummary(memory) {
  const groups = Number(memory?.excluded_group_count || 0);
  return groups > 0 ? `已避开 ${groups} 组不想做的相似任务` : '';
}
~~~

在结果页时间线顶部或右侧状态面板渲染该文字，不显示内部组名。保存反馈后：评分 <= 2 显示 反馈已保存，之后会避开这类任务，否则显示 反馈已保存。执行跳过与编辑跳过成功后均显示 任务已跳过，之后会避开相似任务。替换、重排、首次生成计划成功后用返回的 memory 更新状态。

在 README.md 更新任务数为 200、正式问卷数为 105，并说明 1–2 分/跳过在当前会话内影响下一次推荐、替换和重排。docs/api.md 为反馈、两类跳过、生成、替换和重排响应补充 recommendation_memory JSON 示例；说明它不跨会话保存。

- [ ] **Step 4: 运行前端、后端完整回归与静态检查**

Run:

~~~powershell
node --test tests/*.test.js
& ".\.venv-debug\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py" -v
git diff --check
~~~

Expected: Node 测试全部通过；未设置 SESSION_DATABASE_URL 的 live 测试显示 skipped，设置后全部通过；git diff --check 无输出。

- [ ] **Step 5: 使用 PostgreSQL 运行核心链路回归**

先设置本机实际数据库连接串，再执行：

~~~powershell
$env:SESSION_DATABASE_URL="postgresql://postgres:<本机密码>@127.0.0.1:5433/free_time_agent"
& ".\.venv-debug\Scripts\python.exe" -m unittest tests.test_questionnaire_selection tests.test_recommendation_memory tests.test_feedback_service tests.test_phase_two_api -v
~~~

Expected: 新会话、问卷、低分排除、跳过排除和 API 执行链路全部通过；测试清理自己创建的会话。

- [ ] **Step 6: 提交前端、文档与回归测试**

~~~powershell
git add frontend/app.js tests/frontend-api.test.js tests/frontend-execution.test.js README.md docs/api.md
git commit -m "feat: show feedback-aware recommendations"
~~~

## 最终验证清单

- [ ] git status --short --branch 只允许保留用户已有的 backup-before-github-20260814-1/ 未跟踪目录。
- [ ] git log --oneline -7 包含本计划的 7 个独立提交以及规格提交。
- [ ] node --test tests/*.test.js 返回零失败。
- [ ] 已设置 SESSION_DATABASE_URL 时，Python 全量测试返回零失败或仅明确标记为外部环境缺失的 skipped。
- [ ] 手工启动 PostgreSQL、uvicorn main:app --host 127.0.0.1 --port 8000 与前端服务后，完成一遍：创建会话 -> 选偏好 -> 快速问卷 -> 生成计划 -> 完成任务 -> 打 1 分 -> 重排；新计划不包含该 feedback_group。
- [ ] 手工完成一遍执行跳过或编辑跳过 -> 替换任务；替换任务不包含被跳过的 feedback_group。
