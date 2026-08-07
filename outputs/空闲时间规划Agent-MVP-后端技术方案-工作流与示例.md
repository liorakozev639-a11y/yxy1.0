# 空闲时间规划 Agent MVP 后端技术方案

**版本：** v2.0  
**依据：**《空闲时间规划 Agent MVP 产品需求文档》  
**实现原则：** 模块化单体、同步 API、人工审核任务库、规则优先、无 MQ、无异步 Worker。

## 1. 方案概述

### 1.1 MVP 后端目标

后端完成以下闭环：

```text
匿名会话
→ 兴趣和前置条件
→ 5 题或 30 题问卷
→ 用户画像
→ 任务筛选
→ Agent 组合推荐
→ 时间排程
→ 任务执行
→ 计划调整和反馈
```

### 1.2 技术架构

```text
Web 前端
   ↓ 同步 HTTP/JSON
FastAPI 单体服务
   ├── Session Module
   ├── Questionnaire Module
   ├── Profile Module
   ├── Task Repository
   ├── Recommendation Module
   ├── Scheduling Module
   ├── Execution Module
   └── Feedback Module
   ↓
PostgreSQL
```

### 1.3 推荐技术栈

| 层 | 技术 |
|---|---|
| API | Python 3.11+、FastAPI |
| 数据校验 | Pydantic |
| ORM | SQLAlchemy 2.x |
| 数据库 | PostgreSQL |
| 数据迁移 | Alembic |
| 测试 | pytest、httpx |
| 部署 | Docker + 单个 API 服务 |

MVP 不使用 Redis、MQ、Celery、定时 Worker、邮件服务、PDF 服务或实时外部 API。

## 2. 统一代码约定

以下代码是模块核心逻辑的最小示例。实际项目中应把模型、服务和路由分别放入不同文件。

```python
from datetime import datetime, timedelta, timezone
from enum import Enum
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Free Time Agent API")

def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"

def now_utc() -> datetime:
    return datetime.now(timezone.utc)
```

生产环境中，内存字典替换为 PostgreSQL Repository，接口保持不变。

## 3. Session Module：会话模块

### 3.1 精简职责

Session Module 为一次空闲时间规划建立独立的数据边界，负责匿名会话创建、token 校验、流程阶段保存、草稿恢复、有效期控制和本次数据删除。

它不负责推荐任务、计算画像或生成计划，只负责回答：

```text
当前请求属于哪个用户会话？
这个会话目前进行到哪一步？
这个会话能否继续访问自己的数据？
```

### 3.2 保存内容

```text
会话基础信息：session_id、token_hash、stage、version、expires_at
业务草稿：preferences、questionnaire_answers、profile、plan
```

生产环境中，基础信息保存到 `sessions` 表，业务数据分别保存到 `preferences`、`questionnaire_answers`、`profiles` 和 `plans` 表，并通过 `session_id` 关联。

### 3.3 状态阶段

```text
interests
→ preferences
→ questionnaire
→ recommendation
→ planning
→ confirmed
→ executing
```

阶段用于页面恢复和流程校验。用户可以返回修改已完成步骤，但不能跳过必要的前置步骤直接生成计划。

### 3.4 完整同步工作流

#### 创建会话

```text
POST /api/v1/sessions
→ 生成随机 session_id
→ 生成不可预测的 token
→ 计算 token_hash
→ 保存会话记录和有效期
→ 返回 session_id、token、stage
```

#### 访问会话

```text
请求携带 Authorization: Bearer <token>
→ 解析 token
→ 根据 session_id 查询会话
→ 对 token 做哈希
→ 使用安全比较校验哈希
→ 检查 expires_at
→ 检查资源是否属于该 session
→ 返回当前草稿和 stage
```

#### 保存业务数据

```text
提交兴趣或问卷答案
→ 校验 token
→ 校验字段值
→ 写入对应业务数据
→ 更新 stage、updated_at、version
→ 返回保存结果
```

#### 恢复会话

```text
用户刷新或重新进入网页
→ 前端读取临时 session 凭证
→ GET /api/v1/sessions/{session_id}
→ 服务端校验 token 和有效期
→ 返回 stage、preferences、answers、profile、plan
→ 前端恢复对应页面
```

#### 删除本次数据

```text
DELETE /api/v1/sessions/{session_id}/data
→ 校验 token
→ 删除问卷、画像、计划、执行和反馈数据
→ 删除或注销 session
→ 返回删除成功
```

### 3.5 安全和一致性要求

- 客户端持有原始 token，服务端只保存 `token_hash`。
- 使用 `hmac.compare_digest` 做哈希比较。
- token 只通过 HTTPS 传输。
- 所有业务资源查询必须同时校验 `session_id` 和 token。
- session 过期后返回 401，不继续访问旧数据。
- 写操作使用 `version` 做乐观锁，避免多个页面互相覆盖。
- 删除会话数据时，相关业务数据必须在同一事务内删除。

### 3.6 完整运行代码

完整示例文件：

[session_module.py](C:\Users\杨星宇\Documents\Codex\2026-08-01\an-zhu\examples\session_module.py)

安装依赖：

```bash
python -m pip install fastapi uvicorn
```

启动服务：

```bash
python examples/session_module.py
```

服务启动后访问：

```text
http://127.0.0.1:8000/docs
```

示例使用内存 Repository，进程重启后数据会消失；正式环境只需将 `InMemorySessionRepository` 替换为 PostgreSQL Repository，Service 和 API 结构可以保留。

### 3.7 API 示例

创建会话：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/sessions
```

保存前置条件：

```bash
curl -X PUT http://127.0.0.1:8000/api/v1/sessions/{session_id}/preferences \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "categories": ["松弛疗愈", "自我成长"],
    "duration": "half-day",
    "budget": "0-50",
    "outing": "home",
    "company": "solo",
    "city_or_campus": null,
    "rest_only": false
  }'
```

恢复会话：

```bash
curl http://127.0.0.1:8000/api/v1/sessions/{session_id} \
  -H "Authorization: Bearer {token}"
```

### 3.8 验收点

- 无需注册即可创建会话。
- token 不以明文保存。
- 错误 token 无法访问会话。
- 过期会话无法继续访问。
- 刷新页面可以恢复当前 stage 和草稿。
- 不同 session 之间不能读取或修改彼此数据。
- 删除本次数据后，问卷、计划、执行和反馈数据不再可读。

## 4. Questionnaire Module：问卷模块

### 4.1 精简职责

生成快速版或深度版问卷，保存答案、跳过记录和提交状态。

### 4.2 输入和输出

```text
输入：session_id、问卷模式、前置条件
输出：题目列表、答案进度、提交结果
依赖：question_bank、questionnaire_answers
```

### 4.3 同步工作流

```text
选择 quick/deep
→ 查询审核题库
→ 按出行、同行和身份条件过滤
→ 返回 5 题或 30 题
→ 每次回答立即保存
→ 提交后进入 Profile Module
```

### 4.4 最小示例代码

```python
class QuestionnaireStart(BaseModel):
    mode: str = Field(pattern="^(quick|deep)$")

QUESTION_BANK = [
    {"id": "q_energy", "mode": "quick", "text": "我想通过轻度活动恢复状态"},
    {"id": "q_rest", "mode": "quick", "text": "我今天更需要放松和休息"},
    {"id": "q_social", "mode": "quick", "text": "我愿意和别人一起度过空闲时间"},
    {"id": "q_explore", "mode": "quick", "text": "我想尝试一些新鲜的体验"},
    {"id": "q_growth", "mode": "quick", "text": "我希望利用时间学习或提升自己"},
]

answers: dict[tuple[str, str], int] = {}

@app.post("/api/v1/sessions/{session_id}/questionnaire/start")
def start_questionnaire(
    session_id: str,
    body: QuestionnaireStart,
):
    count = 5 if body.mode == "quick" else 30
    questions = QUESTION_BANK[:count]
    return {
        "data": {
            "mode": body.mode,
            "total": count,
            "questions": questions,
            "scale": ["非常同意", "比较同意", "不太同意", "完全不同意"],
        },
        "error": None,
    }

@app.patch("/api/v1/sessions/{session_id}/questionnaire/answers/{question_id}")
def save_answer(session_id: str, question_id: str, value: int):
    if value not in {1, 2, 3, 4}:
        raise HTTPException(status_code=400, detail="答案必须为 1-4")
    answers[(session_id, question_id)] = value
    return {"data": {"saved": True}, "error": None}
```

### 4.5 验收点

- quick 返回 5 题，deep 返回 30 题。
- 只能提交 1-4 的合法答案。
- 支持跳过、修改和恢复。
- 题目来自审核题库，不由模型临时生成。

### 4.6 详细运行过程

#### 开始问卷

```text
POST /questionnaire/start
→ 校验 session
→ 读取 preferences
→ 查询 status=approved 的题目
→ 根据 quick/deep 选择 5/30 题
→ 根据居家/外出、独处/结伴等条件过滤
→ 保存 questionnaire_session
→ 返回题目和量表
```

#### 保存、修改和跳过答案

```text
PATCH /questionnaire/answers/{question_id}
→ 校验题目属于当前问卷
→ 校验 value 必须是 1-4
→ 保存或覆盖答案
→ 返回 saved=true

POST /questionnaire/skip/{question_id}
→ 校验题目属于当前问卷
→ 保存 skipped=true
→ 该题不阻塞提交
```

每次回答都立即保存，用户刷新页面后可以通过进度接口恢复。

#### 恢复问卷

```text
GET /questionnaire/progress
→ 查询当前 questionnaire_session
→ 查询当前 session 的答案
→ 统计已答、已跳过和未答题目
→ 前端定位到第一道未处理题目
```

#### 提交问卷

```text
POST /questionnaire/submit
→ 检查每道题都有答案或 skipped 记录
→ 统计答题数量和跳过数量
→ 标记 submitted=true
→ 生成 Profile Module 的结构化输入
→ 返回 next_stage=profile
```

### 4.7 业务规则

- 题目必须来自人工审核题库，不由模型临时生成。
- 用户可以修改已保存答案，后写入的答案覆盖旧答案。
- 跳过题目保存 `skipped=true`，画像计算时使用中性值。
- 已提交问卷不能继续修改；如需修改，应创建新的问卷版本。
- 题目数量不足时，只能使用同维度审核题补充。
- Questionnaire Module 只负责收集和整理答案，不负责推荐任务或安排时间。

### 4.8 完整运行代码

完整示例文件：

[questionnaire_module.py](C:\Users\杨星宇\Documents\Codex\2026-08-01\an-zhu\examples\questionnaire_module.py)

安装依赖：

```bash
python -m pip install fastapi uvicorn
```

启动服务：

```bash
python examples/questionnaire_module.py
```

打开接口文档：

```text
http://127.0.0.1:8001/docs
```

该示例包含一个本地内存 Session Store，用于独立运行演示。正式环境中应替换为 Session Module 的会话校验，并将题库和答案保存到 PostgreSQL。

创建演示会话：

```bash
curl -X POST http://127.0.0.1:8001/api/v1/demo/sessions
```

开始快速问卷：

```bash
curl -X POST http://127.0.0.1:8001/api/v1/sessions/{session_id}/questionnaire/start \
  -H "Content-Type: application/json" \
  -d '{"mode":"quick"}'
```

保存答案：

```bash
curl -X PATCH http://127.0.0.1:8001/api/v1/sessions/{session_id}/questionnaire/answers/q_rest \
  -H "Content-Type: application/json" \
  -d '{"value":4}'
```

查看进度：

```bash
curl http://127.0.0.1:8001/api/v1/sessions/{session_id}/questionnaire/progress
```

提交问卷：

```bash
curl -X POST http://127.0.0.1:8001/api/v1/sessions/{session_id}/questionnaire/submit
```

## 5. Profile Module：用户画像模块

### 5.1 精简职责

将问卷答案转换为活力、恢复、社交、探索和成长等结构化偏好。

### 5.2 输入和输出

```text
输入：问卷答案、兴趣方向、前置条件
输出：profile scores、constraints、confidence
依赖：questionnaire_answers、preferences
```

### 5.3 同步工作流

```text
读取已提交答案
→ 转换量表分数
→ 处理反向题
→ 计算各维度平均值
→ 合并预算、时间和出行约束
→ 保存画像版本
```

### 5.4 最小示例代码

```python
def build_profile(raw_answers: dict[str, int]) -> dict:
    def score(question_id: str) -> float:
        # 1-4 转成 0-1；题库中的反向题应在这里反转
        value = raw_answers.get(question_id, 2)
        return round((value - 1) / 3, 2)

    return {
        "energy_preference": score("q_energy"),
        "recovery_need": score("q_rest"),
        "social_preference": score("q_social"),
        "exploration_preference": score("q_explore"),
        "growth_preference": score("q_growth"),
        "confidence": min(1.0, len(raw_answers) / 5),
        "rule_version": "rule-v1",
    }
```

### 5.5 验收点

- 相同答案得到相同画像。
- 画像计算不依赖大模型。
- 画像保留规则版本。
- 预算、时长、出行和同行条件作为硬约束保存。

### 5.6 Profile Module 详细实现与运行规则

Profile Module 只负责把已经提交的问卷答案转换为结构化画像，不负责推荐任务、搜索商户或安排时间。MVP 使用确定性的规则计算，保证相同输入得到相同输出。

#### 5.6.1 输入与输出

```text
输入：session_id、Question 列表、Answer 列表、preferences
输出：Profile(session_id、scores、constraints、confidence、rule_version)
依赖：Questionnaire Module 提交结果、Session Module 的 preferences
```

每个答案包含 `question_id`、`value`（1～4 或 `None`）和 `skipped`；每道题包含 `id`、`dimension` 和 `reverse_scored`。

#### 5.6.2 打分标准

```text
1 = 完全不同意
2 = 不太同意
3 = 比较同意
4 = 非常同意
```

处理规则：

1. 普通题直接使用用户选择的 1～4 分。
2. 反向题使用 `5 - value`，例如原始 4 分转换为 1 分。
3. 跳过题使用中性值 `2.5`，避免跳过行为直接拉高或拉低画像。
4. 同一维度先求平均分，再按 `(average - 1) / 3` 转成 0～1。
5. 保留两位小数，并记录 `rule_version`。

#### 5.6.3 同步工作流

```text
Questionnaire Module 校验问卷已提交
→ 读取该 session 的题目和答案
→ 跳过题转换为 2.5
→ 反向题执行 5 - value
→ 按 dimension 聚合分数
→ 计算平均分并标准化为 0～1
→ 计算 confidence
→ 合并 preferences 形成 constraints
→ 保存 Profile 版本
→ 返回画像给 Task Repository 和 Recommendation Module
```

`confidence` 只表示输入完整度，MVP 可按“已处理题数 / 问卷总题数”计算，不代表医学或心理学结论。

#### 5.6.4 模块边界

```text
Task Repository：使用 constraints 做预算、时长、出行和同行方式硬过滤
Recommendation Module：使用 scores 对候选任务排序
Profile Module：只计算和保存画像，不直接决定最终任务
```

#### 5.6.5 完整运行代码

完整示例文件：

[profile_module.py](C:\Users\杨星宇\Documents\Codex\2026-08-01\an-zhu\examples\profile_module.py)

安装依赖并启动：

```bash
python -m pip install fastapi uvicorn
python examples/profile_module.py
```

接口文档：`http://127.0.0.1:8002/docs`。

示例提供 `POST /api/v1/sessions/{session_id}/profile/build`，可直接验证普通题、反向题、跳过题、按维度聚合和 0～1 标准化。

#### 5.6.6 验收点

- 相同题目和答案得到相同画像。
- `value` 只能是 1～4，跳过题的 `value` 可以为空。
- 反向题严格执行 `5 - value`。
- 跳过题按 2.5 处理中性分。
- 每个维度的得分范围为 0～1。
- 画像计算不依赖大模型、MQ 或异步 Worker。
- 画像保留 `rule_version`。
- 预算、时长、出行和同行条件作为硬约束保存。

## 6. Task Repository：任务库模块

### 6.1 精简职责

Task Repository 是推荐链路中的候选任务提供者，负责提供人工审核的公共任务和当前用户的自定义任务。

它只做任务库管理和硬约束过滤，不负责：

- 根据画像分数排序；
- 生成最终计划；
- 调用大模型；
- 查询实时地图、商户、活动或价格。

### 6.2 任务来源

```text
MVP：人工录入或初始化脚本导入
后续：合规 API 适配
不采用：直接爬取互联网
```

### 6.3 输入和输出

```text
输入：session_id、画像 constraints、兴趣方向、任务筛选条件
输出：approved 任务列表
依赖：tasks、custom_tasks
```

其中 `constraints` 主要包含预算、最大时长、出行方式和同行方式。`scores` 由 Profile Module 生成，但不在本模块中参与排序。

### 6.4 同步工作流

```text
接收 session_id 和筛选条件
→ 查询公共 tasks 和当前 session 的 custom_tasks
→ 过滤 status != approved 的任务
→ 过滤预算上限
→ 过滤任务最大时长
→ 过滤居家、就近或全城出行方式
→ 过滤独处、结伴或两者皆可
→ 按用户选择的兴趣方向过滤
→ 返回候选任务 ID 和任务详情
```

出行方式采用逐级兼容规则：`home` 只匹配居家任务，`nearby` 可以匹配居家和就近任务，`city` 可以匹配居家、就近和全城任务，`any` 不限制出行范围。同行方式中，`both` 表示任务既适合独处也适合结伴。

### 6.5 运行原理

用户完成问卷后，Profile Module 将前置条件整理为 `constraints`。Task Repository 收到请求后，将公共任务和当前会话的自定义任务合并为候选集合，再逐项执行硬过滤。所有硬条件都满足的任务才会交给 Recommendation Module。

```text
Profile Module
    ├── scores：用于后续排序
    └── constraints：用于本模块硬过滤
                  ↓
Task Repository
    ├── status 过滤
    ├── 预算过滤
    ├── 时长过滤
    ├── 出行过滤
    ├── 同行过滤
    └── 兴趣方向过滤
                  ↓
Recommendation Module
    └── 根据 scores 排序并生成匹配理由
```

公共任务和自定义任务必须隔离保存。用户新增自定义任务时，只写入 `custom_tasks`，不会修改 `tasks` 中的公共任务。没有城市数据时，查询仍可返回通用居家任务。

### 6.6 完整运行代码

完整示例文件：

`examples/task_repository.py`

运行命令：

```bash
python examples/task_repository.py
```

示例代码包含以下功能：

- `Task`：任务数据结构；
- `TaskRepository.public_tasks`：50 条公共任务，每个分类 10 条；
- `TaskRepository.custom_tasks`：按 `session_id` 隔离的自定义任务集合；
- `add_custom_task()`：新增用户自定义任务；
- `search_tasks()`：执行审核状态、预算、时长、出行、同行、兴趣方向和使用场景过滤；
- `Question` / `QUESTION_BANK`：50 道审核题目，每个分类 10 道；
- `get_questions()`：向 Questionnaire Module 返回指定分类的审核题目；
- `demo()`：创建自定义任务并查询候选任务。

五类活动及题目数量固定如下：

```text
活力充电：10 个活动，10 道题目
松弛疗愈：10 个活动，10 道题目
社交连接：10 个活动，10 道题目
乐享探索：10 个活动，10 道题目
自我成长：10 个活动，10 道题目
总计：50 个活动，50 道题目
```

活动通过 `scenarios` 保存五个重点使用场景标签。这样可以在“工作后精力不足”时优先检索恢复型任务，也可以在“临时改变想法”时使用短时、低预算任务重新组合计划。题目仍由 Questionnaire Module 负责展示、保存答案和提交；任务库文件中的题库用于 MVP 初始化和本地联调，不代表 Task Repository 负责画像计算。

核心查询逻辑如下：

```python
def search_tasks(
    session_id: str,
    budget_limit: int,
    max_duration: int,
    outing: str,
    company: str,
    categories: Optional[list[str]] = None,
) -> list[Task]:
    candidates = public_tasks + custom_tasks.get(session_id, [])
    return [
        task for task in candidates
        if task.status == "approved"
        and task.budget <= budget_limit
        and task.duration <= max_duration
        and matches_outing(task, outing)
        and matches_company(task, company)
        and (not categories or task.category in categories)
    ]
```

完整的 `Task` 定义、过滤函数、参数校验和演示入口以独立文件为准，避免文档代码和实际示例出现两份不同实现。

### 6.7 与相邻模块的边界

```text
Profile Module：计算 scores 和 constraints，不直接选任务
Task Repository：根据 constraints 做硬过滤，不负责排序
Recommendation Module：根据 scores 对候选任务排序并检查方向覆盖
Scheduling Module：把推荐任务放入用户空闲时间
```

### 6.8 验收点

- 只有审核任务参与推荐。
- 用户自定义任务不修改公共任务库。
- 公共任务和自定义任务按数据边界分别保存。
- 不保存未经验证的实时地点和价格。
- 无城市数据时可返回通用居家任务。
- 预算、时长、出行、同行条件全部作为硬约束执行。
- 五个分类各有 10 个活动和 10 道题目，题目使用四级同意量表。
- 五个重点使用场景均有活动标签覆盖。
- 查询结果只返回任务库中的任务 ID 和详情。

## 7. Recommendation Module：推荐模块

### 7.1 精简职责

根据 Profile Module 生成的画像分数和 Task Repository 返回的候选任务，生成覆盖用户兴趣方向的任务组合和匹配理由。

Recommendation Module 的处理顺序是“先硬约束、后偏好排序、再分类覆盖”。预算、时长、出行、同行方式和审核状态由 Task Repository 过滤；本模块只在合格候选任务中进行排序和组合。

### 7.2 Agent 的 MVP 作用

Agent 在 MVP 中是受规则约束的任务编排器，负责：

- 对候选任务排序。
- 组合多个任务。
- 生成匹配理由。
- 给出任务执行顺序。

Agent 不负责联网搜索、真实地点查询或突破硬约束。

### 7.3 同步工作流

```text
读取 profile、constraints 和用户选择的分类
→ 调用 Task Repository 获取 approved 候选任务
→ 建立分类与偏好分数的映射
→ 按偏好分数、时长和预算排序
→ 第一轮优先覆盖每个用户选择的分类
→ 第二轮补充剩余推荐名额
→ 生成任务匹配理由
→ 返回 covered_categories 和 missing_categories
→ 将推荐结果交给 Scheduling Module
```

如果某个分类没有符合硬约束的任务，模块不能虚构任务，而是返回 `missing_categories`。前端可以据此提示用户放宽预算、扩大出行范围或重新选择分类。

### 7.4 完整运行代码

完整示例文件：

`examples/recommendation_module.py`

运行命令：

```bash
python examples/recommendation_module.py
```

代码包含两个入口：

- `recommend_tasks()`：对已筛选候选任务排序、覆盖分类并生成理由；
- `build_recommendation()`：串联 Profile Module 的画像约束、Task Repository 和推荐逻辑。

完整运行代码如下：

```python
from dataclasses import asdict
from typing import Any

from task_repository import CATEGORIES, Task, TaskRepository


def recommend_tasks(
    profile: dict[str, Any],
    selected_categories: list[str],
    candidates: list[Task],
    limit: int = 10,
) -> dict[str, Any]:
    if not selected_categories:
        raise ValueError("至少需要选择一个活动分类")
    if limit <= 0:
        raise ValueError("推荐任务数量必须大于 0")
    if any(category not in CATEGORIES for category in selected_categories):
        raise ValueError("存在不支持的活动分类")

    selected_category_set = set(selected_categories)
    scores = profile.get("scores", {})
    preference_map = {
        category: float(scores.get(category, 0))
        for category in selected_category_set
    }
    usable = [
        task for task in candidates
        if task.status == "approved"
        and task.category in selected_category_set
    ]
    ranked = sorted(
        usable,
        key=lambda task: (
            -preference_map.get(task.category, 0),
            task.duration,
            task.budget,
            task.id,
        ),
    )

    selected = []
    selected_ids = set()
    covered = set()

    for task in ranked:
        if task.category in covered:
            continue
        selected.append(task)
        selected_ids.add(task.id)
        covered.add(task.category)
        if len(selected) >= limit:
            break

    if len(selected) < limit:
        for task in ranked:
            if task.id in selected_ids:
                continue
            selected.append(task)
            selected_ids.add(task.id)
            if len(selected) >= limit:
                break

    reasons = [
        {
            "task_id": task.id,
            "text": (
                f"任务属于{task.category}，当前分类偏好分数为"
                f"{preference_map.get(task.category, 0):.2f}，"
                f"预计需要{task.duration}分钟，预算约为{task.budget}元。"
            ),
        }
        for task in selected
    ]

    return {
        "tasks": [asdict(task) for task in selected],
        "task_ids": [task.id for task in selected],
        "covered_categories": sorted(covered),
        "missing_categories": sorted(selected_category_set - covered),
        "reasons": reasons,
    }


def build_recommendation(
    session_id: str,
    profile: dict[str, Any],
    selected_categories: list[str],
    repository: TaskRepository,
    limit: int = 10,
) -> dict[str, Any]:
    constraints = profile["constraints"]
    candidates = repository.search_tasks(
        session_id=session_id,
        budget_limit=constraints["budget_limit"],
        max_duration=constraints["max_duration"],
        outing=constraints["outing"],
        company=constraints["company"],
        categories=selected_categories,
        scenarios=constraints.get("scenarios"),
    )
    result = recommend_tasks(
        profile,
        selected_categories,
        candidates,
        limit,
    )
    result["candidate_count"] = len(candidates)
    result["constraints"] = constraints
    return result


if __name__ == "__main__":
    repository = TaskRepository()
    profile = {
        "scores": {
            "活力充电": 0.65,
            "松弛疗愈": 0.90,
            "自我成长": 0.70,
        },
        "constraints": {
            "budget_limit": 50,
            "max_duration": 90,
            "outing": "nearby",
            "company": "solo",
            "scenarios": ["工作后精力不足"],
        },
    }
    result = build_recommendation(
        "session_001",
        profile,
        ["松弛疗愈", "活力充电", "自我成长"],
        repository,
        limit=6,
    )
    print(result)
```

独立文件中的完整实现使用 `Task` 数据类，返回任务详情、任务 ID、已覆盖分类、缺失分类、候选任务数量、硬约束和匹配理由。它不会生成任务库之外的任务 ID。

### 7.5 验收点

- 推荐结果不违反硬约束。
- 推荐任务覆盖用户选择的方向，或明确返回缺口。
- 推荐结果只引用任务库中的任务 ID。
- 推荐失败时返回规则结果或可解释的无任务提示。
- 推荐排序不改变 Task Repository 的任务数据。
- 推荐理由能够说明任务分类、偏好分数、时长和预算。

## 8. Scheduling Module：排程模块

### 8.1 职责与模块边界

Scheduling Module 把 Recommendation Module 已经筛选并排序的任务放入用户空闲时间，生成可执行的计划草稿。它负责回答“什么时候做”，不重新决定“做什么”，也不负责记录任务是否完成。

```text
Recommendation Module：决定推荐做什么
→ Scheduling Module：决定任务何时开始、何时结束
→ Execution Module：记录任务是否开始、完成、跳过或超时
```

排程必须使用规则算法执行时间、冲突、密度和休息约束。Agent 可以解释排程理由，但不能绕过这些硬约束，也不能凭空生成任务 ID。

### 8.2 输入与输出

输入：

- `session_id`：计划所属会话。
- `tasks`：Recommendation Module 返回的推荐任务，包含任务 ID、分类、持续时间和匹配分。
- `free_start`、`free_end`：用户本次空闲时间窗口。
- `density`：`light`、`balanced` 或 `full`。
- `locked_items`：已完成任务或用户明确锁定时间的任务。
- `version`、`parent_plan_id`：重新排程时使用的计划版本信息。

输出 `PlanDraft`：

- `plan_id`、`session_id`、`density` 和版本信息。
- 按开始时间排序的任务项与休息块。
- 每个计划项的开始时间、结束时间、状态和锁定状态。
- 因密度限制或时间不足而未放入计划的 `unscheduled_task_ids`。

### 8.3 三档密度规则

| 密度 | 最大任务数 | 任务间缓冲 | 插入休息时机 | 休息时长 |
| --- | ---: | ---: | ---: | ---: |
| `light` | 2 | 20 分钟 | 第 1 个任务后 | 30 分钟 |
| `balanced` | 4 | 15 分钟 | 第 2 个任务后 | 20 分钟 |
| `full` | 6 | 10 分钟 | 第 3 个任务后 | 15 分钟 |

配置代表 MVP 初始规则，后续可以根据计划确认率、任务完成率和用户反馈调整，但接口枚举保持不变。

### 8.4 同步工作流

```text
接收生成计划请求
→ 校验 session_id、空闲时间、密度和任务字段
→ 按匹配分、持续时间和任务 ID 确定稳定顺序
→ 读取并校验已完成任务和用户锁定任务
→ 从空闲窗口中扣除锁定时间和缓冲时间
→ 根据密度计算还能安排的任务数量
→ 使用 first-fit 规则把候选任务放入剩余时间段
→ 在指定任务数量后插入休息块
→ 若休息块无法放入，减少任务或尝试先安排休息
→ 检查所有计划项是否越界或重叠
→ 生成 unscheduled_task_ids
→ 在同一数据库事务中保存 plan 和 plan_items
→ 返回计划草稿
```

该算法是确定性的：相同输入产生相同任务顺序和时间安排。计划项 ID 和计划 ID 使用 UUID，因此每次生成的资源 ID 不同。

### 8.5 排程算法原理

1. **固定区间**：已完成任务和 `locked=True` 的任务不能移动。
2. **计算空档**：从完整空闲窗口中扣除固定区间及任务缓冲，得到多个可用时间段。
3. **稳定排序**：推荐任务按匹配分降序、持续时间升序、任务 ID 升序排列。
4. **首次适配**：依次寻找第一个能容纳任务及后续缓冲的时间段。
5. **强制休息**：每份计划必须有至少一个 `kind="rest"` 的休息块；空间不足时宁可少排任务。
6. **最终校验**：任何越界、重叠、重复任务 ID、非法持续时间或非法分数都会使排程失败。

无法排入计划的任务不会丢失，也不会被伪装成已安排任务，而是通过 `unscheduled_task_ids` 返回给前端。

### 8.6 用户修改开始时间和持续时间

`validate_time_change()` 在保存用户修改前执行三项检查：

1. 持续时间必须大于 0。
2. 新的开始和结束时间必须位于本次空闲窗口内。
3. 新时间不能与其他任务或休息块重叠。

重叠判断公式为：

```python
new_start < existing_end and new_end > existing_start
```

当修改当前计划项时，通过 `ignore_item_id` 排除它原来的时间，避免计划项与自身发生冲突。

### 8.7 重新排程与计划版本

`replan()` 不覆盖旧计划，而是创建新版本：

```text
读取旧计划
→ 保留 status=completed 的任务
→ 保留 locked=True 的任务
→ 排除这些任务 ID，防止重复安排
→ 只重新安排其余候选任务
→ version + 1
→ parent_plan_id 指向旧 plan_id
→ 保存新计划和计划项
```

已完成任务在新版本中保留原计划项 ID、开始时间、结束时间、状态和锁定标记。

### 8.8 建议 API

```text
POST  /api/v1/sessions/{session_id}/plans/draft
PATCH /api/v1/plans/{plan_id}/items/{item_id}
POST  /api/v1/plans/{plan_id}/replan
POST  /api/v1/plans/{plan_id}/confirm
GET   /api/v1/plans/{plan_id}
```

`POST .../plans/draft` 接收空闲窗口、密度和推荐任务 ID；`PATCH .../items/{item_id}` 修改开始时间或持续时间；`replan` 创建新版本；`confirm` 将草稿转为用户确认计划。

### 8.9 PostgreSQL 保存规则

排程计算本身保持为纯同步逻辑，计算成功后由 Repository 在同一事务中保存：

```text
BEGIN
→ INSERT plans
→ INSERT plan_items（任务、休息块和锁定项）
→ 校验写入数量和当前版本
→ COMMIT
```

任何计划项写入失败都必须回滚整个计划，不能留下只有 `plans`、没有完整 `plan_items` 的半成品。重新排程通过 `parent_plan_id` 保留版本链，不直接更新旧版本。

### 8.10 完整运行代码

完整文件：`scheduling_module.py`

运行命令：

```bash
python scheduling_module.py
```

聚焦测试：

```bash
python -m unittest tests.test_scheduling_module -v
```

完整代码如下：

```python
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable


class ScheduleError(ValueError):
    """Raised when a valid schedule cannot be produced."""


@dataclass(frozen=True, slots=True)
class Task:
    id: str
    title: str
    category: str
    duration: int
    score: float


@dataclass(frozen=True, slots=True)
class PlanItem:
    id: str
    task_id: str | None
    title: str
    category: str | None
    start_at: datetime
    end_at: datetime
    kind: str = "task"
    status: str = "pending"
    locked: bool = False


@dataclass(frozen=True, slots=True)
class DensityConfig:
    max_tasks: int
    buffer_minutes: int
    rest_after_tasks: int
    rest_minutes: int


@dataclass(frozen=True, slots=True)
class PlanDraft:
    plan_id: str
    session_id: str
    density: str
    free_start: datetime
    free_end: datetime
    items: tuple[PlanItem, ...]
    unscheduled_task_ids: tuple[str, ...]
    version: int = 1
    parent_plan_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "session_id": self.session_id,
            "density": self.density,
            "free_start": self.free_start.isoformat(),
            "free_end": self.free_end.isoformat(),
            "version": self.version,
            "parent_plan_id": self.parent_plan_id,
            "unscheduled_task_ids": list(self.unscheduled_task_ids),
            "items": [
                {
                    "id": item.id,
                    "task_id": item.task_id,
                    "title": item.title,
                    "category": item.category,
                    "kind": item.kind,
                    "status": item.status,
                    "locked": item.locked,
                    "start_at": item.start_at.isoformat(),
                    "end_at": item.end_at.isoformat(),
                }
                for item in self.items
            ],
        }


DENSITY_CONFIGS = {
    "light": DensityConfig(2, 20, 1, 30),
    "balanced": DensityConfig(4, 15, 2, 20),
    "full": DensityConfig(6, 10, 3, 15),
}


@dataclass(slots=True)
class _FreeSlot:
    cursor: datetime
    end_at: datetime


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _validate_window(free_start: datetime, free_end: datetime) -> None:
    if free_start >= free_end:
        raise ScheduleError("空闲结束时间必须晚于开始时间")
    if (free_start.tzinfo is None) != (free_end.tzinfo is None):
        raise ScheduleError("开始时间和结束时间必须使用相同的时区格式")


def _validate_tasks(tasks: list[Task]) -> None:
    task_ids = [task.id for task in tasks]
    if len(task_ids) != len(set(task_ids)):
        raise ScheduleError("推荐任务中存在重复的任务 ID")
    for task in tasks:
        if not task.id or not task.title or not task.category:
            raise ScheduleError("任务 ID、标题和分类不能为空")
        if task.duration <= 0:
            raise ScheduleError("任务持续时间必须大于 0")
        if not 0 <= task.score <= 1:
            raise ScheduleError("任务匹配分数必须在 0 到 1 之间")


def _validate_locked_items(
    items: list[PlanItem],
    free_start: datetime,
    free_end: datetime,
) -> list[PlanItem]:
    ordered = sorted(items, key=lambda item: (item.start_at, item.end_at, item.id))
    for item in ordered:
        if item.start_at >= item.end_at:
            raise ScheduleError("锁定任务的结束时间必须晚于开始时间")
        if item.start_at < free_start or item.end_at > free_end:
            raise ScheduleError("锁定任务超出可用时间")
    for left, right in zip(ordered, ordered[1:]):
        if left.end_at > right.start_at:
            raise ScheduleError("锁定任务之间存在时间冲突")
    return ordered


def _build_free_slots(
    free_start: datetime,
    free_end: datetime,
    locked_items: list[PlanItem],
    buffer_minutes: int,
) -> list[_FreeSlot]:
    buffer = timedelta(minutes=buffer_minutes)
    cursor = free_start
    slots: list[_FreeSlot] = []
    for item in locked_items:
        gap_end = item.start_at - buffer
        if cursor < gap_end:
            slots.append(_FreeSlot(cursor, gap_end))
        cursor = max(cursor, item.end_at + buffer)
    if cursor < free_end:
        slots.append(_FreeSlot(cursor, free_end))
    return slots


def _copy_slots(slots: list[_FreeSlot]) -> list[_FreeSlot]:
    return [_FreeSlot(slot.cursor, slot.end_at) for slot in slots]


def _place(
    slots: list[_FreeSlot],
    duration_minutes: int,
    following_buffer_minutes: int,
) -> tuple[datetime, datetime] | None:
    duration = timedelta(minutes=duration_minutes)
    following_buffer = timedelta(minutes=following_buffer_minutes)
    for slot in slots:
        start_at = slot.cursor
        end_at = start_at + duration
        if end_at + following_buffer <= slot.end_at:
            slot.cursor = end_at + following_buffer
            return start_at, end_at
    return None


def _make_rest_item(start_at: datetime, end_at: datetime) -> PlanItem:
    return PlanItem(
        id=make_id("rest"),
        task_id=None,
        title="休息与自由调整",
        category="松弛疗愈",
        start_at=start_at,
        end_at=end_at,
        kind="rest",
    )


def _attempt_schedule(
    tasks: list[Task],
    base_slots: list[_FreeSlot],
    config: DensityConfig,
    task_limit: int,
    rest_already_present: bool,
    rest_first: bool,
) -> list[PlanItem] | None:
    slots = _copy_slots(base_slots)
    created: list[PlanItem] = []
    rest_added = rest_already_present

    if rest_first and not rest_added:
        position = _place(slots, config.rest_minutes, 0)
        if position is None:
            return None
        created.append(_make_rest_item(*position))
        rest_added = True

    scheduled_count = 0
    for task in tasks:
        if scheduled_count >= task_limit:
            break
        position = _place(slots, task.duration, config.buffer_minutes)
        if position is None:
            continue
        created.append(
            PlanItem(
                id=make_id("item"),
                task_id=task.id,
                title=task.title,
                category=task.category,
                start_at=position[0],
                end_at=position[1],
            )
        )
        scheduled_count += 1

        if not rest_added and scheduled_count == config.rest_after_tasks:
            rest_position = _place(slots, config.rest_minutes, 0)
            if rest_position is not None:
                created.append(_make_rest_item(*rest_position))
                rest_added = True

    if not rest_added:
        rest_position = _place(slots, config.rest_minutes, 0)
        if rest_position is None:
            return None
        created.append(_make_rest_item(*rest_position))

    return created


def build_schedule(
    session_id: str,
    tasks: Iterable[Task],
    free_start: datetime,
    free_end: datetime,
    density: str = "balanced",
    *,
    locked_items: Iterable[PlanItem] = (),
    version: int = 1,
    parent_plan_id: str | None = None,
) -> PlanDraft:
    if not session_id:
        raise ScheduleError("session_id 不能为空")
    if density not in DENSITY_CONFIGS:
        raise ScheduleError("不支持的计划密度")
    if version <= 0:
        raise ScheduleError("计划版本必须大于 0")
    _validate_window(free_start, free_end)

    task_list = list(tasks)
    _validate_tasks(task_list)
    config = DENSITY_CONFIGS[density]
    locked = _validate_locked_items(list(locked_items), free_start, free_end)
    locked_task_ids = {
        item.task_id for item in locked if item.kind == "task" and item.task_id
    }
    ranked = sorted(
        (task for task in task_list if task.id not in locked_task_ids),
        key=lambda task: (-task.score, task.duration, task.id),
    )

    base_slots = _build_free_slots(
        free_start,
        free_end,
        locked,
        config.buffer_minutes,
    )
    locked_task_count = sum(item.kind == "task" for item in locked)
    maximum_new_tasks = max(0, config.max_tasks - locked_task_count)
    rest_present = any(item.kind == "rest" for item in locked)

    created: list[PlanItem] | None = None
    for task_limit in range(maximum_new_tasks, -1, -1):
        attempts = [
            _attempt_schedule(
                ranked,
                base_slots,
                config,
                task_limit,
                rest_present,
                rest_first,
            )
            for rest_first in (False, True)
        ]
        valid_attempts = [attempt for attempt in attempts if attempt is not None]
        if valid_attempts:
            created = max(
                valid_attempts,
                key=lambda attempt: sum(item.kind == "task" for item in attempt),
            )
            break

    if created is None:
        raise ScheduleError("可用时间不足，无法保留休息块")

    items = sorted(
        [*locked, *created],
        key=lambda item: (item.start_at, item.end_at, item.id),
    )
    for left, right in zip(items, items[1:]):
        if left.end_at > right.start_at:
            raise ScheduleError("生成的计划存在时间冲突")
    if not any(item.kind == "rest" for item in items):
        raise ScheduleError("计划必须包含至少一个休息块")

    scheduled_task_ids = {
        item.task_id for item in items if item.kind == "task" and item.task_id
    }
    unscheduled = tuple(
        task.id
        for task in task_list
        if task.id not in scheduled_task_ids and task.id not in locked_task_ids
    )
    return PlanDraft(
        plan_id=make_id("plan"),
        session_id=session_id,
        density=density,
        free_start=free_start,
        free_end=free_end,
        items=tuple(items),
        unscheduled_task_ids=unscheduled,
        version=version,
        parent_plan_id=parent_plan_id,
    )


def validate_time_change(
    start_at: datetime,
    duration_minutes: int,
    free_start: datetime,
    free_end: datetime,
    existing_items: Iterable[PlanItem],
    *,
    ignore_item_id: str | None = None,
) -> tuple[datetime, datetime]:
    _validate_window(free_start, free_end)
    if duration_minutes <= 0:
        raise ScheduleError("任务持续时间必须大于 0")
    end_at = start_at + timedelta(minutes=duration_minutes)
    if start_at < free_start or end_at > free_end:
        raise ScheduleError("任务超出可用时间")
    for item in existing_items:
        if item.id == ignore_item_id:
            continue
        if start_at < item.end_at and end_at > item.start_at:
            raise ScheduleError(f"任务时间发生冲突: {item.id}")
    return start_at, end_at


def replan(
    previous: PlanDraft,
    tasks: Iterable[Task],
    density: str | None = None,
) -> PlanDraft:
    locked = tuple(
        item
        for item in previous.items
        if item.locked or item.status == "completed"
    )
    return build_schedule(
        session_id=previous.session_id,
        tasks=tasks,
        free_start=previous.free_start,
        free_end=previous.free_end,
        density=density or previous.density,
        locked_items=locked,
        version=previous.version + 1,
        parent_plan_id=previous.plan_id,
    )


def demo() -> None:
    free_start = datetime(2026, 8, 6, 14, 0, tzinfo=timezone.utc)
    tasks = [
        Task("walk", "去公园散步", "活力充电", 40, 0.95),
        Task("coffee", "喝咖啡放松", "松弛疗愈", 30, 0.90),
        Task("read", "安静阅读", "自我成长", 45, 0.85),
        Task("stretch", "居家拉伸", "活力充电", 20, 0.80),
        Task("music", "听一张专辑", "乐享探索", 30, 0.75),
    ]
    draft = build_schedule(
        session_id="sess_demo",
        tasks=tasks,
        free_start=free_start,
        free_end=free_start + timedelta(hours=4),
        density="balanced",
    )
    print(json.dumps(draft.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    demo()
```

### 8.11 验收点

- `light`、`balanced`、`full` 最多分别安排 2、4、6 个任务。
- 所有计划项都位于 `free_start` 和 `free_end` 之间。
- 任务和休息块不重叠，并保留密度要求的缓冲时间。
- 每份计划至少包含一个休息块；时间不足时减少任务而不是删除休息。
- 未安排任务通过 `unscheduled_task_ids` 返回。
- 自定义时间越界或与其他计划项冲突时拒绝保存。
- 已完成任务和用户锁定任务在重排时保持不变。
- 重排生成新版本并记录 `parent_plan_id`。
- 相同任务 ID 不会在同一个计划中重复出现。
- 核心排程逻辑不依赖大模型、消息队列或内存会话仓储。

## 9. Execution Module：执行模块

### 9.1 模块职责与边界

Execution Module 不负责生成任务，也不负责重新排序时间。它接收 Scheduling Module 生成的 `PlanItem`，负责：

1. 记录用户开始、完成和跳过操作。
2. 使用服务端当前时间判断任务是否已经超时。
3. 校验状态转换，防止完成后再次开始或重复完成。
4. 写入 `execution_events`，保留状态变化历史。
5. 在任务未开始、执行超时或主动跳过时返回 `needs_adjustment`，让前端提示用户调整计划。

Scheduling Module 和 Execution Module 的分工如下：

```text
Recommendation Module
    → 提供候选任务
Scheduling Module
    → 生成 start_at、end_at 和 pending 状态的 PlanItem
Execution Module
    → 更新任务状态、记录事件、判断超时
Feedback Module
    → 收集完成后的满意度和原因标签
```

Execution Module 在 MVP 中保持同步运行，不使用 MQ、Redis、Celery、后台 Worker 或大模型。

### 9.2 数据模型

| 对象 | 关键字段 | 作用 |
|---|---|---|
| `PlanItem` | `id`, `title`, `start_at`, `end_at`, `status` | 一条可执行计划任务 |
| `ExecutionEvent` | `item_id`, `event_type`, `from_status`, `to_status`, `occurred_at` | 一次不可变的状态变化记录 |
| `plan_items` | `status`, `start_at`, `end_at` | 保存当前任务状态 |
| `execution_events` | `plan_item_id`, `event_type`, `occurred_at` | 保存执行历史，便于审计和反馈分析 |

任务状态含义：

| 状态 | 含义 |
|---|---|
| `pending` | 计划已生成，用户尚未开始 |
| `active` | 用户已经开始执行 |
| `completed` | 用户在截止时间前完成 |
| `skipped` | 用户主动跳过的原始事件类型；当前状态统一进入 `needs_adjustment` |
| `missed` | `pending` 任务到达结束时间仍未开始的事件类型 |
| `overdue` | `active` 任务超过结束时间仍未完成的事件类型 |
| `needs_adjustment` | 计划需要重新安排，前端应展示调整提示 |

### 9.3 状态流转规则

```text
pending --start--> active --complete--> completed
pending --skip--> needs_adjustment（事件类型 skipped）
active  --skip--> needs_adjustment（事件类型 skipped）
pending --到达 end_at--> needs_adjustment（事件类型 missed）
active  --到达 end_at--> needs_adjustment（事件类型 overdue）
```

以下转换必须拒绝：

- `pending` 不能直接 `complete`。
- `completed` 不能再次 `start`、`complete` 或 `skip`。
- `needs_adjustment` 不能继续执行原任务，必须先经过重新排程或替换。
- `start` 早于 `start_at` 时拒绝，避免用户提前执行尚未到时间的任务。

### 9.4 同步运行工作流

```text
前端点击“开始/完成/跳过”
→ POST 执行接口
→ 服务端读取数据库当前时间
→ SELECT plan_items ... FOR UPDATE
→ 判断当前任务是否已超过 end_at
→ 若超时：写入 missed/overdue 事件并返回 needs_adjustment
→ 若未超时：校验 action 是否允许
→ 更新 plan_items.status
→ 插入 execution_events
→ 同一事务 COMMIT
→ 返回最新任务状态和调整提示
```

超时检查不依赖后台定时任务。用户打开页面、刷新页面或发起执行请求时，都可以触发一次检查。检查函数是幂等的：已经进入 `needs_adjustment` 的任务不会重复添加超时事件。

### 9.5 前后端接口约定

前端可以使用以下同步接口：

```text
POST /api/v1/plan-items/{item_id}/start
POST /api/v1/plan-items/{item_id}/complete
POST /api/v1/plan-items/{item_id}/skip
GET  /api/v1/plan-items/{item_id}
```

成功完成任务的响应：

```json
{
  "data": {
    "item_id": "item_001",
    "status": "completed",
    "needs_adjustment": false
  },
  "error": null
}
```

任务超时的响应：

```json
{
  "data": {
    "item_id": "item_001",
    "status": "needs_adjustment",
    "needs_adjustment": true,
    "event_type": "missed",
    "message": "任务已超时，计划需要调整"
  },
  "error": null
}
```

前端收到 `needs_adjustment: true` 后，展示“计划需要调整”，并提供重新排程、替换任务或暂时放弃三个动作。

### 9.6 PostgreSQL 事务要求

状态更新和事件写入必须处于同一个事务中，避免出现“任务状态已经改变，但事件没有记录”的不一致：

```sql
BEGIN;

SELECT id, status, start_at, end_at
FROM plan_items
WHERE id = 'item_001'
FOR UPDATE;

UPDATE plan_items
SET status = 'completed'
WHERE id = 'item_001';

INSERT INTO execution_events
    (plan_item_id, event_type, occurred_at)
VALUES
    ('item_001', 'completed', NOW());

COMMIT;
```

`FOR UPDATE` 会锁定当前任务行，防止两个并发请求同时修改同一个任务。实际服务层应使用数据库返回的当前行重新判断状态，不能信任前端传来的旧状态或客户端时间。

### 9.7 完整可运行 Python 代码

以下代码与仓库根目录的 `execution_module.py` 逻辑一致，可直接运行：

```python
"""Synchronous execution state machine for scheduled plan items."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone


class ExecutionError(ValueError):
    """Raised when an execution action is invalid or the item is not runnable."""


@dataclass(frozen=True, slots=True)
class ExecutionEvent:
    item_id: str
    event_type: str
    from_status: str
    to_status: str
    occurred_at: datetime


@dataclass(slots=True)
class PlanItem:
    id: str
    title: str
    start_at: datetime
    end_at: datetime
    status: str = "pending"
    events: list[ExecutionEvent] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "start_at": self.start_at.isoformat(),
            "end_at": self.end_at.isoformat(),
            "status": self.status,
            "needs_adjustment": self.status == "needs_adjustment",
            "events": [
                {
                    **asdict(event),
                    "occurred_at": event.occurred_at.isoformat(),
                }
                for event in self.events
            ],
        }


ALLOWED_ACTIONS = {
    "pending": {"start", "skip"},
    "active": {"complete", "skip"},
}


def _validate_item(item: PlanItem) -> None:
    if not item.id or not item.title:
        raise ExecutionError("任务 ID 和标题不能为空")
    if item.start_at >= item.end_at:
        raise ExecutionError("任务结束时间必须晚于开始时间")
    if item.status not in {
        "pending",
        "active",
        "completed",
        "skipped",
        "missed",
        "overdue",
        "needs_adjustment",
    }:
        raise ExecutionError(f"不支持的任务状态: {item.status}")


def _validate_time(item: PlanItem, current: datetime) -> None:
    if (item.start_at.tzinfo is None) != (current.tzinfo is None):
        raise ExecutionError("任务时间和当前时间必须使用相同的时区格式")


def _record_event(
    item: PlanItem,
    event_type: str,
    old_status: str,
    new_status: str,
    current: datetime,
) -> None:
    item.events.append(
        ExecutionEvent(
            item_id=item.id,
            event_type=event_type,
            from_status=old_status,
            to_status=new_status,
            occurred_at=current,
        )
    )


def expire_if_needed(item: PlanItem, current: datetime) -> bool:
    """Mark a pending or active item as needing adjustment after its deadline."""
    _validate_item(item)
    _validate_time(item, current)

    if current < item.end_at:
        return False

    old_status = item.status
    if item.status == "pending":
        item.status = "needs_adjustment"
        _record_event(item, "missed", old_status, item.status, current)
        return True

    if item.status == "active":
        item.status = "needs_adjustment"
        _record_event(item, "overdue", old_status, item.status, current)
        return True

    return False


def execute_action(
    item: PlanItem,
    action: str,
    current: datetime,
) -> PlanItem:
    """Apply ``start``, ``complete`` or ``skip`` to one plan item."""
    _validate_item(item)

    if expire_if_needed(item, current):
        return item

    old_status = item.status
    if action not in ALLOWED_ACTIONS.get(old_status, set()):
        raise ExecutionError(f"不允许从 {old_status} 执行 {action}")

    if action == "start":
        if current < item.start_at:
            raise ExecutionError("任务尚未到开始时间")
        item.status = "active"
        event_type = "started"
    elif action == "complete":
        item.status = "completed"
        event_type = "completed"
    elif action == "skip":
        item.status = "needs_adjustment"
        event_type = "skipped"
    else:
        raise ExecutionError(f"不支持的操作: {action}")

    _record_event(item, event_type, old_status, item.status, current)
    return item


def demo() -> None:
    tz = timezone.utc
    start = datetime(2026, 8, 7, 14, 0, tzinfo=tz)
    end = start + timedelta(minutes=40)

    completed = PlanItem("item_001", "去公园散步", start, end)
    execute_action(completed, "start", start + timedelta(minutes=5))
    execute_action(completed, "complete", start + timedelta(minutes=30))

    missed = PlanItem("item_002", "阅读 30 分钟", start, start + timedelta(minutes=30))
    execute_action(missed, "start", start + timedelta(minutes=35))

    print(json.dumps({
        "completed_flow": completed.to_dict(),
        "missed_flow": missed.to_dict(),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    demo()
```

### 9.8 验收标准

- `pending` 任务在开始时间前不能执行 `start`。
- `pending` 任务超过 `end_at` 未开始时，自动变为 `needs_adjustment`，并记录 `missed` 事件。
- `active` 任务超过 `end_at` 未完成时，自动变为 `needs_adjustment`，并记录 `overdue` 事件。
- 正常执行必须遵守 `pending → active → completed`。
- 完成任务后不能再次开始或完成。
- 跳过任务必须记录 `skipped` 事件并触发计划调整。
- 重复执行超时检查不会重复写入事件。
- 每次状态变化和事件写入在同一个 PostgreSQL 事务中完成。
- 核心逻辑不依赖后台 Worker、消息队列、Redis 或大模型。

## 10. Feedback Module：反馈模块

### 10.1 精简职责

保存任务满意度和可选原因标签，为后续规则优化提供数据。

### 10.2 同步工作流

```text
用户完成任务
→ 提交 1-5 分满意度
→ 可选选择原因标签
→ 校验任务归属
→ 保存 feedback
```

### 10.3 最小示例代码

```python
class FeedbackInput(BaseModel):
    rating: int = Field(ge=1, le=5)
    reason_tags: list[str] = Field(default_factory=list, max_length=5)

feedback_store: list[dict] = []

@app.post("/api/v1/plans/{plan_id}/items/{item_id}/feedback")
def submit_feedback(
    plan_id: str,
    item_id: str,
    body: FeedbackInput,
):
    record = {
        "id": new_id("feedback"),
        "plan_id": plan_id,
        "item_id": item_id,
        "rating": body.rating,
        "reason_tags": body.reason_tags,
        "created_at": now_utc(),
    }
    feedback_store.append(record)
    return {"data": record, "error": None}
```

### 10.4 验收点

- 满意度只能为 1-5。
- 原因标签可以不填写。
- 用户只能提交自己计划中的任务反馈。
- 反馈不改变已确认计划内容。

## 11. 数据库设计

### 11.1 核心表

```text
sessions
preferences
question_bank
questionnaire_answers
profiles
tasks
custom_tasks
plans
plan_items
execution_events
feedback
```

### 11.2 关键关系

```text
sessions 1 - 1 preferences
sessions 1 - N questionnaire_answers
sessions 1 - 1 profiles
sessions 1 - N plans
plans 1 - N plan_items
plan_items 1 - N execution_events
plan_items 1 - N feedback
```

### 11.3 计划版本规则

- 首次生成保存为 `draft`。
- 用户确认后变为 `confirmed`。
- 重排创建新的 `plans` 记录。
- 新计划通过 `parent_plan_id` 关联旧计划。
- 已完成的 `plan_items` 在新版本中保留。

## 12. API 总览

```text
POST   /api/v1/sessions
GET    /api/v1/sessions/{session_id}
DELETE /api/v1/sessions/{session_id}/data
PUT    /api/v1/sessions/{session_id}/preferences

POST   /api/v1/sessions/{session_id}/questionnaire/start
PATCH  /api/v1/sessions/{session_id}/questionnaire/answers/{question_id}
POST   /api/v1/sessions/{session_id}/questionnaire/submit

POST   /api/v1/sessions/{session_id}/recommendations
POST   /api/v1/sessions/{session_id}/plans/draft
GET    /api/v1/plans/{plan_id}
PATCH  /api/v1/plans/{plan_id}/items/{item_id}
POST   /api/v1/plans/{plan_id}/replan
POST   /api/v1/plans/{plan_id}/confirm
POST   /api/v1/plans/{plan_id}/custom-tasks

POST   /api/v1/plans/{plan_id}/items/{item_id}/start
POST   /api/v1/plans/{plan_id}/items/{item_id}/complete
POST   /api/v1/plans/{plan_id}/items/{item_id}/skip
POST   /api/v1/plans/{plan_id}/items/{item_id}/feedback
```

统一返回：

```json
{
  "requestId": "req_xxx",
  "data": {},
  "error": null
}
```

## 13. 事务和错误处理

### 13.1 事务要求

- 创建计划时，`plans` 和 `plan_items` 必须在同一事务中写入。
- 修改任务状态时，状态和 `execution_events` 必须在同一事务中写入。
- 重排时创建新版本，不直接修改旧计划。
- 使用计划版本号阻止旧页面覆盖新数据。

### 13.2 主要错误

| 场景 | 返回 |
|---|---|
| session 无效 | 401 |
| 参数错误 | 400 |
| 资源不属于当前 session | 403 |
| 问卷未完成 | 409 |
| 无符合条件任务 | 200 + 限制说明 |
| 时间冲突 | 409 + 可用时间 |
| 状态转换非法 | 409 + 当前状态 |
| 计划版本冲突 | 409 + 要求刷新 |

## 14. 安全和隐私

- token 使用随机值，数据库保存哈希。
- 每次请求校验 session 与资源归属。
- 日志不记录原始 token、完整问卷答案和精确地址。
- 城市或校园字段按普通文本处理，不获取精确定位。
- 提供删除本次会话数据的接口。
- 限制自定义任务标题、时长和标签数量。
- 对创建会话、提交问卷和任务操作做基础限流。

## 15. 测试要求

### 15.1 单元测试

- 四级量表转换。
- 反向题计算。
- 任务硬约束过滤。
- 兴趣方向覆盖。
- 时间冲突检测。
- 计划密度选择。
- 状态机转换。
- 超时判断。

### 15.2 接口测试

- 创建和恢复 session。
- 提交快速问卷。
- 提交深度问卷。
- 生成推荐。
- 创建和确认计划。
- 修改任务时间。
- 添加自定义任务。
- 开始、完成和跳过任务。
- 重排后保留已完成任务。

### 15.3 核心端到端测试

```text
创建 session
→ 选择方向和条件
→ 完成 5 题问卷
→ 生成推荐
→ 生成计划
→ 修改任务时间
→ 确认计划
→ 开始任务
→ 完成任务
→ 提交反馈
```

## 16. 精简实施顺序

### 阶段一：基础层

- 初始化 FastAPI 项目。
- 配置 PostgreSQL、SQLAlchemy 和 Alembic。
- 建立统一响应和异常处理。
- 完成 session 校验。

### 阶段二：输入层

- 完成 Session Module。
- 完成 preferences 保存。
- 完成 Questionnaire Module。
- 完成答案保存和恢复。

### 阶段三：推荐层

- 导入人工审核任务库。
- 完成 Profile Module。
- 完成 Task Repository。
- 完成规则版 Recommendation Module。

### 阶段四：计划层

- 完成 Scheduling Module。
- 完成三种密度。
- 完成时间调整和自定义任务。
- 完成计划版本。

### 阶段五：执行层

- 完成 Execution Module。
- 完成同步超时判断。
- 完成重新排程和 Feedback Module。

### 阶段六：验证上线

- 执行单元测试、接口测试和端到端测试。
- 在一个校园或城市导入任务库。
- 小范围灰度运行。
- 根据问卷完成率、计划确认率和任务完成率迭代。

## 17. 最终后端工作流

```text
1. Session Module 创建匿名会话
2. 前端提交兴趣方向和前置条件
3. Questionnaire Module 返回 5 题或 30 题
4. 用户答案同步保存到数据库
5. Profile Module 计算结构化画像
6. Task Repository 返回审核任务
7. Recommendation Module 按硬约束和画像排序
8. Agent 组合任务并生成匹配理由
9. Scheduling Module 生成计划草稿
10. 用户修改时间、替换任务或添加自定义任务
11. 服务端校验冲突并保存计划版本
12. 用户确认计划
13. Execution Module 同步记录开始、完成、跳过和超时
14. 任务异常时显示“计划需要调整”
15. 用户选择重排、替换或暂不执行
16. Feedback Module 保存满意度和原因标签
```

## 18. MVP 完成标准

后端达到以下条件即可进入测试：

- 全部核心接口使用同步调用完成。
- 不依赖 MQ、Redis、Worker 或异步任务。
- 用户无需注册即可完成规划。
- 推荐结果遵守时间、预算、出行和同行约束。
- 计划不存在时间冲突。
- 用户可以修改计划和添加自定义任务。
- 任务状态可以正确流转。
- 超时可以在请求时被识别。
- 重排不会覆盖已完成任务。
- 所有核心状态变化都有可追踪记录。
