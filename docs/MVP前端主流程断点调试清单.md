# MVP 前端主流程断点调试清单

这份清单用于在 PyCharm 中逐步验证当前前端已经接入的主流程：

```text
创建 Session
-> 保存偏好
-> 启动问卷
-> 保存或跳过答案
-> 提交问卷
-> 构建画像
-> 筛选并推荐任务
-> 生成时间计划
-> 保存 PostgreSQL
-> 生成网页展示数据
-> 前端展示结果
```

当前不验证 Execution Module、Feedback Module、PDF、邮件、日历和实时地图/商户接口，因为它们尚未接入 `main.py` 主流程。

> 行号以当前仓库版本为参考。代码变化后优先通过函数名定位，不要只依赖行号。

---

## 1. 本次调试记录

开始前填写：

| 项目 | 记录值 |
| --- | --- |
| 调试日期 |  |
| Git 提交 |  |
| Session ID |  |
| 问卷模式 | `quick` / `deep` |
| 第一题 Question ID |  |
| Plan ID |  |
| PostgreSQL 端口 | `5433` |
| 后端地址 | `http://127.0.0.1:8000` |
| 前端地址 | `http://127.0.0.1:5173` |

查看当前提交：

```powershell
Set-Location "D:\yxy1.0"
git log -1 --oneline
```

---

## 2. 调试前准备

### 2.1 检查 PostgreSQL

```powershell
& "D:\pgsql18\pgsql\bin\pg_ctl.exe" status `
  -D "D:\pgsql18\data"

& "D:\pgsql18\pgsql\bin\pg_isready.exe" `
  -h 127.0.0.1 -p 5433 -d free_time_agent
```

通过标准：输出包含 `accepting connections`。

### 2.2 避免两个后端占用 8000

前端固定请求 `127.0.0.1:8000`。用 PyCharm 调试前，确认没有其他后端占用该端口：

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
```

如果存在旧的 Uvicorn 进程，先确认它确实是本项目后端，再在原终端按 `Ctrl+C` 停止。不要直接结束来源不明的进程。

### 2.3 PyCharm Debug Configuration

打开：

```text
Run -> Edit Configurations -> + -> Python
```

配置如下：

| 配置项 | 值 |
| --- | --- |
| Name | `MVP Backend Debug` |
| Run kind | `Module name` |
| Module name | `uvicorn` |
| Parameters | `main:app --host 127.0.0.1 --port 8000` |
| Interpreter | `D:\yxy1.0\.venv\Scripts\python.exe` |
| Working directory | `D:\yxy1.0` |
| Environment variables | `SESSION_DATABASE_URL=postgresql://postgres:<password>@127.0.0.1:5433/free_time_agent` |

不要添加 `--reload`。重载模式会产生额外进程，断点可能无法命中。

点击 Debug 后，控制台应显示：

```text
Application startup complete.
Uvicorn running on http://127.0.0.1:8000
```

### 2.4 启动前端

另开 PowerShell：

```powershell
Set-Location "D:\yxy1.0"
.\.venv\Scripts\python.exe -m http.server 5173 `
  --bind 127.0.0.1 `
  --directory frontend
```

打开 `http://127.0.0.1:5173/`。

---

## 3. 断点操作规则

### 3.1 一次只启用一组断点

推荐做法：

1. 给当前阶段列出的函数加断点。
2. 在前端执行该阶段操作。
3. 按顺序检查变量。
4. 记录结果。
5. 按 `F9` 完成本次请求。
6. 禁用本组断点，再进入下一阶段。

如果一次添加所有断点，一个答题请求会暂停很多次，很难判断自己正在验证哪个功能。

### 3.2 常用按键

| 操作 | 快捷键 | 用途 |
| --- | --- | --- |
| Resume | `F9` | 继续到下一个断点 |
| Step Over | `F8` | 执行当前行，不进入函数 |
| Step Into | `F7` | 进入当前行调用的函数 |
| Smart Step Into | `Shift+F7` | 一行多个调用时选择进入哪个 |
| Step Out | `Shift+F8` | 返回调用当前函数的位置 |
| Evaluate Expression | `Alt+F8` | 临时查看表达式值 |

笔记本电脑可能需要按 `Fn+F8`。快捷键无效时直接点击 Debug 工具栏图标。

### 3.3 Variables 的使用原则

可以查看：

```python
session_id
body
session.preferences
questionnaire.question_ids
len(answers)
profile.scores
constraints
len(candidates)
recommendation["missing_categories"]
plan.to_dict()
delivery.to_dict()
```

不要在 Evaluate Expression 中执行以下写操作：

```python
self.repository.save(...)
self.plans.save(plan)
self.delivery.deliver(...)
```

否则会绕过正常流程重复写数据库。

### 3.4 最少断点总表

第一次调试先标记下面 12 个入口断点。需要深入某个阶段时，再添加该阶段列出的 Service、Repository 和算法断点。

| 编号 | 文件与函数 | 当前参考行 | 触发动作 |
| ---: | --- | ---: | --- |
| 1 | `main.py -> create_session()` | 188 | 首次打开或重新开始 |
| 2 | `main.py -> get_session()` | 192 | 刷新页面 |
| 3 | `main.py -> save_preferences()` | 196 | 保存前置条件 |
| 4 | `main.py -> start_questionnaire()` | 220 | 选择快速版/深度版 |
| 5 | `main.py -> save_answer()` | 229 | 点击答案 |
| 6 | `main.py -> skip_question()` | 245 | 跳过题目 |
| 7 | `main.py -> get_progress()` | 251 | 答题中刷新页面 |
| 8 | `main.py -> submit_questionnaire()` | 255 | 提交问卷 |
| 9 | `main.py -> generate_plan()` | 259 | 提交后自动生成计划 |
| 10 | `MVPOrchestrator.generate_plan()` | 336 | 跟踪画像到交付完整链路 |
| 11 | `main.py -> get_plan()` | 275 | Swagger 查询计划 |
| 12 | `main.py -> clear_session_data()` | 214 | 点击重新开始 |

答题时 `save_answer()` 会命中很多次。记录第一题 ID 后，可以右键断点设置 Condition：

```python
question_id == "<question_id>"
```

这样只在指定题目暂停，其他题目正常提交。

---

## 4. 阶段一：创建 Session

### 前端操作

清除旧测试会话后刷新前端，或首次打开前端页面。`frontend/app.js` 的 `initialize()` 会调用 `createFreshSession()`。

### HTTP 接口

```text
POST /api/v1/sessions
```

### 断点顺序

1. `main.py -> create_session()`，当前约第 188 行。
2. `session_module.py -> SessionService.create()`，当前约第 161 行。
3. `session_module.py -> PostgresSessionRepository.save()`，当前约第 90 行。

### 操作方法

1. 在 `main.py` 路由的 `return success(...)` 设置断点。
2. 刷新前端，程序应在路由暂停。
3. 按 `F7` 进入 `SessionService.create()`。
4. 用 `F8` 执行到 `Session(...)` 创建完成。
5. 检查 `session`。
6. 再按 `F7` 进入 Repository 的 `save()`。

### 关键变量

| 变量 | 预期 |
| --- | --- |
| `session.id` | 以 `sess_` 开头 |
| `session.stage` | `interests` |
| `session.version` | `1` |
| `session.preferences` | `{}` |
| `session.expires_at` | 当前时间约 24 小时后 |

### 前端预期

- 显示欢迎页或活动分类选择页。
- `frontend/api.js -> createSession()` 把 `session_id` 保存到键 `free_time_agent_session_id`。
- 页面不显示错误横幅。

### 后端预期

- HTTP 状态码：`201`。
- `data.session_id`、`data.stage`、`data.version`、`data.expires_at` 有值。
- 不返回 Token，也不需要 Authorization 请求头。

### 数据库验证

```sql
SELECT id, stage, version, preferences, expires_at
FROM sessions
WHERE id = '<session_id>';
```

### 通过标准

- [ ] 断点依次进入 Route、Service、Repository。
- [ ] 数据库存在一行相同 `session_id`。
- [ ] 前端进入欢迎或兴趣选择页面。

---

## 5. 阶段二：恢复 Session

### 前端操作

在 Session 已创建的情况下刷新页面。

### HTTP 接口

```text
GET /api/v1/sessions/{session_id}
```

### 断点顺序

1. `main.py -> get_session()`，当前约第 192 行。
2. `session_module.py -> SessionService.restore()`，当前约第 195 行。
3. `session_module.py -> SessionService.require_active()`，当前约第 175 行。
4. `session_module.py -> PostgresSessionRepository.get()`，当前约第 117 行。

### 关键变量

| 变量 | 预期 |
| --- | --- |
| `session_id` | 与阶段一记录值一致 |
| `session` | 不是 `None` |
| `utc_now() < session.expires_at` | `True` |
| 返回 `preferences` | 与数据库一致 |

### 前端预期

- 有偏好时恢复到问卷模式选择、答题或结果阶段。
- 无偏好时回到欢迎页。

### 后端预期

- HTTP `200`。
- 返回原 Session，而不是创建新 Session。

### 通过标准

- [ ] 刷新前后的 `session_id` 相同。
- [ ] 数据从 PostgreSQL Repository 读取。
- [ ] 未过期 Session 没有触发 404/410。

---

## 6. 阶段三：保存活动分类和前置条件

### 前端操作

1. 选择一个或多个活动分类。
2. 填写时间、预算、出行、同行和城市/校园。
3. 点击继续或保存。

### HTTP 接口

```text
PUT /api/v1/sessions/{session_id}/preferences
```

### 断点顺序

1. `main.py -> save_preferences()`，当前约第 196 行。
2. `session_module.py -> SessionService.save_preferences()`，当前约第 183 行。
3. `session_module.py -> SessionService._touch()`，当前约第 206 行。
4. `session_module.py -> PostgresSessionRepository.save()`，当前约第 90 行。

### 关键变量

在路由检查 `body.model_dump()`：

```python
body.model_dump()
```

应包含：

```text
categories, duration, budget, outing,
company, city_or_campus, rest_only
```

在 Service 检查：

| 变量 | 预期 |
| --- | --- |
| `session.preferences` | 等于请求体 |
| `session.stage` | `questionnaire` |
| `session.version` | 比保存前增加 1 |
| `session.updated_at` | 更新为当前时间 |

### 前端预期

- 页面进入快速版/深度版选择。
- 保存失败时停留原页面并显示后端错误。

### 后端预期

```json
{
  "data": {
    "saved": true,
    "stage": "questionnaire",
    "version": 2
  },
  "error": null
}
```

### 数据库验证

```sql
SELECT id, stage, version, preferences, updated_at
FROM sessions
WHERE id = '<session_id>';
```

### 通过标准

- [ ] Pydantic 已把 JSON 转成 `PreferencesInput`。
- [ ] 分类和约束完整保存到 `preferences` JSONB。
- [ ] `version` 递增，阶段变成 `questionnaire`。

---

## 7. 阶段四：启动问卷

### 前端操作

点击“快速版”或“深度版”。

### HTTP 接口

```text
POST /api/v1/sessions/{session_id}/questionnaire/start
```

请求体：

```json
{"mode": "quick"}
```

或：

```json
{"mode": "deep"}
```

### 断点顺序

1. `main.py -> start_questionnaire()`，当前约第 220 行。
2. `questionnaire_module.py -> QuestionnaireService.start()`，当前约第 390 行。
3. `questionnaire_module.py -> QuestionnaireService.select_questions()`，当前约第 530 行。
4. `questionnaire_module.py -> PostgresQuestionnaireRepository.save_questionnaire()`，当前约第 137 行。
5. `questionnaire_module.py -> QuestionnaireService.payload()`，当前约第 575 行。

### 关键变量

| 变量 | 快速版 | 深度版 |
| --- | ---: | ---: |
| `mode` | `quick` | `deep` |
| `expected_count` | `5` | `30` |
| `len(questions)` | 至少 5 | 至少 30 |
| `len(questionnaire.question_ids)` | 5 | 30 |
| `questionnaire.submitted` | `False` | `False` |

还要检查：

```python
session.preferences["outing"]
session.preferences["company"]
questions[0].id
```

### 前端预期

- 显示第一题。
- 右侧总数显示 `5` 或 `30`。
- 四级选项固定为 1～4。

### 后端预期

- HTTP `200`。
- 返回 `mode`、`total`、`questions`、`scale`。
- 再次请求相同模式返回原问卷；请求不同模式返回 409。

### 数据库验证

```sql
SELECT session_id, mode, submitted, question_ids, started_at
FROM questionnaires
WHERE session_id = '<session_id>';
```

### 通过标准

- [ ] 快速版恰好 5 题，深度版恰好 30 题。
- [ ] 每个题目 ID 都进入 `question_ids`。
- [ ] 前端题目和后端返回一致。

---

## 8. 阶段五：保存和修改答案

### 前端操作

选择任一答案。之后点击“上一题”，对同一题选择另一个答案。

### HTTP 接口

```text
PATCH /api/v1/sessions/{session_id}/questionnaire/answers/{question_id}
```

### 断点顺序

1. `main.py -> save_answer()`，当前约第 229 行。
2. `questionnaire_module.py -> QuestionnaireService.save_answer()`，当前约第 417 行。
3. `questionnaire_module.py -> QuestionnaireService.require_active()`，当前约第 557 行。
4. `questionnaire_module.py -> QuestionnaireService.require_question()`，当前约第 566 行。
5. `questionnaire_module.py -> PostgresQuestionnaireRepository.save_answer_if_active()`，当前约第 190 行。

### 关键变量

| 变量 | 预期 |
| --- | --- |
| `question_id` | 属于当前 `questionnaire.question_ids` |
| `value` | `1`、`2`、`3` 或 `4` |
| `questionnaire.submitted` | `False` |
| `answer.skipped` | `False` |
| `stored` | `True` |

修改同一题时，数据库主键 `(session_id, question_id)` 不变，`value` 和 `answered_at` 更新。

### 前端预期

- 点击后自动进入下一道未处理题。
- 返回上一题时能显示已选答案。
- 修改后不增加答题总数，只更新该题答案。

### 后端预期

```json
{
  "data": {
    "saved": true,
    "question_id": "q_xxx",
    "value": 3
  },
  "error": null
}
```

### 数据库验证

```sql
SELECT session_id, question_id, value, skipped, answered_at
FROM questionnaire_answers
WHERE session_id = '<session_id>'
  AND question_id = '<question_id>';
```

### 通过标准

- [ ] 首次选择产生一行答案。
- [ ] 修改同一题仍然只有一行。
- [ ] 数据库 `value` 等于最后一次选择。

---

## 9. 阶段六：跳过题目和查询进度

### 前端操作

在一道未答题点击“跳过本题”，然后刷新页面。

### HTTP 接口

```text
POST /api/v1/sessions/{session_id}/questionnaire/skip/{question_id}
GET  /api/v1/sessions/{session_id}/questionnaire/progress
```

### 跳过断点

1. `main.py -> skip_question()`，当前约第 245 行。
2. `questionnaire_module.py -> QuestionnaireService.skip_question()`，当前约第 440 行。
3. `PostgresQuestionnaireRepository.save_answer_if_active()`，当前约第 190 行。

检查：

```python
answer.value is None
answer.skipped is True
stored is True
```

### 进度断点

1. `main.py -> get_progress()`，当前约第 251 行。
2. `questionnaire_module.py -> QuestionnaireService.progress()`，当前约第 460 行。
3. `PostgresQuestionnaireRepository.get_answers()`，当前约第 224 行。

检查：

```python
len(answered)
len(skipped)
len(question_ids - handled)
```

必须满足：

```text
answered_count + skipped_count + unanswered_count = total
```

### 前端预期

- 跳过后进入下一道未处理题。
- 刷新后从第一道未处理题恢复。
- 已答和已跳过记录仍存在。

### 数据库验证

```sql
SELECT question_id, value, skipped
FROM questionnaire_answers
WHERE session_id = '<session_id>'
ORDER BY answered_at;
```

### 通过标准

- [ ] 跳过记录为 `value=NULL, skipped=TRUE`。
- [ ] 刷新后进度计数不丢失。
- [ ] 三种计数总和等于问卷总题数。

---

## 10. 阶段七：提交问卷

### 前端操作

处理全部题目后点击“提交问卷”。

### HTTP 接口

```text
POST /api/v1/sessions/{session_id}/questionnaire/submit
```

### 断点顺序

1. `main.py -> submit_questionnaire()`，当前约第 255 行。
2. `questionnaire_module.py -> QuestionnaireService.submit()`，当前约第 496 行。
3. `questionnaire_module.py -> PostgresQuestionnaireRepository.submit_if_complete()`，当前约第 264 行。

### 关键变量

| 变量 | 预期 |
| --- | --- |
| `snapshot` | 不是 `None` |
| `snapshot.missing_question_ids` | `[]` |
| `questionnaire.submitted` | 提交后为 `True` |
| `answered_count + skipped_count` | 等于 `total` |

如果仍有未处理题，预期返回 409，`details.missing_question_ids` 列出缺失题目。

### 前端预期

前端提交成功后会立即调用计划生成接口。因此不要在问卷提交断点处长时间停留；检查完成后按 `F9`，准备进入下一组计划断点。

### 数据库验证

```sql
SELECT session_id, mode, submitted, submitted_at
FROM questionnaires
WHERE session_id = '<session_id>';
```

### 通过标准

- [ ] 未完成时返回 409，完成后返回 200。
- [ ] 提交后 `submitted=TRUE` 且 `submitted_at` 有值。
- [ ] 提交后的答案不能继续修改。

---

## 11. 阶段八：画像 Profile

### HTTP 接口

```text
POST /api/v1/sessions/{session_id}/plan/generate
```

请求由前端提交问卷后自动发送。

### 断点顺序

1. `main.py -> generate_plan()`，当前约第 259 行。
2. `mvp_orchestrator.py -> MVPOrchestrator.generate_plan()`，当前约第 336 行。
3. `mvp_orchestrator.py -> _normalize_preferences()`，当前约第 436 行。
4. `profile_module.py -> ProfileService.build()`，当前约第 97 行。
5. `mvp_orchestrator.py -> PostgreSQLProfileRepository.next_version()`，当前约第 95 行。
6. `mvp_orchestrator.py -> PostgreSQLProfileRepository.save()`，当前约第 103 行。

### 关键变量

在路由检查：

```python
body.free_start
body.free_end
body.density
```

在 Orchestrator 检查：

```python
questionnaire.submitted
len(questions)
len(answers)
constraints
```

在 Profile 检查：

```python
question_map.keys()
answer_map.keys()
dimensions
scores
profile.confidence
profile.profile_version
```

### 正常预期

- 快速版有 5 个题目和 5 个答案/跳过记录。
- 深度版有 30 个题目和 30 个答案/跳过记录。
- 每个分数位于 `0.0`～`1.0`。
- `confidence` 当前按答案记录数除以题目数计算，完整处理后通常为 `1.0`。

### 当前需要重点记录的缺口

执行：

```python
set(profile.scores)
set(constraints["categories"])
```

当前题目维度通常是英文键，例如 `energy`、`recovery`；活动分类是中文键，例如 `活力充电`、`松弛疗愈`。后续推荐代码使用中文分类查询 `profile.scores`，可能全部得到默认分数 `0`。

这表示：画像成功生成并保存，但问卷分数目前可能没有真正影响推荐排序。此项应记录为产品缺口，而不是判定 Profile 接口完全符合个性化要求。

### 数据库验证

```sql
SELECT session_id, profile_version, scores, constraints,
       confidence, rule_version
FROM profiles
WHERE session_id = '<session_id>'
ORDER BY profile_version DESC;
```

### 通过标准

- [ ] Profile 行成功保存。
- [ ] 分数范围正确，约束完整。
- [ ] 已记录分数键与分类键是否一致。

---

## 12. 阶段九：Task Repository 和 Recommendation

### 断点顺序

1. `mvp_orchestrator.py -> MVPOrchestrator._recommend()`，当前约第 419 行。
2. `task_repository.py -> TaskRepository.search_tasks()`，当前约第 237 行。
3. `recommendation_module.py -> recommend_tasks()`，当前约第 10 行。

### Task Repository 关键变量

```python
budget_limit
max_duration
outing
company
categories
len(candidates)
```

对筛选结果执行：

```python
[(task.title, task.category, task.budget, task.outing, task.company)
 for task in candidates]
```

每项候选必须满足预算、时长、出行、同行和分类约束。

### Recommendation 关键变量

```python
preference_map
len(usable)
len(ranked)
covered
missing
len(selected)
```

### 正常预期

- 推荐数量最多为 10。
- `selected_ids` 不重复。
- `covered_categories` 应包含所有用户选择分类。
- `missing_categories` 应为 `[]`。
- 每项推荐都有匹配理由。

### 错误预期

如果某分类在当前约束下没有候选任务，Orchestrator 返回 409：

```text
当前约束下无法覆盖全部选择分类
```

此时在断点检查 `missing_categories`，再回到 `candidates` 找出是预算、出行还是同行约束过滤了该分类。

### 通过标准

- [ ] 候选任务全部满足硬约束。
- [ ] 推荐任务不重复且不超过 10。
- [ ] 所有已选分类均被推荐覆盖。

---

## 13. 阶段十：Scheduling 时间排程

### 断点顺序

1. `scheduling_module.py -> build_schedule()`，当前约第 241 行。
2. `_validate_window()`，当前约第 100 行。
3. `_build_free_slots()`，当前约第 137 行。
4. `_attempt_schedule()`，当前约第 188 行。
5. `_place()`，当前约第 160 行。

### 关键变量

```python
density
config
ranked
base_slots
maximum_new_tasks
attempts
valid_attempts
created
items
unscheduled
```

### 三种密度

| 密度 | 最多任务 | 缓冲 | 休息块 |
| --- | ---: | ---: | ---: |
| `light` | 2 | 20 分钟 | 30 分钟 |
| `balanced` | 4 | 15 分钟 | 20 分钟 |
| `full` | 6 | 10 分钟 | 15 分钟 |

### 必须验证

```python
all(item.start_at < item.end_at for item in items)
any(item.kind == "rest" for item in items)
```

相邻项目不得重叠：

```python
all(left.end_at <= right.start_at for left, right in zip(items, items[1:]))
```

### 当前需要重点记录的缺口

如果用户选择 5 个分类而密度为 `balanced`，排程器最多安排 4 个任务。Recommendation 可以覆盖 5 个分类，但最终 `plan.items` 可能只覆盖 4 个分类。

比较：

```python
set(recommendation["covered_categories"])
{item.category for item in plan.items if item.kind == "task"}
```

两者不相等时，说明接口运行成功，但最终计划没有满足“覆盖所有已选分类”的产品要求，应记录为产品缺口。

### 通过标准

- [ ] 所有项目位于可用时间范围内。
- [ ] 时间不重叠。
- [ ] 至少有一个休息块。
- [ ] 未排入任务记录在 `unscheduled_task_ids`。
- [ ] 已记录最终计划分类是否覆盖全部已选分类。

---

## 14. 阶段十一：保存 Plan 并生成 Web Delivery

### 断点顺序

1. `mvp_orchestrator.py -> PostgreSQLPlanRepository.save()`，当前约第 208 行。
2. `mvp_orchestrator.py -> _to_delivery_plan()`，当前约第 458 行。
3. `delivery_module.py -> WebDeliveryService.deliver()`，当前约第 163 行。
4. `delivery_module.py -> build_web_payload()`，当前约第 132 行。
5. `delivery_module.py -> PostgreSQLDeliveryRepository.save_or_get_web()`，当前约第 192 行。

### 关键变量

```python
plan.plan_id
plan.items
plan.unscheduled_task_ids
web_plan
payload
row
delivery.status
```

### 前端预期

- 页面进入第 5 步结果页。
- 显示按时间排序的任务和休息块。
- 不再显示“当前约束下无法覆盖全部选择分类”。

### 后端预期

生成接口返回：

```text
profile
recommendation
plan
delivery
```

并满足：

```python
delivery.channel == "web"
delivery.status == "ready"
delivery.plan_id == plan.plan_id
```

### 数据库验证

```sql
SELECT id, session_id, density, free_start, free_end,
       version, unscheduled_task_ids
FROM plans
WHERE session_id = '<session_id>'
ORDER BY created_at DESC;

SELECT id, plan_id, task_id, title, category,
       start_at, end_at, kind, status, locked
FROM plan_items
WHERE plan_id = '<plan_id>'
ORDER BY start_at;

SELECT id, session_id, plan_id, channel, status,
       payload_json, created_at, updated_at
FROM delivery_jobs
WHERE session_id = '<session_id>'
ORDER BY created_at DESC;
```

### 通过标准

- [ ] `plans` 有一行计划头。
- [ ] `plan_items` 数量等于返回的 `plan.items` 数量。
- [ ] `delivery_jobs.channel=web`、`status=ready`。
- [ ] 前端显示的标题、时间和数据库一致。

---

## 15. 阶段十二：计划查询、刷新和重新开始

### 15.1 后端计划查询

接口：

```text
GET /api/v1/sessions/{session_id}/plan
```

断点：

1. `main.py -> get_plan()`，当前约第 275 行。
2. `mvp_orchestrator.py -> MVPOrchestrator.get_plan()`，当前约第 414 行。
3. `mvp_orchestrator.py -> PostgreSQLPlanRepository.get()`，当前约第 272 行。

通过 Swagger 调用，检查：

```python
plan.plan_id
len(plan.items)
```

必须与阶段十一记录一致。

### 15.2 当前前端刷新缺口

`frontend/api.js` 当前已经定义 `getPlan()`，但 `frontend/app.js -> initialize()` 没有调用它。刷新结果页时，前端会恢复 Session 和问卷进度，却不会从后端加载完整计划。

验证方法：

1. 在 `main.py -> get_plan()` 设置断点。
2. 在计划结果页按浏览器刷新。
3. 如果断点没有命中，说明前端确实没有请求 GET Plan。
4. 在 Swagger 手动调用 GET Plan，断点应正常命中并返回计划。

记录结论：

- [ ] 后端 GET Plan 正常。
- [ ] 前端刷新时调用了 GET Plan。

第二项在当前版本预计无法勾选，应作为前端接入缺口记录，而不是数据库故障。

### 15.3 重新开始

前端点击“重新开始”会执行：

```text
DELETE /api/v1/sessions/{session_id}/data
POST   /api/v1/sessions
```

断点顺序：

1. `main.py -> clear_session_data()`，当前约第 214 行。
2. `questionnaire_module.py -> QuestionnaireService.clear()`，当前约第 526 行。
3. `session_module.py -> SessionService.clear_data()`，当前约第 198 行。
4. 回到阶段一的 `create_session()`。

预期：

- 原 Session 的 Questionnaire 被删除。
- 原 Session 偏好清空，阶段重置为 `interests`。
- 前端删除本地 Session ID，并创建一个新的 Session。
- 新旧 `session_id` 不同。

当前清理接口不会删除原 Session 的 `profiles`、`plans` 和 `delivery_jobs`。这是数据清理边界，需要记录，但不阻止前端创建新会话。

### 通过标准

- [ ] 后端 GET Plan 能恢复最新计划。
- [ ] 已记录前端刷新未调用 GET Plan 的现状。
- [ ] 重新开始后创建了新 Session。
- [ ] 新页面回到欢迎或兴趣选择步骤。

---

## 16. 异常分支断点

异常处理函数位于 `main.py -> create_app()` 内：

| 状态 | 触发方式 | 主要断点 | 预期 |
| --- | --- | --- | --- |
| 404 | 使用不存在的 Session ID | `require_active()`、`handle_http_exception()` | `session_not_found` |
| 409 | 未完成问卷就提交 | `QuestionnaireService.submit()` | 返回缺失题目 |
| 409 | 未提交问卷就生成计划 | `MVPOrchestrator.generate_plan()` | `问卷尚未提交` |
| 409 | 约束下分类无法覆盖 | `recommend_tasks()`、Orchestrator | 返回 `missing_categories` |
| 410 | Session 超过 `expires_at` | `SessionService.require_active()` | `session_expired` |
| 422 | 答案发送 5 或密度拼写错误 | `handle_validation_error()` | `validation_error` |
| 503 | PostgreSQL 不可用 | `handle_database_error()` | `database_unavailable` |

不要为了测试 503 直接破坏数据库数据。可以先完成其他调试，再临时停止 PostgreSQL，调用一个接口，验证后立即重新启动。

统一错误响应应为：

```json
{
  "data": null,
  "error": {
    "code": "...",
    "message": "..."
  }
}
```

---

## 17. 最终验收表

### 前端与接口

- [ ] 首次打开自动创建 Session。
- [ ] 刷新时恢复同一个 Session。
- [ ] 保存分类和前置条件后进入模式选择。
- [ ] 快速版显示 5 题。
- [ ] 深度版显示 30 题。
- [ ] 答案自动保存并可修改。
- [ ] 跳过记录和进度可恢复。
- [ ] 未处理全部题目时不能提交。
- [ ] 提交后生成计划并显示结果。
- [ ] 重新开始后创建新 Session。

### 画像、推荐与排程

- [ ] Profile 分数范围为 0～1。
- [ ] Profile 约束与前置条件一致。
- [ ] 候选任务全部满足预算、时长、出行和同行约束。
- [ ] 推荐任务不重复且最多 10 项。
- [ ] Recommendation 覆盖全部已选分类。
- [ ] Plan 项目位于空闲时间内且不重叠。
- [ ] Plan 至少包含一个休息块。
- [ ] 未排入任务进入 `unscheduled_task_ids`。

### PostgreSQL 与 Delivery

- [ ] `sessions` 存在当前 Session。
- [ ] `questionnaires` 模式、题数和提交状态正确。
- [ ] `questionnaire_answers` 数量正确。
- [ ] `profiles` 保存了画像版本。
- [ ] `plans` 与 `plan_items` 保存了完整计划。
- [ ] `delivery_jobs` 状态为 `ready`。
- [ ] GET Plan 的 `plan_id` 与生成结果相同。

### 当前已知缺口

- [ ] 画像分数键与活动分类键已经一致。
- [ ] 最终计划覆盖全部已选分类，而不仅是推荐结果覆盖。
- [ ] 前端刷新结果页会调用 `getPlan()` 恢复计划。
- [ ] 清空接口会按产品数据保留策略处理历史画像、计划和交付记录。

如果前三项无法勾选，说明代码请求链路可以运行，但产品功能还没有完全满足 MVP 目标，需要进入下一轮修复，而不是继续在 PyCharm 中反复按 F8。

---

## 18. 调试结论模板

```text
测试 Session：
测试 Question：
生成 Plan：

已通过阶段：
1.
2.

未通过阶段：
1.

断点观察值：
1.

前端表现：

后端状态码与响应：

PostgreSQL 查询结果：

判断：
[ ] 程序错误
[ ] 数据问题
[ ] 产品规则缺口
[ ] 环境配置问题
```
