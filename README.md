# 空闲时间规划 Agent MVP

当前版本打通以下真实链路：

```text
创建 Session
-> 保存兴趣方向与前置条件
-> 选择快速版 5 题或深度版 30 题
-> 自动保存、修改或跳过答案
-> 刷新后恢复进度
-> 提交问卷
-> 计算画像、筛选任务、生成排程
-> 网页展示计划
```

后端只使用 PostgreSQL，不提供内存模式；本地测试版只使用 `session_id`，不使用 Token 或 `Authorization`。

## 1. 项目入口

- 后端唯一入口：`main.py`
- 前端目录：`frontend`
- 后端接口文档：`http://127.0.0.1:8000/docs`
- 静态接口说明：`docs/api.md`
- 前端页面：`http://127.0.0.1:5173/`

不要再单独运行旧版 `session_module.py` 或 `questionnaire_module.py`，否则会占用端口或形成两套不共享状态的服务。

## 2. 启动 PostgreSQL

本机现有安装目录为 `D:\pgsql18`，数据目录为 `D:\pgsql18\data`，项目使用端口 `5433`：

```powershell
& "D:\pgsql18\pgsql\bin\pg_ctl.exe" start `
  -D "D:\pgsql18\data" `
  -l "D:\pgsql18\postgres.log" `
  -o '"-p 5433"' `
  -w
```

确认数据库可用：

```powershell
& "D:\pgsql18\pgsql\bin\pg_isready.exe" `
  -h 127.0.0.1 -p 5433 -d free_time_agent
```

期望输出包含 `accepting connections`。数据库 `free_time_agent` 需要已经创建。

## 3. 安装 Python 依赖

在 PowerShell 中执行：

```powershell
Set-Location "D:\yxy1.0"
uv venv .venv --python 3.12
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
```

真实密码只写入当前终端环境变量，不要写入代码或提交：

```powershell
$env:SESSION_DATABASE_URL = `
  "postgresql://postgres:<password>@127.0.0.1:5433/free_time_agent"
```

## 4. 启动后端

```powershell
Set-Location "D:\yxy1.0"
.\.venv\Scripts\python.exe -m uvicorn main:app `
  --host 127.0.0.1 `
  --port 8000
```

打开 `http://127.0.0.1:8000/docs`，应看到 Session、Questionnaire 和 Plan Generation 接口。

如果提示 `8000` 被占用，先在 PyCharm 停止旧的 `session_module.py` 调试进程，再启动 `main.py`。

## 5. 启动前端

另开一个 PowerShell：

```powershell
Set-Location "D:\yxy1.0"
.\.venv\Scripts\python.exe -m http.server 5173 `
  --bind 127.0.0.1 `
  --directory frontend
```

浏览器打开：

```text
http://127.0.0.1:5173/
```

前端只在 `localStorage` 保存 `free_time_agent_session_id`。刷新页面后会从 PostgreSQL 恢复当前问卷和已保存答案。

## 6. PyCharm 逐行调试

新建 Python Run/Debug Configuration：

- Python interpreter：`D:\yxy1.0\.venv\Scripts\python.exe`
- Run kind：Module name
- Module name：`uvicorn`
- Parameters：`main:app --host 127.0.0.1 --port 8000`
- Working directory：`D:\yxy1.0`
- Environment variables：`SESSION_DATABASE_URL=postgresql://postgres:<password>@127.0.0.1:5433/free_time_agent`

推荐断点位置：

- `main.py`：HTTP 请求进入点。
- `session_module.py`：Session 校验、偏好保存和 PostgreSQL 读写。
- `questionnaire_module.py`：抽题、答案覆盖、进度统计和提交锁定。

点击 Debug 后，从前端操作或 Swagger 调用接口，PyCharm 会在对应断点暂停。

## 7. 自动化测试

先设置 `SESSION_DATABASE_URL`，再执行：

```powershell
.\.venv\Scripts\python.exe -m unittest discover `
  -s tests -p "test_*.py" -v

node --test tests/*.test.js
```

Python 测试会创建临时 Session，并在结束后从 PostgreSQL 删除这些测试数据。

## 8. 实机链路检查

后端运行时执行：

```powershell
.\tests\live_flow.ps1
```

脚本会创建会话、保存前置条件、开始快速问卷并保存第一题答案，最后输出：

```json
{"session_id":"sess_...","question_id":"q_energy","mode":"quick","total":5,"answered_count":1}
```

重启后端后，可用输出中的 `session_id` 验证数据仍在：

```powershell
Invoke-RestMethod `
  "http://127.0.0.1:8000/api/v1/sessions/<session_id>"

Invoke-RestMethod `
  "http://127.0.0.1:8000/api/v1/sessions/<session_id>/questionnaire/progress"
```

第二个接口应继续返回 `answered_count = 1`，证明 Session、问卷和答案都来自 PostgreSQL，而不是进程内存。

核心计划链路可在后端启动后执行：

```powershell
.\tests\live_core_flow.ps1
```

脚本会验证创建会话、保存偏好、提交问卷、画像、推荐、排程、网页交付和计划恢复。

## 9. 当前范围

当前已接入 Profile、Task Repository、Recommendation、Scheduling 和网页 Delivery。任务库仍是人工审核的通用活动，不调用实时地图、商户或活动 API。PDF、邮件、日历、Execution 和 Feedback 尚未接入主流程。
