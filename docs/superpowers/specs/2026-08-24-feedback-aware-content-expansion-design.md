# 反馈驱动推荐与内容扩充设计

**日期：** 2026-08-24  
**状态：** 已完成设计，等待实现计划评审  
**范围：** 当前 MVP 的任务库、问卷库、反馈记录、推荐、替换与重排链路

## 1. 目标与边界

### 1.1 目标

本次迭代让用户的负向偏好能够在一个会话中立刻生效：

1. 用户为已完成任务给出 `1` 或 `2` 分后，系统不再推荐该任务及同一细分偏好组的任务。
2. 用户主动跳过计划任务后，系统同样不再推荐该任务及同组任务。
3. 排除规则覆盖首次生成计划、替换单个任务和重新生成计划三个入口。
4. 公共任务库从 150 条扩展为 200 条，五个分类各 40 条；内容继续保持可离线运行的通用活动，不依赖地图、商户或实时活动 API。
5. 正式运行的问卷库从现有 50 条扩展为 150 条，五个分类各 30 条；快速问卷只从 `quick` 与 `both` 题目中抽取 5 题，深度问卷只从 `deep` 与 `both` 题目中抽取 30 题。
6. 前端明确告知当前计划已避开的任务数量，使用户知道低评分和跳过操作已产生效果。

### 1.2 非目标

- 不增加账号、登录和跨会话偏好同步。
- 不调用真实地图、商户、活动或大模型 API。
- 不把一个低分任务所在的整个大分类全部屏蔽。
- 不改变四级量表、既有评分归一化方式或任务的时间编辑机制。

## 2. 当前问题

1. `questionnaire_module.py` 是主流程实际使用的问卷题库，而 `task_repository.py` 还保留另一套 50 题题库，形成重复内容来源，容易出现“新增题目未参与问卷”的问题。
2. `FeedbackService.save` 只保存评分，不会将低分转化为后续推荐约束。
3. 跳过计划任务只改变计划项状态，没有形成用户的负向偏好。
4. 推荐、任务替换与重排没有共同的排除条件，因此同一任务或相似任务会再次出现。

## 3. 内容模型

### 3.1 任务库

保留 `task_repository.py` 作为公共任务内容的唯一来源。`Task` 新增不可为空的 `feedback_group: str`：

```text
Task
  id                 任务唯一标识
  title              任务名称
  category           五大活动分类之一
  duration / budget  推荐约束
  outing / company   出行与同行约束
  scenarios          使用场景标签
  feedback_group     细分偏好组
```

每个任务只能属于一个细分偏好组。组按“用户拒绝的是哪一种体验”划分，而不是按五大分类划分。例如：

| 分类 | feedback_group 示例 | 代表任务 |
| --- | --- | --- |
| 活力充电 | `energy_low_impact_home` | 居家拉伸、低冲击有氧、舒缓瑜伽 |
| 松弛疗愈 | `recovery_quiet_home` | 呼吸练习、热饮休息、白噪音闭眼休息 |
| 社交连接 | `social_small_group` | 与熟人散步、小范围聊天、轻量桌游 |
| 乐享探索 | `explore_food_drink` | 喝咖啡、尝试甜品、寻找特色饮品 |
| 自我成长 | `growth_reading_writing` | 阅读、写短笔记、整理知识卡片 |

新增 50 条任务，五个分类各新增 10 条。扩充后总量为 200 条，每类 40 条。每个分类至少包含 4 个细分偏好组，避免一个低分动作把该分类几乎全部清空。

### 3.2 问卷库

`questionnaire_module.py` 成为正式问卷的唯一题目来源；删除或弃用 `task_repository.py` 中不参与主流程的重复 `Question`、`QUESTION_BANK` 与查询入口。主流程只导入 `questionnaire_module.QUESTION_BANK`。

问卷题目保留以下字段：

```text
id, mode, category, dimension, prompt, reverse_scored,
eligible_outing, eligible_company, scenario_tags, priority, status
```

新增 100 题，五个分类各 20 题。扩充后共 150 题、每类 30 题。题目遵守：

- 单题只表达一个偏好；
- 与空闲时间场景相关；
- 反向题不超过总题量的五分之一；
- `quick` 题优先覆盖各分类的核心偏好，`deep` 题提供细分偏好，`both` 用于两种模式的补足；
- 不同前置条件会优先抽取匹配出行、同行、时长、预算、休息倾向和所选分类的题目。

模式是硬过滤，而非仅排序加分：

| 问卷模式 | 可用题目 mode |
| --- | --- |
| 快速版 `quick` | `quick`、`both` |
| 深度版 `deep` | `deep`、`both` |

若严格条件下候选不足，才按既有渐进放宽逻辑补足；补足时仍不得跨越模式边界或返回重复题目。

## 4. 会话内负向偏好存储

新增 PostgreSQL 表 `session_task_exclusions`，由新的 `recommendation_memory.py` 管理。它是会话级推荐记忆，不属于账号画像。

```sql
CREATE TABLE session_task_exclusions (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    task_id TEXT NOT NULL,
    feedback_group TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('low_rating', 'skipped')),
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (session_id, feedback_group)
);
```

规则：

1. 评分为 `1` 或 `2` 时，保存该计划项的 `task_id` 与其 `feedback_group`，来源为 `low_rating`。
2. 执行阶段或计划阶段的“跳过”操作成功后，保存同样的信息，来源为 `skipped`。
3. 同一会话再次排除同一组时使用幂等写入，不产生重复行；第一次记录的 `task_id` 和来源保留，便于追溯。
4. 自定义任务没有公共细分组时使用 `custom:<task_id>`，只屏蔽该自定义任务本身。
5. 清空会话数据、会话过期或删除会话时，外键级联删除这些记录。因此它只对当前会话及该会话随后生成的计划永久有效。

推荐记忆模块向其他模块提供三个明确接口：

```text
record_plan_item_exclusion(session_id, plan_id, item_id, source) -> Exclusion
list_excluded_groups(session_id) -> set[str]
summary(session_id) -> { excluded_group_count, excluded_task_count }
```

它通过 `plans`、`plan_items` 和公共 `Task` 定位任务与细分组；服务层不接收由前端提交的 `feedback_group`，防止前端伪造排除范围。

## 5. 业务链路

### 5.1 低评分

```text
前端提交评分 1 或 2
  -> FeedbackService 校验会话、计划、已完成计划项与评分格式
  -> 写入或更新 task_feedback
  -> RecommendationMemory.record_plan_item_exclusion(..., 'low_rating')
  -> 返回反馈记录与当前避开组数
```

评分为 3、4、5 时只保存反馈，不创建排除记录。若同一计划项先低分后改为 3、4、5，则保留已有会话级排除记录：用户已经明确表达过不想继续收到这类任务，MVP 不自动撤销该偏好。

### 5.2 跳过任务

```text
用户点击跳过
  -> PlanManagementService.skip_item 或 ExecutionService.execute(action='skip')
  -> 原有状态与事件写入成功
  -> RecommendationMemory.record_plan_item_exclusion(..., 'skipped')
  -> 返回计划项状态与当前避开组数
```

排除记录必须在跳过动作写入成功后创建，避免失败请求污染偏好记忆。

### 5.3 首次推荐、替换与重排

所有三个入口都使用同一个 `excluded_feedback_groups` 集合：

```text
读取会话偏好记忆
  -> 获取 excluded_feedback_groups
  -> 过滤 task.feedback_group 不在集合中的候选任务
  -> 继续使用原有分类、预算、时长、出行、同行与画像排序
  -> 生成推荐 / 替换 / 新计划
```

具体接入点：

| 入口 | 变化 |
| --- | --- |
| `mvp_orchestrator.py` 首次生成计划 | 将排除组传给 `recommend_tasks` |
| `recommendation_module.py` | 接收可选 `excluded_feedback_groups` 并在排序前过滤；结果返回排除统计 |
| `plan_module.py` 单项替换 | 候选项同时排除当前计划任务、`replacement_history` 和会话排除组 |
| `plan_module.py` 重排 | 重新获取排除组，并把它应用于新的候选任务集合 |

若排除规则使某一分类暂时无可用任务，系统不恢复被排除任务；返回明确的“当前偏好与约束下该分类没有未排除任务”信息，并保持其他分类可生成。这比重复推荐用户已拒绝的任务更符合产品承诺。

## 6. API 与前端契约

保持现有 API 路径不变，响应在相关对象中增加以下非破坏性字段：

```json
{
  "recommendation_memory": {
    "excluded_group_count": 2,
    "excluded_task_count": 6
  }
}
```

该字段出现在：

- 提交反馈响应；
- 跳过计划项响应；
- 执行阶段跳过响应；
- 新建、替换或重排后的计划响应。

前端在计划页和重排结果页展示简短状态：`已避开 N 组不想做的相似任务`。不显示内部 `feedback_group` 字符串，也不让用户编辑该组名。

前端可继续使用已有反馈评分控件；当用户选 1 或 2 分时，在成功响应后提示“之后会避开这类任务”。跳过成功后使用相同的自然语言提示。页面恢复、刷新与历史计划读取不需要新增本地存储，全部以 PostgreSQL 会话数据为准。

## 7. 错误处理与兼容性

1. 计划项、计划或会话不属于当前会话时返回现有的 404/409 风格错误，不写排除记录。
2. `feedback_group` 缺失的旧公共任务采用一次性迁移默认值 `legacy:<task_id>`，只屏蔽该任务，保证旧计划可读可操作。
3. 数据库初始化使用 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` 和 `CREATE TABLE IF NOT EXISTS`，便于本地已有数据库平滑升级。
4. 题库内容扩容不改变已开始问卷持有的 `question_ids`；已有会话继续答原题，新开始的问卷使用新选择逻辑。
5. 所有过滤发生在服务端，前端仅展示结果；直接调用 API 不能绕过排除规则。

## 8. 测试与验收

### 8.1 单元测试

1. 公共任务总数为 200，五类各 40，所有任务具有有效 `feedback_group`。
2. 正式问卷总数为 150，五类各 30；快速版只返回 `quick/both`，深度版只返回 `deep/both`，并且无重复。
3. 不同前置偏好得到不同的快速问卷组合，且均覆盖所选分类。
4. 评分 1、2 创建排除记录；评分 3、4、5 不创建记录。
5. 跳过计划项和执行跳过都创建排除记录，重复调用不产生重复组。
6. 推荐、替换、重排均不返回已排除组的任务。
7. 在某分类没有未排除任务时返回受控结果，而不是重复旧任务或抛出未处理异常。

### 8.2 API 与前端测试

1. 从创建会话到生成计划的主流程仍可完成。
2. 对已完成任务提交 1 分后重排，返回任务不属于被排除组。
3. 连续替换同一计划项，候选同时避开替换历史和负向偏好组。
4. 前端能显示避开数量及 1–2 分/跳过的提示。
5. PostgreSQL 真实连接下执行现有核心链路测试与新增反馈记忆测试。

## 9. 实施文件边界

| 文件 | 责任 |
| --- | --- |
| `task_repository.py` | 200 条公共任务、`feedback_group` 与任务筛选 |
| `questionnaire_module.py` | 唯一正式问卷库、150 条题目、模式硬过滤与偏好排序 |
| `recommendation_memory.py` | 会话级排除表、记录、读取和统计 |
| `feedback_service.py` | 低分触发排除记忆 |
| `execution_service.py` | 执行阶段跳过触发排除记忆 |
| `plan_module.py` | 计划阶段跳过、替换、重排应用排除记忆 |
| `recommendation_module.py` | 推荐候选的统一排除过滤 |
| `mvp_orchestrator.py` | 首次推荐接入排除组 |
| `main.py` | 依赖装配和响应契约 |
| `frontend/app.js` | 避开数量与用户提示 |
| `tests/` | 内容数量、排除规则、主链路回归 |
| `README.md`、`docs/api.md` | 更新可用数量、行为与接口说明 |

## 10. 成功标准

在同一会话中，用户给某项任务打 1–2 分或跳过它后，无论是重新生成计划还是多次替换任务，系统都不会再提供该任务或同一细分 `feedback_group` 的任务。新的 200 条任务和 150 条正式问卷题均由实际主流程使用，且现有本地 PostgreSQL、后端 API 与像素前端主流程保持可运行。
