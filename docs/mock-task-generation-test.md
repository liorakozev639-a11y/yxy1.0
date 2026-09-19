# 无模型密钥的任务生成闭环测试

本模式用于验证未来 AI 任务生成的数据契约和业务闭环，**不是实际大模型输出**。默认 `rules` 模式及线上页面行为保持不变；只有本地显式设置 `TASK_GENERATION_MODE=mock` 才启用模拟生成。生产 Vercel 环境拒绝开启此模式。

## 启动

1. 确认 PostgreSQL 已启动，且本机可连接到项目数据库。不要把数据库密码写进仓库。
2. 在新的 PowerShell 窗口进入仓库，设置连接串和模拟模式：

```powershell
Set-Location 'D:\yxy1.0'
$env:SESSION_DATABASE_URL = 'postgresql://postgres:<你的密码>@127.0.0.1:5433/free_time_agent'
$env:TASK_GENERATION_MODE = 'mock'
& '.\.venv\Scripts\python.exe' -m uvicorn main:app --host 127.0.0.1 --port 8000
```

3. 浏览器打开 `http://127.0.0.1:8000/`；前端由后端提供静态页面。若使用独立前端服务，确保其 API 指向 8000 端口。

## 验收路线

1. 创建新会话，选择方向、预算、出行及同行等硬性条件，完成并提交问卷。
2. 查看画像后生成计划。响应 `recommendation.generation_mode` 应为 `mock`，候选任务有 `first_action`、`prerequisites`、`generation_reason`、`recommendation_reason`、`evidence_refs`；页面明显标注“模拟生成”。
3. 核对候选任务符合本次预算、时长、出行、同行和低精力限制；没有有效问卷回答的维度不应出现在画像证据中。推荐任务可能多于能排进时间线的任务，未安排任务仍可供选择。
4. 连续更换同一个计划项：此前出现过的任务不能回流；指定不符合硬约束的任务应返回 409，原计划不变。
5. 将未安排的推荐任务加入时间线，修改起止时间，开始并完成一个任务，再提交反馈。重新排程时已开始或已完成的任务应保留，已跳过的任务不应重新出现。
6. 在同一会话用相同条件再次生成，应复用同一批任务及现有计划；改变条件后生成的新任务不能重复之前生成的具体任务。候选耗尽时应得到明确的 409，而非悄悄放宽条件。

## 自动检查

```powershell
Set-Location 'D:\yxy1.0'
& '.\.venv\Scripts\python.exe' -m unittest discover -s tests -p 'test_*.py'
node --test
```

模拟链路的数据库集成测试为 `tests/test_mock_api_flow.py`，需要可用的 `SESSION_DATABASE_URL`。测试只使用新建会话，并在结束时清理该会话。运行模式切换后请重启后端；仅刷新页面不会改变后端模式。
