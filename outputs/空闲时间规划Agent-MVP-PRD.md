# 留白计划 MVP 产品需求文档与调试验收方案

**文档版本：** v2.0
**更新日期：** 2026-09-05
**产品阶段：** 本地可运行 MVP
**目标平台：** 移动端优先网页，当前以本地浏览器调试为主
**代码仓库：** `D:\yxy1.0`
**正式前端目录：** `D:\yxy1.0\frontend`
**后端入口：** `D:\yxy1.0\main.py`
**数据库：** PostgreSQL，项目只使用数据库持久化，不使用内存仓储

---

## 1. 产品概述

### 1.1 产品定位

“留白计划”是一个空闲时间规划 Agent。它面向在校大学生、工作后突然获得休息时间的人，以及想要把零散空闲时间变成可执行安排的用户。

用户不需要提前想好要做什么，只需要告诉系统：

- 今天想偏向哪些休闲方向；
- 当前可用时间有多长；
- 预算、出行范围和同行方式是什么；
- 当前对休息、运动、社交、探索、成长的偏好如何。

系统会根据这些信息生成一组推荐任务，并自动排成一份可以执行、可以调整、可以反馈的计划。

### 1.2 当前 MVP 核心闭环

```text
打开前端网页
→ 自动创建或恢复匿名用户和 Session
→ 选择兴趣方向
→ 填写空闲条件
→ 选择快速版或深度版问卷
→ 自动保存答案
→ 提交问卷
→ 生成偏好画像解释
→ 生成 10 个推荐任务
→ 自动排入时间线
→ 用户调整时间 / 替换 / 跳过 / 加入推荐 / 添加自定义任务
→ 用户确认按此流程执行
→ 开始任务前确认当下精力
→ 开始 / 完成 / 跳过 / 检查截止
→ 提交任务反馈
→ 查看计划复盘
→ 历史偏好影响后续推荐
```

### 1.3 当前产品目标

1. 用户无需注册即可本地完成完整规划流程。
2. 前端、后端、PostgreSQL 可以在本地联通运行。
3. 问卷、偏好、计划、执行事件、反馈均写入 PostgreSQL。
4. 问卷提交后一次性返回 10 个推荐任务。
5. 用户可以对计划进行真实调整，而不是只能查看静态推荐。
6. 用户完成、跳过、低评分、替换任务后，系统能在后续推荐中利用这些信号。
7. 通过 PyCharm 断点、Swagger、前端页面和数据库查询，可以逐步验证每个模块是否符合预期。

---

## 2. 目标用户与使用场景

### 2.1 目标用户

- 在校学生：课余、周末、假期有空，但不知道怎么安排。
- 工作后疲惫用户：想休息，但又不想完全浪费时间。
- 临时获得空闲时间的人：想快速获得一份低决策成本计划。
- 想培养更健康休闲习惯的人：希望系统逐步理解自己的偏好。

### 2.2 典型使用场景

| 场景 | 用户问题 | 产品解决方式 |
|---|---|---|
| 周末不知道做什么 | 我有半天时间，但没有想法 | 根据兴趣和约束生成 10 个候选任务和时间线 |
| 下班后很累 | 想做点事但不想太累 | 通过问卷和当下精力确认推荐更轻松任务 |
| 想独处 | 不想参加强社交活动 | 通过同行偏好过滤高社交压力任务 |
| 任务不合适 | 系统推荐的任务不想做 | 支持换一个、换更轻松、跳过和低评分记忆 |
| 时间不合适 | 推荐时间只是参考 | 用户可以自由修改每个任务的起止时间 |
| 想复盘 | 想知道自己完成了什么 | 计划结束后查看完成、跳过、未完成和感受汇总 |

---

## 3. 当前已实现功能清单

### 3.1 本地运行与健康检查

**用户价值：** 让用户知道当前是后端没启动、数据库没连上，还是前端请求失败。

**已实现能力：**

- 后端健康检查：`GET /health`。
- 数据库健康检查：`GET /api/v1/health/database`。
- 前端初始化时会先检查后端和 PostgreSQL。
- 数据库不可用时，前端显示中文错误提示。

**验收标准：**

- 打开 `http://127.0.0.1:8000/docs` 能看到 Swagger。
- `GET /health` 返回 `data.status = ok`。
- `GET /api/v1/health/database` 返回 `data.status = ok`。
- 前端 `http://127.0.0.1:5173/` 能从“正在恢复你的留白”进入正式流程。

### 3.2 匿名用户与 Session 会话

**用户价值：** 不登录也能使用，并且刷新页面后可以恢复进度。

**已实现能力：**

- 创建匿名用户：`POST /api/v1/users/anonymous`。
- 查询用户历史摘要：`GET /api/v1/users/{user_id}/history/summary`。
- 创建 Session：`POST /api/v1/sessions`。
- 恢复 Session：`GET /api/v1/sessions/{session_id}`。
- 保存偏好：`PUT /api/v1/sessions/{session_id}/preferences`。
- 清空当前 Session 数据：`DELETE /api/v1/sessions/{session_id}/data`。
- 前端使用 `localStorage` 保存 `session_id` 和 `user_id`。

**验收标准：**

- 第一次打开网页会创建新 Session。
- 刷新页面后不会丢失当前问卷或计划。
- 点击重新开始后，旧的本地 Session 会被清理。
- 不需要 Token 或 Authorization 请求头。

### 3.3 兴趣方向与空闲条件

**用户价值：** 在推荐任务前先确定用户的硬约束。

**已实现能力：**

- 五类方向：活力充电、松弛疗愈、社交连接、乐享探索、自我成长。
- 支持选择 1-5 个方向。
- 支持调整方向优先级。
- 支持填写：身份、近期状态、可用时长、预算、城市/校园、出行范围、同行方式、计划密度。
- 保存后进入问卷模式选择。

**验收标准：**

- 不选择方向时无法继续。
- 保存偏好后后端返回 `saved = true`、`stage` 和 `version`。
- 数据库 `sessions.preferences` 字段中能看到保存的 JSON。

### 3.4 Questionnaire 问卷模块

**用户价值：** 用少量问题建立初步偏好画像。

**已实现能力：**

- 快速版：5 道题。
- 深度版：30 道题。
- 题库总量：150 道，五个分类各 30 道。
- 根据前置偏好选择更相关的问题。
- 支持答题、跳过、上一题修改、刷新恢复。
- 每次答题立即保存到 PostgreSQL。
- 提交后锁定问卷，避免重复提交造成结果不一致。

**主要接口：**

- `POST /api/v1/sessions/{session_id}/questionnaire/start`
- `PATCH /api/v1/sessions/{session_id}/questionnaire/answers/{question_id}`
- `POST /api/v1/sessions/{session_id}/questionnaire/skip/{question_id}`
- `GET /api/v1/sessions/{session_id}/questionnaire/progress`
- `POST /api/v1/sessions/{session_id}/questionnaire/submit`

**验收标准：**

- quick 返回 `total = 5`。
- deep 返回 `total = 30`。
- 答题后 `answered_count` 增加。
- 跳过后该题被记录为 `skipped`。
- 所有题处理完成后才能提交问卷。
- 刷新页面后已答题目仍然存在。

### 3.5 Profile 偏好画像解释

**用户价值：** 让用户理解为什么系统会推荐这些任务。

**已实现能力：**

- 根据问卷答案计算结构化画像。
- 输出用户更偏向的休闲方式。
- 输出约束解释卡片。
- 输出建议文案。
- 前端在提交问卷后先展示画像解释页，再生成计划。

**主要接口：**

- `GET /api/v1/sessions/{session_id}/profile/insight`

**验收标准：**

- 问卷提交前调用返回业务冲突。
- 问卷提交后返回 `summary`、`top_dimensions`、`constraint_cards`、`suggestions`。
- 前端第 5 步展示画像解释，而不是直接跳到计划。

### 3.6 Task Repository 任务库

**用户价值：** 推荐结果来自可控的任务库，不虚构真实地点和价格。

**已实现能力：**

- 任务库总量：300 个。
- 五个分类各 60 个任务。
- 每个任务包含：标题、分类、时长、预算、出行方式、同行方式、适用场景、反馈分组。
- 每个任务包含任务轻重分级：轻松度、体力消耗、社交压力、地点依赖。
- 支持用户自定义任务。

**验收标准：**

- 单元测试验证每类任务数量为 60。
- 推荐任务不突破预算、时长、出行和同行约束。
- 前端任务卡片能展示轻松度、体力消耗、社交压力、预算和地点依赖。

### 3.7 Recommendation 推荐模块

**用户价值：** 返回更符合当前状态的任务，而不是普通任务列表。

**已实现能力：**

- 根据硬约束过滤任务。
- 根据画像分数排序。
- 尽量覆盖用户选择的分类。
- 每次返回最多 10 个推荐任务。
- 生成推荐理由、匹配标签、警示文案、匹配分。
- 支持低评分和跳过后的相似任务排除。
- 支持历史偏好影响后续推荐。

**验收标准：**

- `recommendation.recommended_task_count = 10`。
- `recommendation.tasks` 中任务 ID 不重复。
- 前端展示 10 个推荐任务。
- 点击“换一个”后不再返回当前任务和历史出现过的任务。
- 1-2 分或跳过后，当前会话后续推荐避开相似任务组。

### 3.8 Scheduling 排程模块

**用户价值：** 把推荐任务变成有时间顺序的计划。

**已实现能力：**

- 支持三种密度：轻松、平衡、充实。
- 自动插入休息块。
- 避免任务时间重叠。
- 校验空闲时间窗口。
- 校验锁定任务。
- 支持重排时保留已完成任务和锁定任务。

**验收标准：**

- 所有计划项都在 `free_start` 到 `free_end` 之间。
- 计划项之间不重叠。
- 至少保留一个休息块。
- 时间不足时返回未安排任务，而不是强行塞入。

### 3.9 Plan 计划管理模块

**用户价值：** 用户可以主动改计划，而不是被系统强制安排。

**已实现能力：**

- 查询当前计划：`GET /api/v1/sessions/{session_id}/plan`。
- 修改任务时间：`PATCH /api/v1/plans/{plan_id}/items/{item_id}`。
- 换一个任务：`POST /api/v1/plans/{plan_id}/items/{item_id}/replace`。
- 换更轻松任务：`POST /api/v1/plans/{plan_id}/items/{item_id}/replace-easier`。
- 编辑阶段跳过任务：`POST /api/v1/plans/{plan_id}/items/{item_id}/skip`。
- 添加自定义任务：`POST /api/v1/plans/{plan_id}/custom-tasks`。
- 把推荐池任务加入时间线：`POST /api/v1/plans/{plan_id}/recommended-tasks/{task_id}`。
- 确认计划：`POST /api/v1/plans/{plan_id}/confirm`。
- 重新排程：`POST /api/v1/plans/{plan_id}/replan`。
- 计划版本控制：每次修改生成新版本，并要求前端携带 `expected_version`。

**验收标准：**

- 修改时间超出空闲窗口时返回错误。
- 修改时间与其他任务重叠时返回错误。
- 成功修改后 `version` 增加。
- 被替换任务的 `replacement_history` 会记录当前任务和历史任务。
- 点击“加入时间线”成功后，该推荐任务成为正式计划项。

### 3.10 Execution 执行模块

**用户价值：** 让计划进入真实执行，而不是只停留在推荐页。

**已实现能力：**

- 开始任务：`POST /api/v1/plans/{plan_id}/items/{item_id}/execution/start`。
- 开始前精力确认：`POST /api/v1/plans/{plan_id}/items/{item_id}/execution/prepare`。
- 完成任务：`POST /api/v1/plans/{plan_id}/items/{item_id}/execution/complete`。
- 执行中跳过：`POST /api/v1/plans/{plan_id}/items/{item_id}/execution/skip`。
- 检查截止：`POST /api/v1/plans/{plan_id}/items/{item_id}/execution/check-deadline`。
- 查询执行事件：`GET /api/v1/plans/{plan_id}/execution/events`。
- 刷新执行提醒：`POST /api/v1/plans/{plan_id}/execution/refresh`。
- 支持提前开始和提前完成。
- 页面每 30 秒刷新提醒。

**验收标准：**

- pending 任务点击开始后变为 active。
- active 任务点击完成后变为 completed。
- 跳过后变为 needs_adjustment。
- 超过截止仍未完成时可被标记为 needs_adjustment。
- 执行事件表中能查到 started、completed、skipped、missed 或 overdue 事件。

### 3.11 Feedback 反馈模块

**用户价值：** 让系统知道哪些任务不合适，后续减少类似推荐。

**已实现能力：**

- 完成任务后可提交 1-5 分评分。
- 可选择最多 3 个原因标签。
- 同一个任务重复提交会更新原反馈。
- 1-2 分会记录为负向信号。
- 负向信号会影响当前会话后续重新生成计划。

**主要接口：**

- `POST /api/v1/plans/{plan_id}/items/{item_id}/feedback`
- `GET /api/v1/plans/{plan_id}/feedback`

**验收标准：**

- 未完成任务不能提交反馈。
- 评分必须是 1-5。
- 原因标签最多 3 个。
- 保存成功后前端提示“反馈已保存”。

### 3.12 Review 复盘模块

**用户价值：** 让用户看到本次计划执行结果，并形成下一次使用的认知反馈。

**已实现能力：**

- 获取计划复盘：`GET /api/v1/plans/{plan_id}/review`。
- 保存完成感受：`POST /api/v1/plans/{plan_id}/items/{item_id}/reflection`。
- 复盘包含完成数、跳过数、未完成数、感受统计、逐项结果和建议。

**验收标准：**

- 已完成任务可以保存“满意 / 一般 / 不满意”。
- 未完成任务不能保存完成感受。
- 计划结束后复盘状态变为 finished。
- 前端可以从计划页查看本次复盘。

### 3.13 Delivery 网页交付模块

**用户价值：** 当前 MVP 只通过网页展示计划，不做 PDF、邮件或日历写入。

**已实现能力：**

- 生成网页计划交付记录。
- 保存交付 payload。
- 同一 session、plan、channel 使用幂等保存。

**验收标准：**

- 生成计划时返回 `delivery.channel = web`。
- 生成计划时返回 `delivery.status = ready`。
- 数据库中存在对应的 `delivery_jobs` 记录。

### 3.14 像素风正式前端

**用户价值：** 用更有辨识度的像素视觉降低工具感，让产品更像一个轻量休闲规划产品。

**已实现能力：**

- 正式业务前端已经合并像素视觉风格。
- 每个步骤标题旁有像素形象。
- 前端使用原生 HTML/CSS/JS，不依赖 npm。
- 前端入口是 `D:\yxy1.0\frontend\index.html`。
- 本地服务用 Python http server 启动。

**验收标准：**

- 打开 `http://127.0.0.1:5173/` 看到像素风页面。
- 可以完整走完问卷、画像、推荐、计划、执行和反馈流程。
- 控制台没有 `api.xxx is not a function` 这类前端方法缺失错误。

### 3.15 后端模块功能总览

**用户价值：** 后端由多个独立模块共同支撑完整产品链路。该板块用于说明每个模块负责什么、在主流程中什么时候被调用，以及调试时应该重点验证什么。

#### 3.15.1 后端整体工作流

```text
main.py / api/index.py
  -> session_module.py 创建或恢复会话
  -> questionnaire_module.py 生成问卷、保存答案、提交问卷
  -> profile_module.py 生成偏好画像解释
  -> task_repository.py 提供任务库、任务标签、任务轻重分级
  -> recommendation_module.py 根据偏好、历史、限制生成推荐任务
  -> scheduling_module.py 把推荐任务排进用户空闲时间
  -> mvp_orchestrator.py 串联画像、推荐、排程、计划保存、网页交付
  -> plan_module.py 支持换任务、调时间、跳过、加入推荐任务、自定义任务
  -> execution_module.py / execution_service.py 记录任务开始、完成、跳过、超时
  -> feedback_service.py 保存任务反馈
  -> review_service.py 生成计划复盘
  -> user_history_service.py / history_insight_service.py 沉淀历史偏好并生成可视化解释
  -> delivery_module.py 返回网页可展示的计划数据
```

#### 3.15.2 模块职责说明

| 后端模块 | 核心职责 | 当前已实现能力 | 调试重点 |
| --- | --- | --- | --- |
| `main.py` | FastAPI 后端入口 | 注册 Swagger 接口、统一成功/失败响应、装配各服务、处理 CORS 和数据库异常 | 启动后访问 `/docs`、`/health`、`/api/v1/health/database` |
| `api/index.py` | Vercel Serverless 入口 | 在线部署时复用 `main.py` 的应用；启动失败时返回可读错误 | Vercel 500 时看该入口是否暴露启动错误 |
| `session_module.py` | 会话模块 | 创建 session、恢复 session、保存偏好、清空会话数据、维护 stage/version/expires_at | 创建会话后应返回 `session_id`、`stage`、`version` |
| `questionnaire_module.py` | 问卷模块 | 支持 quick/deep 模式、动态选题、保存答案、跳过题目、查看进度、提交问卷 | 问卷题目应根据前置偏好变化，提交后生成答案快照 |
| `profile_module.py` | 偏好画像模块 | 根据问卷和偏好生成画像、解释用户倾向、输出推荐依据 | `/profile/insight` 应返回画像摘要、维度、解释文字 |
| `task_repository.py` | 推荐任务库 | 保存公共任务、分类任务、自定义任务、轻松度/体力/社交/预算/地点依赖等标签 | 搜索任务时应能按分类、限制条件、历史排除过滤 |
| `recommendation_module.py` | 推荐模块 | 根据偏好画像、历史反馈、当前限制给出 10 个推荐任务和推荐理由 | 点击“换一个”不能反复返回当前任务或历史剔除任务 |
| `recommendation_memory.py` | 推荐记忆模块 | 记录当前会话中不喜欢的任务组、被替换任务、低分任务和调整历史 | 被用户替换或低评分的任务组应进入排除记忆 |
| `scheduling_module.py` | 排程模块 | 校验空闲时间、锁定任务、任务间隔、休息块、密度策略、重新排程 | 生成计划时任务时间不能重叠，必须落在空闲时间内 |
| `mvp_orchestrator.py` | 主流程编排模块 | 串联画像、推荐、排程、计划保存和网页交付，形成完整产品工作流 | `/plan/generate` 是主链路调试入口 |
| `plan_module.py` | 计划管理模块 | 编辑任务时间、换任务、换轻松任务、跳过任务、加入推荐任务、自定义任务、确认计划、重新生成计划 | 每次修改应校验 `expected_version`，避免前端旧数据覆盖新数据 |
| `execution_module.py` | 执行规则模块 | 定义任务 pending/active/completed/skipped/missed 等状态流转规则 | 开始、完成、跳过任务时状态必须按规则变化 |
| `execution_service.py` | 执行持久化模块 | 把执行事件写入数据库，刷新超时任务，并同步用户历史 | 完成任务后历史记录和计划项状态都应更新 |
| `feedback_service.py` | 反馈模块 | 保存任务评分、原因、备注，并把低分反馈写入推荐记忆 | 1-2 分任务后续应被当前会话避开 |
| `review_service.py` | 复盘模块 | 汇总完成/跳过/替换任务，保存反思，生成复盘建议 | 计划结束后应能看到本次完成情况和复盘状态 |
| `user_history_service.py` | 用户历史模块 | 创建匿名用户、记录完成/跳过/替换/反馈行为、计算历史偏好权重 | 历史行为应影响后续推荐排序 |
| `history_insight_service.py` | 历史洞察模块 | 输出本周完成任务、近期计划、常跳过类型、偏好学习说明、下次推荐策略 | 历史计划页应能解释“系统学到了什么” |
| `delivery_module.py` | 网页交付模块 | 校验计划并生成网页展示 payload，保存 `delivery_jobs` 记录 | 生成计划接口应返回 `delivery.channel = web` 和可渲染 payload |

#### 3.15.3 主要接口和模块对应关系

| 用户动作 | 后端接口 | 主要模块 |
| --- | --- | --- |
| 打开产品并恢复进度 | `POST /api/v1/sessions`、`GET /api/v1/sessions/{session_id}` | `session_module.py` |
| 选择兴趣和空闲条件 | `PUT /api/v1/sessions/{session_id}/preferences` | `session_module.py` |
| 开始问卷 | `POST /api/v1/sessions/{session_id}/questionnaire/start` | `questionnaire_module.py` |
| 回答/跳过问卷题 | `PATCH /api/v1/sessions/{session_id}/questionnaire/answers/{question_id}`、`POST /api/v1/sessions/{session_id}/questionnaire/skip/{question_id}` | `questionnaire_module.py` |
| 提交问卷 | `POST /api/v1/sessions/{session_id}/questionnaire/submit` | `questionnaire_module.py`、`profile_module.py` |
| 查看偏好画像 | `GET /api/v1/sessions/{session_id}/profile/insight` | `profile_module.py` |
| 生成计划 | `POST /api/v1/sessions/{session_id}/plan/generate` | `mvp_orchestrator.py`、`recommendation_module.py`、`scheduling_module.py`、`delivery_module.py` |
| 查看当前计划 | `GET /api/v1/sessions/{session_id}/plan` | `plan_module.py` |
| 修改任务时间 | `PATCH /api/v1/plans/{plan_id}/items/{item_id}`、`POST /api/v1/plans/{plan_id}/items/{item_id}/adjust` | `plan_module.py`、`scheduling_module.py` |
| 更换任务 | `POST /api/v1/plans/{plan_id}/items/{item_id}/replace`、`POST /api/v1/plans/{plan_id}/items/{item_id}/replace-easier` | `plan_module.py`、`recommendation_module.py`、`recommendation_memory.py` |
| 加入推荐任务 | `POST /api/v1/plans/{plan_id}/recommended-tasks/{task_id}` | `plan_module.py` |
| 开始/完成/跳过任务 | `/execution/start`、`/execution/complete`、`/execution/skip` | `execution_module.py`、`execution_service.py`、`user_history_service.py` |
| 提交任务反馈 | `POST /api/v1/plans/{plan_id}/items/{item_id}/feedback` | `feedback_service.py`、`recommendation_memory.py` |
| 查看历史学习结果 | `GET /api/v1/users/{user_id}/history/insight` | `history_insight_service.py` |
| 查看计划复盘 | `GET /api/v1/plans/{plan_id}/review` | `review_service.py` |

#### 3.15.4 后端验收标准

- 本地后端能通过 `uvicorn main:app --host 127.0.0.1 --port 8000` 启动。
- `/docs` 能正常展示所有接口。
- `/api/v1/health/database` 返回数据库可用。
- 创建会话、保存偏好、开始问卷、提交问卷、生成计划可以连续跑通。
- 生成计划后至少返回 10 个推荐任务，并包含推荐理由和任务标签。
- 任务时间可以被用户手动修改，修改后计划版本号递增。
- 点击“换一个”时不会返回当前任务，也不会在当前会话中反复返回已经被替换掉的任务。
- 用户低评分或跳过的任务类型，会进入当前会话推荐记忆。
- 完成、跳过、替换任务后，历史计划与偏好学习接口能看到对应记录。
- 计划复盘页能展示完成任务、跳过任务、替换任务和建议。

---

## 4. 当前不在 MVP 范围内的功能

以下内容当前不作为本地 MVP 验收阻塞项：

- 登录账号体系。
- 跨设备同步。
- 微信小程序正式版本。
- 正式公网部署。
- 实时地图、商户、营业时间、距离查询。
- 活动预约、购票、支付。
- 日历双向同步。
- 浏览器系统通知。
- 大语言模型实时生成任务。
- PDF、邮件或日历形式交付。

---

## 5. 本地启动要求

### 5.1 数据库启动

PowerShell 执行：

```powershell
& "D:\pgsql18\pgsql\bin\pg_ctl.exe" status `
  -D "D:\pgsql18\data"
```

如果显示没有运行，再执行：

```powershell
& "D:\pgsql18\pgsql\bin\pg_ctl.exe" start `
  -D "D:\pgsql18\data" `
  -l "$env:TEMP\free_time_agent-postgres.log" `
  -o "-p 5433" `
  -w
```

检查数据库：

```powershell
& "D:\pgsql18\pgsql\bin\pg_isready.exe" `
  -h 127.0.0.1 -p 5433 -d free_time_agent
```

预期：返回类似 `127.0.0.1:5433 - accepting connections`。

### 5.2 后端启动

新开 PowerShell：

```powershell
Set-Location "D:\yxy1.0"
$env:SESSION_DATABASE_URL = "postgresql://postgres:你的数据库密码@127.0.0.1:5433/free_time_agent"
& ".\.venv\Scripts\python.exe" -m uvicorn main:app `
  --host 127.0.0.1 `
  --port 8000
```

预期：看到 `Uvicorn running on http://127.0.0.1:8000`。

Swagger 地址：

```text
http://127.0.0.1:8000/docs
```

### 5.3 前端启动

新开 PowerShell：

```powershell
Set-Location "D:\yxy1.0"
& ".\.venv\Scripts\python.exe" -m http.server 5173 `
  --bind 127.0.0.1 `
  --directory frontend
```

前端地址：

```text
http://127.0.0.1:5173/
```

注意：当前前端没有 `package.json`，不要使用 `npm run dev`。

---

## 6. 调试总原则

### 6.1 推荐使用的调试工具

- PyCharm：后端断点逐行调试。
- Swagger：直接调用后端接口。
- 前端网页：验证真实用户流程。
- PowerShell：启动服务和执行自动化脚本。
- pgAdmin 或 psql：查询 PostgreSQL 数据。

### 6.2 PyCharm 后端调试配置

运行配置建议：

| 配置项 | 值 |
|---|---|
| 名称 | MVP Backend Debug |
| 运行类型 | 模块名称 |
| 模块名称 | uvicorn |
| 参数 | main:app --host 127.0.0.1 --port 8000 |
| 解释器 | D:\yxy1.0\.venv\Scripts\python.exe |
| 工作目录 | D:\yxy1.0 |
| 环境变量 | SESSION_DATABASE_URL=postgresql://postgres:你的数据库密码@127.0.0.1:5433/free_time_agent |

点击 Debug 按钮启动后端。然后通过前端或 Swagger 发请求，断点才会被触发。

### 6.3 断点使用方法

- 红点断点表示程序运行到这里会暂停。
- 当前暂停行通常会高亮显示。
- `F8`：执行当前行，不进入函数内部。
- `F7`：进入当前函数内部。
- `Shift + F8`：跳出当前函数。
- `F9`：继续运行到下一个断点。
- Variables 面板可以查看当前变量值。
- Watches 可以手动输入表达式，例如 `session_id`、`body.model_dump()`、`plan["version"]`。

---

## 7. 主流程调试方案

### 7.1 第一步：验证服务是否启动

**前端操作：** 打开 `http://127.0.0.1:5173/`。

**建议断点：**

- `main.py` 的 `health()`。
- `main.py` 的 `database_health()`。
- `frontend/api.js` 的 `getHealth()` 和 `getDatabaseHealth()` 可通过浏览器 DevTools 查看请求。

**预期前端反馈：**

- 如果成功，会进入兴趣方向选择页。
- 如果后端没启动，显示本地后端服务未启动。
- 如果数据库没启动，显示 PostgreSQL 数据库未连接。

**预期后端反馈：**

- `/health` 返回 `status = ok`。
- `/api/v1/health/database` 返回 `status = ok`。

### 7.2 第二步：验证匿名用户和 Session 创建

**前端操作：** 刷新首页，让系统自动恢复或创建会话。

**建议断点：**

- `main.py -> create_anonymous_user()`。
- `user_history_service.py -> ensure_user()`。
- `main.py -> create_session()`。
- `session_module.py -> SessionService.create()`。
- `session_module.py -> PostgresSessionRepository.save()`。

**调试观察：**

- `user_id` 是否为空；为空时会创建匿名用户。
- `session.id` 是否以 `sess_` 开头。
- `session.stage` 初始是否为 `interests` 或当前代码定义的初始阶段。
- `session.version` 是否为 1。

**预期前端反馈：**

- 页面进入“选择兴趣方向”。
- 刷新后不会重新开始，而是恢复到当前进度。

**预期数据库反馈：**

- `sessions` 表中出现新的 session 行。
- 用户历史相关表中出现匿名用户记录。

### 7.3 第三步：验证兴趣方向和前置条件保存

**前端操作：**

1. 选择 1-5 个兴趣方向。
2. 调整方向顺序。
3. 填写时长、预算、出行、同行、城市或校园。
4. 点击“选择问卷”。

**建议断点：**

- `main.py -> save_preferences()`。
- `session_module.py -> SessionService.save_preferences()`。
- `session_module.py -> PostgresSessionRepository.save()`。

**调试观察：**

- `body.model_dump()` 是否包含 categories、duration、budget、outing、company。
- `session.preferences` 是否写入用户选择。
- `session.version` 是否递增。

**预期前端反馈：**

- 成功后进入问卷模式选择页。

**预期后端反馈：**

- 返回 `saved = true`。
- 返回新的 `stage` 和 `version`。

### 7.4 第四步：验证问卷抽题

**前端操作：** 选择快速版或深度版。

**建议断点：**

- `main.py -> start_questionnaire()`。
- `questionnaire_module.py -> QuestionnaireService.start()`。
- `questionnaire_module.py -> build_question_bank()`。
- `questionnaire_module.py -> normalize_selected_categories()`。
- `questionnaire_module.py -> preference_tags()`。

**调试观察：**

- `body.mode` 是 `quick` 还是 `deep`。
- `questionnaire.question_ids` 数量是否正确。
- `quick` 是否返回 5 道题。
- `deep` 是否返回 30 道题。
- 题目是否优先覆盖已选择分类。

**预期前端反馈：**

- 快速版显示 `1 / 5`。
- 深度版显示 `1 / 30`。

**预期数据库反馈：**

- 问卷表中保存了当前 session 的问卷模式和题目 ID。

### 7.5 第五步：验证答题、跳过和恢复

**前端操作：**

1. 选择一个答案。
2. 点击上一题再修改答案。
3. 点击跳过本题。
4. 刷新页面。

**建议断点：**

- `main.py -> save_answer()`。
- `main.py -> skip_question()`。
- `main.py -> get_progress()`。
- `questionnaire_module.py -> QuestionnaireService.save_answer()`。
- `questionnaire_module.py -> QuestionnaireService.skip_question()`。
- `questionnaire_module.py -> QuestionnaireService.progress()`。

**调试观察：**

- `question_id` 是否是当前题目。
- `body.value` 是否在 1-4 之间。
- 修改答案时是否覆盖原答案。
- 跳过时 `skipped` 是否为 true。
- 刷新后 `answers` 是否从数据库恢复。

**预期前端反馈：**

- 选项高亮。
- 进度增加。
- 刷新后仍停留在未完成位置。

**预期后端反馈：**

- progress 返回 `answered_count`、`total`、`answers`。

### 7.6 第六步：验证提交问卷和画像解释页

**前端操作：** 完成所有题后点击“提交问卷”。

**建议断点：**

- `main.py -> submit_questionnaire()`。
- `questionnaire_module.py -> QuestionnaireService.submit()`。
- `main.py -> get_profile_insight()`。
- `mvp_orchestrator.py -> MVPOrchestrator.build_profile_insight()`。
- `mvp_orchestrator.py -> MVPOrchestrator._build_profile()`。
- `profile_module.py -> ProfileService.build()`。
- `profile_module.py -> build_profile_insight()`。

**调试观察：**

- `questionnaire.submitted` 是否变为 true。
- `answers` 是否完整。
- `profile.scores` 是否生成五类分数。
- `insight.summary` 是否是中文解释。

**预期前端反馈：**

- 进入第 5 步画像解释页。
- 显示偏好总结、优势方向、约束卡片和建议。

**预期后端反馈：**

- submit 返回 `submitted = true`。
- insight 返回 `summary`、`top_dimensions`、`constraint_cards`、`suggestions`。

### 7.7 第七步：验证生成 10 个推荐任务和计划

**前端操作：** 在画像解释页点击“生成计划”。

**建议断点：**

- `main.py -> generate_plan()`。
- `mvp_orchestrator.py -> MVPOrchestrator.generate_plan()`。
- `mvp_orchestrator.py -> MVPOrchestrator._recommend()`。
- `task_repository.py -> TaskRepository.search_tasks()`。
- `recommendation_module.py -> recommend_tasks()`。
- `scheduling_module.py -> build_schedule()`。
- `delivery_module.py -> WebDeliveryService.deliver()`。

**调试观察：**

- `constraints` 是否包含预算、时长、出行、同行。
- `candidates` 是否已经按硬约束过滤。
- `result["tasks"]` 是否有 10 个。
- `missing_categories` 是否为空。
- `plan.items` 是否有时间顺序。
- 是否包含休息块。

**预期前端反馈：**

- 进入结果页。
- 显示 10 个推荐任务。
- 部分任务在时间线中，时间不足的显示为待安排。
- 每个任务卡片显示推荐理由和轻重标签。

**预期后端反馈：**

- 返回 `profile`、`recommendation`、`plan`、`delivery`。
- `recommendation.recommended_task_count = 10`。
- `delivery.channel = web`。

### 7.8 第八步：验证计划编辑

**前端操作：**

1. 点击某个任务“调整时间”。
2. 输入新的开始和结束时间。
3. 点击“换一个”。
4. 点击“加入时间线”。
5. 点击“添加自定义任务”。
6. 点击“编辑跳过”。
7. 点击“重新排程”。

**建议断点：**

- `main.py -> edit_plan_item()`。
- `main.py -> replace_plan_item()`。
- `main.py -> add_recommended_task()`。
- `main.py -> add_custom_task()`。
- `main.py -> skip_plan_item()`。
- `main.py -> replan()`。
- `plan_module.py -> PlanManagementService._check_version()`。
- `plan_module.py -> PlanManagementService._ensure_slot()`。
- `plan_module.py -> PlanManagementService._save_version()`。
- `plan_module.py -> build_replaced_item()`。

**调试观察：**

- 每次请求是否带 `expected_version`。
- 成功后 `version` 是否增加。
- 时间冲突时 `_ensure_slot()` 是否抛出错误。
- 替换后 `replacement_history` 是否增加。
- 再次点击“换一个”是否出现不同任务。

**预期前端反馈：**

- 修改成功后卡片时间变化。
- 换一个后标题变化。
- 再次换一个不应返回刚换过的任务。
- 冲突时显示错误提示。

**预期后端反馈：**

- 成功返回新 `plan_id` 或新 `version` 的计划。
- 旧计划状态变为 `superseded`。

### 7.9 第九步：验证按流程执行和当下精力确认

**前端操作：**

1. 点击“按此流程执行”。
2. 点击某个 pending 任务的“开始任务”。
3. 选择精力：精力充足 / 还可以 / 有点累。
4. 如果选择低精力，点击“换个更轻松的”。
5. 如果选择中高精力，点击确认并开始。

**建议断点：**

- `main.py -> confirm_plan()`。
- `main.py -> prepare_execution()`。
- `main.py -> start_execution()`。
- `main.py -> replace_plan_item_easier()`。
- `execution_service.py -> ExecutionService.execute()`。
- `execution_module.py -> execute_action()`。

**调试观察：**

- `energy = low` 时返回 `recommended_action = replace_easier`。
- `energy = high/medium` 时返回 `can_start = true`。
- start 后任务状态是否从 pending 到 active。
- 用户历史是否记录本次行为。

**预期前端反馈：**

- 点击开始后先出现精力确认面板。
- 低精力时提示换成更轻松任务。
- 确认开始后任务显示“进行中”。

**预期后端反馈：**

- prepare 返回 `recommended_action` 和 `can_start`。
- start 返回任务状态和执行事件。

### 7.10 第十步：验证完成、反馈、跳过和截止检查

**前端操作：**

1. 对 active 任务点击“完成任务”。
2. 点击“任务反馈”。
3. 选择 1-5 分和原因标签。
4. 对其他任务点击“跳过”或“检查截止”。

**建议断点：**

- `main.py -> complete_execution()`。
- `main.py -> skip_execution()`。
- `main.py -> check_execution_deadline()`。
- `main.py -> save_feedback()`。
- `feedback_service.py -> FeedbackService.save()`。
- `recommendation_memory.py -> RecommendationMemory.record_feedback()` 或相关记录函数。
- `user_history_service.py -> UserHistoryService.record_action()`。

**调试观察：**

- complete 后状态是否为 completed。
- 反馈评分是否在 1-5。
- 1-2 分是否进入负向记忆。
- skip 是否把任务变为 needs_adjustment。
- check-deadline 重复执行是否保持幂等。

**预期前端反馈：**

- 完成后显示“已完成”。
- 反馈保存后提示成功。
- 跳过或超时后显示“需要调整”。

**预期后端反馈：**

- 执行事件中出现 completed、skipped、missed 或 overdue。
- feedback 查询接口能查到刚才提交的评分。

### 7.11 第十一步：验证复盘

**前端操作：** 点击“查看本次复盘”，对已完成任务选择完成感受并保存。

**建议断点：**

- `main.py -> get_plan_review()`。
- `main.py -> save_reflection()`。
- `review_service.py -> ReviewService.get_review()`。
- `review_service.py -> ReviewService.save_reflection()`。

**调试观察：**

- `review.summary` 是否统计完成、跳过、未完成。
- `sentiment` 是否只能是 satisfied、neutral、dissatisfied。
- 未完成任务保存 reflection 是否返回 409。

**预期前端反馈：**

- 复盘页展示完成、跳过、未完成数量。
- 保存感受后再次进入复盘仍能看到结果。

**预期后端反馈：**

- review 返回 `status`、`summary`、`items`。
- reflection 返回保存后的感受值。

---

## 8. Swagger 接口调试路线

如果不想通过前端，可以在 Swagger 按以下顺序调试：

1. `GET /health`
2. `GET /api/v1/health/database`
3. `POST /api/v1/users/anonymous`
4. `POST /api/v1/sessions`
5. `PUT /api/v1/sessions/{session_id}/preferences`
6. `POST /api/v1/sessions/{session_id}/questionnaire/start`
7. `PATCH /api/v1/sessions/{session_id}/questionnaire/answers/{question_id}`
8. 重复答完所有题，或使用 skip 处理题目
9. `GET /api/v1/sessions/{session_id}/questionnaire/progress`
10. `POST /api/v1/sessions/{session_id}/questionnaire/submit`
11. `GET /api/v1/sessions/{session_id}/profile/insight`
12. `POST /api/v1/sessions/{session_id}/plan/generate`
13. `GET /api/v1/sessions/{session_id}/plan`
14. `PATCH /api/v1/plans/{plan_id}/items/{item_id}`
15. `POST /api/v1/plans/{plan_id}/items/{item_id}/replace`
16. `POST /api/v1/plans/{plan_id}/confirm`
17. `POST /api/v1/plans/{plan_id}/items/{item_id}/execution/prepare`
18. `POST /api/v1/plans/{plan_id}/items/{item_id}/execution/start`
19. `POST /api/v1/plans/{plan_id}/items/{item_id}/execution/complete`
20. `POST /api/v1/plans/{plan_id}/items/{item_id}/feedback`
21. `GET /api/v1/plans/{plan_id}/review`

---

## 9. 数据库验证语句

先确认自己连接的是 `free_time_agent` 数据库，再查询。

### 9.1 查询所有表

```sql
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```

### 9.2 查询最近创建的 Session

```sql
SELECT id, stage, version, preferences, created_at, updated_at, expires_at
FROM sessions
ORDER BY created_at DESC
LIMIT 10;
```

### 9.3 查询某个 Session 的问卷

```sql
SELECT session_id, mode, question_ids, submitted, created_at, updated_at
FROM questionnaire_sessions
WHERE session_id = '你的session_id';
```

### 9.4 查询某个 Session 的答案

```sql
SELECT session_id, question_id, value, skipped, answered_at
FROM questionnaire_answers
WHERE session_id = '你的session_id'
ORDER BY answered_at;
```

### 9.5 查询画像

```sql
SELECT session_id, profile_version, scores, constraints, confidence, rule_version, created_at
FROM profiles
WHERE session_id = '你的session_id'
ORDER BY profile_version DESC;
```

### 9.6 查询计划

```sql
SELECT id, session_id, density, free_start, free_end, version, status, parent_plan_id
FROM plans
WHERE session_id = '你的session_id'
ORDER BY version DESC;
```

### 9.7 查询计划项

```sql
SELECT id, plan_id, task_id, title, category, start_at, end_at, kind, status, locked, replacement_history
FROM plan_items
WHERE plan_id = '你的plan_id'
ORDER BY start_at, end_at;
```

### 9.8 查询执行事件

```sql
SELECT id, session_id, plan_id, item_id, event_type, occurred_at, metadata_json
FROM execution_events
WHERE plan_id = '你的plan_id'
ORDER BY occurred_at;
```

### 9.9 查询反馈

```sql
SELECT id, session_id, plan_id, item_id, rating, reasons_json, created_at, updated_at
FROM task_feedback
WHERE plan_id = '你的plan_id'
ORDER BY updated_at DESC;
```

### 9.10 查询网页交付记录

```sql
SELECT id, session_id, plan_id, channel, status, payload_json, created_at
FROM delivery_jobs
WHERE session_id = '你的session_id'
ORDER BY created_at DESC;
```

---

## 10. 自动化测试方案

### 10.1 Python 单元测试

```powershell
Set-Location "D:\yxy1.0"
$env:SESSION_DATABASE_URL = "postgresql://postgres:你的数据库密码@127.0.0.1:5433/free_time_agent"
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py" -v
```

**预期：** Python 测试全部通过。

### 10.2 前端 Node 测试

```powershell
Set-Location "D:\yxy1.0"
node --test tests/*.test.js
```

**预期：** 前端 API、流程、视觉关键结构测试全部通过。

### 10.3 核心链路脚本

需要后端已启动：

```powershell
Set-Location "D:\yxy1.0"
.\tests\live_core_flow.ps1
```

**预期输出包含：**

- `session_id = sess_...`
- `questionnaire_total = 5`
- `submitted = true`
- `profile_rule = profile-rule-v1`
- `plan_id = plan_...`
- `review_status`
- `reflection = satisfied`

---

## 11. 调试验收总表

| 模块 | 前端验证 | Swagger 验证 | 数据库验证 | 通过标准 |
|---|---|---|---|---|
| Health | 打开网页能进入流程 | `/health`、数据库 health | 无需查库 | 两个 status 都是 ok |
| Session | 刷新恢复进度 | 创建/恢复 session | `sessions` | session 存在且 preferences 可保存 |
| Questionnaire | 5题/30题答题 | start、answer、progress、submit | 问卷表、答案表 | 题数正确，答案可恢复 |
| Profile | 展示画像解释页 | profile insight | `profiles` | summary 和 top dimensions 存在 |
| Recommendation | 展示 10 个任务 | plan generate | 任务库测试 | 10 个任务且不重复 |
| Scheduling | 有时间线和休息块 | plan generate/get | `plans`、`plan_items` | 不重叠，不越界 |
| Plan Edit | 调整、替换、加入、跳过 | plan item 系列接口 | `replacement_history` | 版本递增，替换不重复 |
| Execution | 开始、完成、跳过 | execution 系列接口 | `execution_events` | 状态正确变化 |
| Feedback | 任务反馈保存 | feedback 接口 | `task_feedback` | 评分和原因保存 |
| Review | 查看复盘和保存感受 | review/reflection | 复盘相关数据 | summary 和 sentiment 正确 |
| Delivery | 计划可网页展示 | generate 返回 delivery | `delivery_jobs` | channel=web，status=ready |

---

## 12. 常见问题定位

### 12.1 前端一直显示 Failed to fetch

优先检查：

1. 后端是否启动在 8000。
2. 数据库是否启动在 5433。
3. `SESSION_DATABASE_URL` 密码是否正确。
4. 前端是否用 `http://127.0.0.1:5173/` 打开。

### 12.2 Swagger 无法访问

说明后端没有运行或端口不是 8000。重新启动后端，并确认没有 8000 端口占用。

### 12.3 后端提示 Password 认证失败

说明 `SESSION_DATABASE_URL` 中的 PostgreSQL 密码不正确。把 `<数据库密码>` 替换成真实密码，不要带尖括号。

### 12.4 前端 npm run dev 报 package.json 不存在

这是正常的。当前前端是静态前端，用 Python http server 启动，不用 npm。

### 12.5 点击换一个仍然看起来一样

检查：

1. 浏览器是否刷新到了最新 `frontend` 静态文件。
2. 后端是否已重启。
3. `plan_items.replacement_history` 是否在增加。
4. 前端是否显示新的任务标题。

---

## 13. MVP 成功定义

当以下条件都满足时，当前 MVP 可以认为达到本地验收标准：

1. PostgreSQL、后端、前端均可本地启动。
2. 用户从前端可以完整完成一次规划。
3. 问卷答案、画像、计划、计划项、执行事件和反馈都能在数据库中查到。
4. 问卷提交后显示画像解释页。
5. 系统一次性返回 10 个推荐任务。
6. 用户可以修改任务时间、替换任务、加入推荐任务、跳过任务和添加自定义任务。
7. 用户可以确认计划、开始任务、完成任务、提交反馈和查看复盘。
8. 低评分、跳过和替换历史会影响后续推荐。
9. 自动化测试和核心链路脚本能够通过。
