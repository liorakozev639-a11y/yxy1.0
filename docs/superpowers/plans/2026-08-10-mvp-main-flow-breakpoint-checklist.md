# MVP 前端主流程断点调试清单实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建一份面向初学者的中文调试清单，用 PyCharm 断点逐步验证当前前端已经接通的 MVP 主流程。

**Architecture:** 文档以真实前端操作顺序为主线，每个阶段从 `main.py` HTTP 路由进入，再跟踪 Service、Orchestrator、算法和 PostgreSQL Repository。函数名作为稳定定位，当前行号仅作辅助参考，并分别给出前端、后端和数据库通过标准。

**Tech Stack:** Markdown、Python 3.12、FastAPI、Pydantic、psycopg 3、PostgreSQL 18、PyCharm、Windows PowerShell。

## Global Constraints

- 只验证当前前端已接通的主流程。
- 不包含 Execution Module、Feedback Module、PDF、邮件、日历或实时地图接口。
- 不修改 Python、JavaScript 或数据库业务代码。
- 输出文件固定为 `docs/MVP前端主流程断点调试清单.md`。
- 使用中文和 Windows PowerShell 命令。
- 函数名是主要定位依据，行号只标注当前版本参考值。
- 数据库连接串中的密码固定写为 `<password>`。
- 不提交 `session_module.py` 和 `questionnaire_module.py` 的既有改动。

---

### Task 1: 核对主流程代码定位

**Files:**
- Read: `main.py`
- Read: `session_module.py`
- Read: `questionnaire_module.py`
- Read: `profile_module.py`
- Read: `task_repository.py`
- Read: `recommendation_module.py`
- Read: `scheduling_module.py`
- Read: `mvp_orchestrator.py`
- Read: `delivery_module.py`
- Read: `frontend/app.js`
- Read: `frontend/api-client.js`

**Interfaces:**
- Consumes: `main.py` 暴露的 Session、Questionnaire 和 Plan HTTP 路由。
- Produces: 每个前端动作对应的接口、Python 函数和当前行号表。

- [ ] **Step 1: 定位 FastAPI 路由**

运行：

```powershell
rg -n "@app\.(get|post|put|patch|delete)|^    def " main.py
```

预期：定位创建/恢复 Session、保存偏好、问卷开始/答题/跳过/进度/提交、计划生成/恢复和清空接口。

- [ ] **Step 2: 定位服务与算法函数**

运行：

```powershell
rg -n "def (create|restore|save_preferences|start|save_answer|skip_question|progress|submit|build|search_tasks|recommend_tasks|build_schedule|generate_plan|get_plan|deliver)" session_module.py questionnaire_module.py profile_module.py task_repository.py recommendation_module.py scheduling_module.py mvp_orchestrator.py delivery_module.py
```

预期：所有主流程服务、算法和交付函数均有结果。

- [ ] **Step 3: 定位前端调用点**

运行：

```powershell
rg -n "createSession|savePreferences|startQuestionnaire|saveAnswer|skipQuestion|progress|submitQuestionnaire|generatePlan|getPlan|clear" frontend
```

预期：能够把页面动作映射到 `frontend/api-client.js` 的 HTTP 调用。

### Task 2: 编写十二阶段断点调试清单

**Files:**
- Create: `docs/MVP前端主流程断点调试清单.md`
- Reference: `docs/MVP新增内容运行与调试指南.md`
- Reference: `docs/api.md`

**Interfaces:**
- Consumes: Task 1 的真实函数、路由和前端调用位置。
- Produces: 可直接照着执行的十二阶段调试文档。

- [ ] **Step 1: 编写调试环境和操作规则**

必须写明 PostgreSQL 5433、后端 8000、前端 5173、PyCharm 的 `uvicorn main:app` 配置、禁用 `--reload`、F7/F8/F9 和 Variables 使用方法。

- [ ] **Step 2: 编写 Session 与偏好阶段**

覆盖创建、恢复、保存偏好和清空数据；每个阶段包含前端动作、接口、断点顺序、关键变量、HTTP 结果、数据库表和通过标准。

- [ ] **Step 3: 编写 Questionnaire 阶段**

覆盖快速/深度问卷、答题覆盖、跳过、进度恢复和提交；明确观察 `question_ids`、`value`、`skipped`、`answered_count`、`submitted`。

- [ ] **Step 4: 编写计划生成阶段**

覆盖 Profile、Task Repository、Recommendation、Scheduling、Plan Repository 和 Web Delivery；明确观察 `scores`、`constraints`、`candidates`、`covered_categories`、`missing_categories`、`plan.items` 和 `delivery.status`。

- [ ] **Step 5: 编写刷新恢复与异常分支**

覆盖 GET Session、GET Questionnaire Progress、GET Plan，以及 404、409、410、422、503 的触发条件和观察点。

- [ ] **Step 6: 编写最终验收记录表**

提供可勾选条目，并保留 `session_id`、`question_id`、`plan_id`、HTTP 状态和数据库验证结果记录位。

### Task 3: 验证文档准确性

**Files:**
- Verify: `docs/MVP前端主流程断点调试清单.md`

**Interfaces:**
- Consumes: 正式清单中的函数名、接口、表名和命令。
- Produces: 与当前仓库一致、没有敏感信息的最终文档。

- [ ] **Step 1: 检查必需覆盖范围**

运行：

```powershell
rg -n "Session|Questionnaire|Profile|Task Repository|Recommendation|Scheduling|Delivery|PyCharm|Variables|PostgreSQL|通过标准" docs/MVP前端主流程断点调试清单.md
```

预期：每个关键词至少出现一次。

- [ ] **Step 2: 检查接口覆盖**

运行：

```powershell
rg -n "/api/v1/sessions|questionnaire/start|questionnaire/answers|questionnaire/skip|questionnaire/progress|questionnaire/submit|plan/generate|/plan" docs/MVP前端主流程断点调试清单.md
```

预期：`main.py` 当前主流程路由全部被清单覆盖。

- [ ] **Step 3: 检查敏感信息和格式**

运行：

```powershell
rg -n "postgresql://postgres:[^<]|Bearer [A-Za-z0-9]" docs/MVP前端主流程断点调试清单.md
git diff --check -- docs/MVP前端主流程断点调试清单.md
```

预期：敏感信息扫描无输出，`git diff --check` 退出代码为 0。

### Task 4: 提交正式清单

**Files:**
- Commit: `docs/MVP前端主流程断点调试清单.md`

**Interfaces:**
- Consumes: 通过 Task 3 验证的正式清单。
- Produces: 一个只包含正式清单的 Git 提交。

- [ ] **Step 1: 检查提交范围**

```powershell
git status --short
git diff -- docs/MVP前端主流程断点调试清单.md
```

- [ ] **Step 2: 只提交正式清单**

```powershell
git add -- docs/MVP前端主流程断点调试清单.md
git commit -m "docs: add main flow breakpoint checklist"
```

- [ ] **Step 3: 确认保留既有改动**

```powershell
git status --short
```

预期：`session_module.py` 和 `questionnaire_module.py` 的既有未提交改动仍存在，且没有被本次提交包含。
