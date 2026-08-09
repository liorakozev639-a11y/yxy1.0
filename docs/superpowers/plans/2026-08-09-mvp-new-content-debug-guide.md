# MVP 新增内容运行与调试指南实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建一份面向初学者的中文 Markdown 指南，完整解释新增整合文件的底层逻辑、本地运行方法和 PyCharm 调试路线。

**Architecture:** 文档以真实产品调用链为主线，把编排器、API 文档和 PowerShell 链路脚本放在同一条数据流中解释。所有命令、函数名、接口路径和数据库表均从当前 `D:\yxy1.0` 代码核对，不修改业务代码。

**Tech Stack:** Markdown、Python 3.12、FastAPI、Pydantic、psycopg 3、PostgreSQL 18、PowerShell、PyCharm。

## Global Constraints

- 输出文件固定为 `docs/MVP新增内容运行与调试指南.md`。
- 使用中文解释，面向正在学习编程的大学生。
- 命令使用 Windows PowerShell。
- 数据库密码使用 `<password>` 占位。
- 断点使用函数名定位，不依赖固定行号。
- 只讲当前核心流程，不宣称 Execution 和 Feedback 已接入主流程。

---

### Task 1: 编写工作流与底层原理

**Files:**
- Create: `docs/MVP新增内容运行与调试指南.md`
- Read: `mvp_orchestrator.py`
- Read: `main.py`
- Read: `docs/api.md`
- Read: `tests/live_core_flow.ps1`

**Interfaces:**
- Consumes: `MVPOrchestrator.generate_plan()`、`POST /api/v1/sessions/{session_id}/plan/generate`、`GET /api/v1/sessions/{session_id}/plan`。
- Produces: 可独立阅读的工作流、数据表和三份新增内容说明。

- [ ] **Step 1: 核对真实调用顺序**

运行：

```powershell
rg -n "def generate_plan|def _recommend|def _normalize_preferences|def _to_delivery_plan|class PostgreSQL" mvp_orchestrator.py
rg -n "plan/generate|questionnaire/submit|def build_orchestrator" main.py
```

预期：能够定位编排入口、推荐转换、偏好归一化、网页交付转换和 FastAPI 路由。

- [ ] **Step 2: 编写文档主体**

文档必须包含：新增内容总览、完整调用链、编排器依赖、四张 PostgreSQL 表、API/OpenAPI/Swagger 关系、链路脚本逐步解释、本地启动命令、PyCharm 断点、Variables 观察项、错误排查和验收清单。

- [ ] **Step 3: 检查敏感信息**

运行：

```powershell
rg -n "yxy050621|postgres:[^<]|Bearer [A-Za-z0-9]" docs/MVP新增内容运行与调试指南.md
```

预期：无输出。

### Task 2: 验证命令、接口和覆盖范围

**Files:**
- Verify: `docs/MVP新增内容运行与调试指南.md`
- Reference: `README.md`
- Reference: `docs/api.md`

**Interfaces:**
- Consumes: 当前本地启动命令、OpenAPI 路径和测试脚本。
- Produces: 与仓库现状一致且没有失效路径的教学文档。

- [ ] **Step 1: 检查必需章节**

运行：

```powershell
rg -n "mvp_orchestrator.py|docs/api.md|live_core_flow.ps1|PostgreSQL|Swagger|PyCharm|断点|验收" docs/MVP新增内容运行与调试指南.md
```

预期：每个关键词至少出现一次。

- [ ] **Step 2: 检查 Markdown 格式**

运行：

```powershell
git diff --check -- docs/MVP新增内容运行与调试指南.md
```

预期：退出代码为 0，无尾随空格或冲突标记。

- [ ] **Step 3: 核对本地链接目标**

确认 `mvp_orchestrator.py`、`main.py`、`docs/api.md`、`tests/live_core_flow.ps1`、`README.md` 均存在。

### Task 3: 提交文档

**Files:**
- Commit: `docs/MVP新增内容运行与调试指南.md`

- [ ] **Step 1: 查看提交范围**

```powershell
git status --short
git diff -- docs/MVP新增内容运行与调试指南.md
```

- [ ] **Step 2: 仅提交最终指南**

```powershell
git add -- docs/MVP新增内容运行与调试指南.md
git commit -m "docs: add mvp runtime debugging guide"
```

- [ ] **Step 3: 确认保留既有改动**

```powershell
git status --short
```

预期：`session_module.py` 和 `questionnaire_module.py` 的既有未提交改动仍然存在，未被本次提交包含。

