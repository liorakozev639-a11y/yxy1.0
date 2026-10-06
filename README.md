# 留白计划：空闲时间规划 Agent MVP

“留白计划”是一个帮助用户把突然出现的空闲时间转成可执行安排的网页产品。用户不必先想好“要做什么”，而是从自己当下的精力、时间、预算、出行和陪伴偏好出发，完成一轮轻量调查，再获得一份包含具体任务和时间段的计划。

它尤其适合忙碌一段时间后突然拥有休息时间、周末不知道如何安排、下班后精力有限、想独处但不想完全躺平的用户。产品的目标不是把一天排满，而是在用户可接受的约束下，给出能够开始、能够调整、能够完成的下一步。

> 当前项目是可本地运行、使用 PostgreSQL 持久化的 MVP。所谓“Agent”由规则化的画像、筛选、推荐与排程模块协作实现；尚未接入大语言模型、实时地图、商户或活动 API。

本地还提供可选的 `TASK_GENERATION_MODE=mock`：用确定性的模拟生成器验证“会话和问卷证据 -> 生成约束摘要 -> 校验候选任务 -> 排程 -> 执行与反馈”整条链路，无需模型密钥或 Token。它不代表真实 AI；默认及 Vercel 线上仍使用现有规则任务库。启动命令和逐步验收见 [模拟任务生成测试说明](docs/mock-task-generation-test.md)。

## 产品定位

“留白计划”是一款面向忙碌人群的空闲时间规划 Agent。它把用户当下的时间、精力、心情、预算、地点和陪伴偏好，逐步转成可执行的任务与时间线。

产品解决的不是“任务太少”，而是“有一段空闲时间，却不知道现在做什么、能不能做、如何开始”。它强调低决策成本、可调整和能真正完成，不追求把用户的日程排满。

## 面向人群

- **学生**：课间、晚自习前后、周末或考试结束后，需要快速安排一段可执行的休息、成长或社交时间。
- **上班族**：下班后、午休、临时空档或周末拥有碎片时间，但当下精力和出行意愿有限。
- **独处或低精力用户**：希望得到低社交压力、低体力消耗、可在家完成的建议。
- **希望改善空闲时间质量的人**：不想继续无目的刷手机，也不希望被复杂的待办清单压迫。

## 主要优势

1. **从当下状态出发**：先收集可用时间、精力、心情、预算、天气和地点依赖，再生成建议，避免只按固定标签推荐。
2. **推荐可解释**：每个任务都返回匹配理由、推荐原因和负荷信息，用户能理解为什么适合自己。
3. **推荐与排程分离**：候选任务先经过硬约束筛选，再由排程模块决定哪些任务进入时间线，推荐池不会因一次排程失败而丢失。
4. **任务可以被用户掌控**：用户能够替换、跳过、加入时间线、修改起止时间和重新排程；系统给出推荐时间，但不强制执行。
5. **会从反馈中调整**：完成、跳过、替换和低分反馈会影响当前会话后续推荐，并在历史页解释系统学到了什么。
6. **适合渐进式演进**：当前使用可测试、可复现的规则任务库，已保留任务生成契约和 `TASK_GENERATION_MODE=mock`，后续可以在不改变排程、执行和反馈链路的情况下接入大模型。

## 使用方法（快速开始）

### 1. 准备 PostgreSQL

Windows 本地 PostgreSQL 默认使用项目约定的 `5433` 端口。先确认数据库服务和 `free_time_agent` 数据库可连接，再在 PowerShell 中设置连接串：

```powershell
$env:SESSION_DATABASE_URL = "postgresql://postgres:<数据库密码>@127.0.0.1:5433/free_time_agent"
```

不要把真实密码提交到 GitHub、README 或日志中。

### 2. 启动后端

```powershell
Set-Location "D:\yxy1.0"
& ".\.venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000
```

后端启动后可检查：

- 健康检查：`http://127.0.0.1:8000/health`
- 数据库健康检查：`http://127.0.0.1:8000/api/v1/health/database`
- Swagger：`http://127.0.0.1:8000/docs`

### 3. 启动前端

另开一个 PowerShell 窗口：

```powershell
Set-Location "D:\yxy1.0\frontend"
npm install
npm run dev
```

然后打开终端输出的本地地址，通常是 `http://127.0.0.1:5173/`。前端会通过 `frontend/config.js` 中的 API 地址连接后端；本地开发时默认指向 `http://127.0.0.1:8000`。

### 4. 按用户流程使用

1. 创建会话并选择兴趣方向。
2. 填写可用时间、预算、出行方式、同行偏好、当前精力和心情。
3. 选择快速版或深度版问卷，逐题作答并提交。
4. 查看偏好画像解释，确认系统为什么推荐这些任务。
5. 生成最多 10 个推荐任务，查看理由后加入时间线、替换或跳过。
6. 调整任务起止时间，点击“按此流程执行”。
7. 开始、完成或跳过任务，并提交反馈。
8. 打开“我的历史”查看完成情况、偏好变化和系统下次的推荐策略。

遇到错误时，先查看浏览器开发者工具的 Network 请求、后端 PowerShell 日志和 Swagger 响应体。完整的接口、调试和验收流程见本文后续章节以及 `docs/` 目录。

## 产品用途

- 将“我有时间，但不知道做什么”转化为一份任务清单和时间安排。
- 用快速问卷识别用户当前更需要活力、休息、社交、探索还是成长。
- 避免推荐不符合硬约束的活动，例如预算不足、只能居家、想独处或可用时间太短。
- 让用户在计划生成后继续调整，而不是被一次生成的日程束缚。
- 记录任务是否开始、完成、跳过或超时，为后续重新排程和任务反馈提供依据。

## 适用场景

| 场景 | 产品如何帮助用户 |
| --- | --- |
| 突然获得半天休息时间 | 选择时长和偏好后，快速生成可执行的半日安排。 |
| 周末不知道做什么 | 同时选择多个活动方向，得到覆盖多个方向的任务组合。 |
| 工作后精力不足 | 通过工作状态、节奏和问卷结果，优先筛选恢复压力较低的任务。 |
| 想独处但不想完全躺平 | 将同行偏好设置为独处，获得低社交成本的轻量活动。 |
| 临时改变想法 | 可以修改时间、替换任务、跳过任务或重新排程。 |

## 用户主流程

```text
创建本地会话
-> 选择一个或多个兴趣方向，并设置优先级
-> 填写可用时长、预算、出行方式、同行偏好等条件
-> 选择快速版 5 题或深度版 30 题
-> 单题作答、自动保存、允许跳过和刷新恢复
-> 提交问卷并查看偏好画像
-> 生成 10 个候选任务和一份时间计划
-> 查看任务匹配理由，替换、跳过或添加自定义任务
-> 调整推荐时间并按当前流程执行
-> 记录开始、完成、跳过、超时和任务反馈
-> 网页内提醒与计划结束后的统一复盘
```

## 核心功能

### 1. 兴趣方向与前置条件

用户可以选择一个或多个活动方向，并通过上下移动按钮设置优先级：

- **活力充电**：运动、走动和恢复身体活力。
- **松弛疗愈**：放松、休息和缓解压力。
- **社交连接**：与朋友、同学或家人相处。
- **乐享探索**：吃喝、娱乐和轻度探索。
- **自我成长**：阅读、学习和兴趣提升。

前置条件包括身份、近期学习或工作状态、可用时长、预算区间、所在城市或校园、居家/附近/全城的活动方式、独处/结伴偏好和安排节奏。用户还可以补充今天的天气/出门成本、准备使用的时间段、当前精力和当前心情。城市或校园为选填；当前 MVP 不根据位置调用真实商户、地图或天气 API，但这些字段会被保存并参与本次推荐排序，为后续接入本地推荐预留。

### 2. 双模式偏好问卷

产品提供两种问卷模式：

- **快速版**：5 题，适合临时规划；每个已选方向优先覆盖一道相关题目。
- **深度版**：30 题，适合半天或全天的细化安排；会结合所选方向、出行方式和同行偏好抽取相关题目。

量表统一为四级，不设置“中立”选项：`1 完全不同意`、`2 不太同意`、`3 比较同意`、`4 非常同意`。每次作答会立即写入 PostgreSQL；用户可以回看修改、跳过题目，刷新页面后可继续填写。问卷提交后系统拒绝重复提交，避免同一会话出现不一致的结果。

### 3. 偏好画像与结果解释

问卷提交后，Profile 模块会按题目维度汇总回答，形成 0 到 1 的偏好分数，并输出用户当前偏好画像。画像不是心理诊断，也不用于给用户贴标签；它只服务于本次空闲时间的任务匹配，例如帮助系统判断用户更偏向恢复、社交、探索或成长型安排。

网页会先展示画像与解释，再让用户生成计划。这样用户可以理解“为什么系统会推荐这些任务”，而不是只收到一份黑盒日程。

### 4. 任务库、候选任务与推荐理由

当前内置人工审核的通用任务库：

- 共 **700 个活动任务**，五个活动分类各 140 个。
- 共 **150 道题目**，五个分类各 30 道。
- 每项任务带有分类、建议时长、预算、出行方式、同行方式和适用场景等元数据。

推荐模块会先筛掉不符合预算、可用时间、出行方式、同行偏好或场景的任务，再根据画像分数、用户选择的优先级、历史反馈和当下生活条件排序。系统返回最多 10 个候选任务，并尽量确保用户所选的每个分类都被覆盖。每个任务会附带匹配分、偏好标签、警示信息和推荐理由，便于用户判断是否保留。

真实生活条件会影响推荐权重：

- **天气/出门成本**：下雨、偏热、偏冷或今天想待在室内时，居家和地点灵活任务会获得更高排序；晴朗时，附近或城市探索会获得少量加分。
- **时间段**：晚上和睡前会降低高体力任务的排序，优先保留低负担、短时间任务。
- **当前精力**：低精力时优先推荐轻松度高、体力消耗低、社交压力低的任务；高精力时可承接更有活动量的任务。
- **当前心情**：焦虑或想放空时优先低刺激、低社交压力任务；无聊时提高探索和社交任务排序；想充电时提高活力和成长任务排序。

问卷提交后，MVP 编排器固定请求 10 个推荐任务，并在响应中返回 `recommended_task_count`、`task_ids` 和 `tasks`。正式前端会在计划结果页一次性展示这 10 个推荐任务；其中能够放入当前空闲时间窗口的任务会进入时间线，其余任务仍保留在推荐任务池中，不会因为时间不足而丢失。

每个任务还带有任务轻重元数据：轻松度、体力消耗、社交压力和地点依赖。轻松度和其他负荷指标由任务分类、时长、预算、出行方式、同行方式及标题关键词规则化推导，便于后续按当下精力进行更细的排序和替换。

计划页的每个任务卡片都提供推荐调节按钮：`更轻松`、`更短时间`、`更低预算`、`更近/居家`、`少社交`、`成长感`。用户点击后，系统会把当前任务写入当前会话的 PostgreSQL 排除池，优先从同分类、符合当前硬约束、且不属于历史相似任务组的任务中选择替代项；如果相似任务组已经被排完，系统会降级到“同分类且具体任务从未出现过”的候选池。这样连续点击“换一个”或调节按钮时，不会出现两个任务来回切换，也不会因为相似分组过少而过早卡住。

如果当前分类和约束下连“从未出现过的具体任务”也没有了，前端会保留原任务并提示“当前没有更合适的任务”。这份排除记忆只对当前会话及该会话后续重新生成的计划生效，不会永久删除公共任务库中的任务。

当推荐无法覆盖全部选择分类时，后端会在 409 响应中返回可执行修复方案，而不是只给出错误文本。前端会展示“放宽条件重新生成”“改成轻量计划”“先保留可覆盖分类”等像素风按钮；用户点击后，页面会自动调整本次偏好、保存到 PostgreSQL，并重新生成计划。

### 5. 自动排程与计划管理

Scheduling 模块把推荐任务排进用户提供的可用时间窗口，并生成轻松、平衡、充实三种密度的安排。排程会处理任务时长、任务间缓冲、休息块、锁定任务、时间冲突和剩余空档。

生成计划后，用户可以：

- 查看按时间排序的任务时间线和任务详情。
- 一键复制“分享执行清单”，把 Session、偏好方向、推荐时间、任务名称和当前状态整理成纯文本，方便发给自己、同学或朋友。
- 更换某一任务；系统会永久排除当前会话里该计划项已经出现过的具体任务，并优先避开相似任务。
- 使用推荐调节按钮，把任务改成更轻松、更短、更低预算、更近、更少社交压力或更有成长感的同分类任务；当相似任务不足时，会自动降级为“不重复具体任务”的候选池。
- 跳过任务，或添加一条自定义任务。
- 重新排程，重新组织尚未完成的任务。
- 修改任意未跳过任务的开始时间和结束时间。

任务时间会进行范围与冲突校验：结束时间必须晚于开始时间，任务不能互相重叠，且不能超出本次空闲时间窗口。每次修改都会使用计划版本号进行校验，并保存为 PostgreSQL 中的新计划版本，避免旧页面误覆盖新计划。

### 6. 推荐时间与执行闭环

时间线显示的是系统的**推荐时间**，不是强制时间。用户可先逐项调整任务起止时间，再点击“按此流程执行”确认当前安排。

执行阶段支持以下状态：

| 用户动作或事件 | 任务状态 | 说明 |
| --- | --- | --- |
| 开始任务 | `pending -> active` | 可早于推荐开始时间启动。 |
| 完成任务 | `active -> completed` | 可早于推荐结束时间完成。 |
| 执行中跳过 | `pending/active -> needs_adjustment` | 任务保留为后续重新排程的对象。 |
| 超过结束时间未开始 | `pending -> needs_adjustment` | 记录为 missed。 |
| 超过结束时间未完成 | `active -> needs_adjustment` | 记录为 overdue。 |

每一次开始、完成、跳过或超时都会生成执行事件。完成后的任务可提交 1 到 5 分评分，并选择最多 3 个原因标签。评分 4-5 分时前端展示“容易开始”“符合当前状态”“下次还想做”等正向原因；评分 1-2 分时会切换为“太累”“太贵”“不想出门”“时间太长”“不感兴趣”“社交压力大”等不喜欢原因，帮助系统后续减少相似任务。同一任务再次提交反馈时会更新原有记录。

计划页打开期间会立即检查一次，并每 30 秒刷新执行状态：页面会提示“现在可以开始”“任务即将结束”或“有 N 项任务需要调整”。提醒只在网页打开期间生效，不依赖浏览器通知或后台服务。

计划到达结束时间后，用户可以查看统一复盘，看到完成、跳过、未完成的汇总与下一次建议。每个已完成任务可选填“满意 / 一般 / 不满意”；该感受可重新修改，只记录本次体验，不等同于低分反馈，也不会自动排除相似任务。

当用户给任务 1–2 分或跳过任务时，系统会在当前会话和后续重排中避开对应任务组。计划页会以“已为你避开 N 组不喜欢的任务”说明这一状态；替换任务后会直接显示替换原因，但不会暴露内部任务组标识。

结果页还会生成一份适合复制的执行清单。它不是新的数据库对象，而是前端根据当前计划实时整理出的文本摘要：包含本次 `Session ID`、所选方向、每个任务的推荐起止时间、任务分类和执行状态。用户点击“复制计划”后，可直接粘贴到聊天软件、备忘录或待办工具中；如果浏览器剪贴板权限不可用，页面会弹出可手动复制的文本。

### 7. 历史计划与偏好学习可视化

正式像素前端在计划结果页提供“我的历史”入口。点击后，页面会在当前结果页内切换到历史视图，不跳转新页面，也不需要登录账号。当前 MVP 使用浏览器保存的匿名 `user_id` 关联用户历史，未来可以平滑迁移到账号体系，实现跨设备学习。

历史视图会展示：

- **摘要统计**：本周完成任务数、累计完成任务数、跳过/替换次数、1–2 分低分反馈次数。
- **本周完成了哪些任务**：帮助用户看到自己已经实际完成的空闲安排。
- **最近 5 个历史计划**：展示每个计划中的完成、跳过、替换概况。
- **最喜欢哪些任务类型**：按大分类统计用户更常完成的方向。
- **经常跳过哪些类型**：按大分类和细任务组解释用户可能不喜欢的任务类型。
- **系统学到了什么**：把完成、跳过、替换、低分反馈转成用户能理解的自然语言解释。
- **下次会如何推荐**：说明系统后续会如何提高喜欢类型的排序，并降低不合适任务的出现频率。

如果用户还没有任何历史记录，页面会展示空状态，引导用户先完成、跳过或反馈几个任务。低分反馈表尚未初始化时，历史洞察服务会把低分反馈计为 0，避免第一次启动产品时历史页报错。

## 技术实现概览

- **前端**：原生 HTML、CSS 和 JavaScript；采用像素风交互界面，通过 `fetch` 调用后端接口。
- **像素视觉优化**：偏好页用“今日状态”组织天气、时间段、精力和情绪；画像页和计划页用轻量信息条解释本次推荐参考了哪些真实生活条件。
- **PWA 壳**：`frontend/manifest.json` 提供安装信息；`frontend/service-worker.js` 缓存前端壳页面和静态资源；`frontend/config.js` 预留线上 API 地址配置。
- **后端**：FastAPI，同步接口由 `main.py` 统一注册。
- **数据库**：PostgreSQL，保存会话、偏好、问卷、答案、画像、计划、计划项、执行事件、网页交付与反馈。
- **上线材料**：`deploy/` 提供 Vercel + Supabase、Render + Supabase、独立服务器 + Nginx 三种网页版上线资料。
- **业务编排**：`mvp_orchestrator.py` 连接 Session、Questionnaire、Profile、Task Repository、Recommendation、Scheduling、Delivery 等模块。
- **真实生活条件推荐**：`main.py` 接收 `weather`、`day_part`、`energy_level`、`mood`；`mvp_orchestrator.py` 将这些偏好写入画像约束；`recommendation_module.py` 用这些约束调整任务排序、标签、警示和推荐理由。
- **推荐调节**：`recommendation_module.py` 根据调节意图排序候选；`recommendation_memory.py` 将被用户换掉或调节过的任务 ID 保存到 PostgreSQL；`plan_module.py` 和 `mvp_orchestrator.py` 分别处理计划内任务和推荐池任务。
- **失败修复建议**：`mvp_orchestrator.py` 在分类覆盖失败时返回 `recovery_options`；`frontend/flow.js` 将后端详情转成前端可执行选项；`frontend/app.js` 负责保存调整后的偏好并重新生成计划。
- **计划分享摘要**：`frontend/flow.js` 将当前计划转换为纯文本执行清单；`frontend/app.js` 在结果页提供复制入口，不额外写入数据库。
- **历史洞察**：`history_insight_service.py` 聚合 `user_task_history`、`plans`、`plan_items` 和 `task_feedback`，为前端“我的历史”视图提供摘要统计、最近计划、偏好说明和下次推荐策略。
- **计划版本控制**：Plan 模块每次变更计划都会递增版本号，前端必须携带当前版本号提交更新。
- **健康检查**：`GET /health` 检查后端，`GET /api/v1/health/database` 使用只读查询检查 PostgreSQL；前端会在启动恢复时调用两者并显示可操作的中文错误提示。
- **接口文档**：FastAPI 自动生成 Swagger，运行后访问 `http://127.0.0.1:8000/docs`；静态说明见 `docs/api.md`。

## 数据与 MVP 边界

后端只使用 PostgreSQL，不提供内存模式。普通业务页面使用浏览器保存的 `session_id`，不要求普通用户登录或携带 `Authorization`。测试观测还会保存不含个人信息的 `mvp_test_anonymous_id`；浏览器存储被阻止时改用当前页面会话内的随机匿名编号，不使用固定共享编号。管理员看板另用短期 bearer token 认证；退出流程结束时前端总会清除本地 token，但服务端只有在 logout 请求成功时才会撤销 token，请求失败时服务端 token 会自然过期。不要复制、分享、写入代码或日志；公网部署必须使用 HTTPS 和密钥管理。

当前不在 MVP 范围内的能力包括实时地图/商户/活动搜索、PDF 下载、邮件发送、日历同步、用户账号体系、跨设备登录和大模型实时对话。任务推荐也不表示医疗、心理或职业建议。

## 1. 项目入口

- 后端唯一入口：`main.py`
- 前端目录：`frontend`
- 后端接口文档：`http://127.0.0.1:8000/docs`
- 静态接口说明：`docs/api.md`
- 前端页面：`http://127.0.0.1:5173/`
- PWA 配置：`frontend/manifest.json`、`frontend/service-worker.js`、`frontend/config.js`
- Vercel 上线说明：`deploy/README-vercel.md`
- 服务器/Render 上线说明：`deploy/README-deploy.md`

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

如需使用测试指标管理员看板，再设置以下变量。密码只写入当前终端或部署平台的密钥配置，不要写入代码、日志或提交：

```powershell
$env:ADMIN_METRICS_USERNAME = '<admin-username>'
$env:ADMIN_METRICS_PASSWORD = '<strong-password>'
```

## 4. 启动后端

```powershell
Set-Location "D:\yxy1.0"
.\.venv\Scripts\python.exe -m uvicorn main:app `
  --host 127.0.0.1 `
  --port 8000
```

打开 `http://127.0.0.1:8000/docs`，应看到 Session、Questionnaire、Profile、Plan、Execution 和 Feedback 接口。

也可以先检查服务状态：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/database
```

两个接口都返回 `data.status` 为 `ok` 后，再打开前端页面。数据库未连接时，前端会提示检查 PostgreSQL；后端未启动时，前端会提示先启动后端。

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

管理员看板地址：

```text
http://127.0.0.1:5173/admin.html
```

看板登录后只展示匿名聚合指标和按匿名编号筛选的匿名行为明细，不展示个人身份。完整的大学生邀请、匿名编号复用、指标口径、一个月记录和删除注意事项见 [测试指标使用说明](docs/user-testing-metrics.md)。

管理员也可以在看板中按匿名编号删除观测数据，或手动运行 90 天保留期清理；这些操作不会删除业务会话、计划、任务或正常业务反馈。

前端在 `localStorage` 保存 `free_time_agent_session_id` 和测试用 `mvp_test_anonymous_id`。后者只是区分测试样本的匿名编号，不是用户账号；若存储不可用，只在当前浏览器会话内保留随机编号。刷新页面后业务会话会从 PostgreSQL 恢复当前问卷和已保存答案。管理员 token 只用于 `/admin.html` 的受保护请求；点击退出后本地 token 总会被清除，服务端撤销取决于 logout 请求是否成功，失败时会自然过期。不要把 token 或管理员密码粘贴到 issue、截图或提交中。

## 6. PWA 与上线准备

当前前端已经具备基础 PWA 能力：

- 浏览器会读取 `frontend/manifest.json`，识别应用名称、主题色、启动路径和图标。
- `frontend/service-worker.js` 会缓存首页、CSS、配置文件、API 客户端、流程脚本、主交互脚本和像素图片。
- Service Worker 不缓存 `/api/v1/` 和 `/health` 请求，避免用户看到过期的业务数据。
- 首页会在浏览器允许时显示“添加到桌面”入口；在本机 `localhost/127.0.0.1` 可调试，正式安装体验需要 HTTPS。

线上部署有两种推荐方式。

**方案 B：Vercel + Supabase**

这是当前优先方案。前端和 FastAPI 后端部署在同一个 Vercel 域名下，PostgreSQL 使用 Supabase。此时 `frontend/config.js` 可以保持为空，前端会自动请求当前 Vercel 同源域名下的 `/api/v1/...` 和 `/health`，不会再请求本机 `:8000` 端口。

需要准备的文件已经在仓库中：

| 文件 | 用途 |
| --- | --- |
| `vercel.json` | 告诉 Vercel 如何把 `/api/*`、`/health` 交给 FastAPI，把首页和静态资源交给 `frontend`。 |
| `api/index.py` | Vercel Python Serverless 入口，复用现有 `main.py` 中的 FastAPI 应用。 |
| `.vercelignore` | 排除本地虚拟环境、日志、备份和生成文件，减少部署包体积。 |
| `deploy/README-vercel.md` | Vercel + Supabase 免费上线步骤。 |

在 Vercel 的环境变量中填写：

```text
SESSION_DATABASE_URL=Supabase Transaction pooler PostgreSQL 连接串
FRONTEND_ORIGINS=https://你的-vercel-域名.vercel.app
```

部署后访问：

```text
https://你的-vercel-域名.vercel.app/
https://你的-vercel-域名.vercel.app/health
https://你的-vercel-域名.vercel.app/docs
```

如果首页能打开，但后端返回 `database_not_configured`，说明 Vercel 环境变量里还缺少 `SESSION_DATABASE_URL`，需要在项目设置中补充 Supabase PostgreSQL 连接串后重新部署。

**独立服务器或 Render 分离部署**

如果前端和后端不在同一个域名下，可以把 `frontend/config.js` 中的 `FREE_TIME_API_BASE_URL` 设置成公网后端地址，例如：

```javascript
window.FREE_TIME_API_BASE_URL = 'https://api.example.com';
```

本地开发时，如果这个值为空，前端会自动使用当前网页协议和主机名拼出 `:8000` 后端地址，方便继续本地调试；线上非本地域名会默认使用同源地址。

项目已经提供部署辅助文件：

| 文件 | 用途 |
| --- | --- |
| `deploy/.env.production.example` | 服务器后端环境变量模板，复制后填写真实数据库密码。 |
| `deploy/frontend-config.production.example.js` | 前端公网 API 地址模板，发布前复制为 `frontend/config.js`。 |
| `deploy/nginx-free-time-agent.conf` | Nginx 静态前端与 FastAPI 反向代理模板。 |
| `deploy/start-local-product.ps1` | Windows 本地一键启动 PostgreSQL、后端和前端。 |
| `deploy/check-local-product.ps1` | 检查本地 API、数据库、首页、Manifest 和 Service Worker。 |
| `deploy/README-deploy.md` | 完整网页版上线指南。 |
| `deploy/README-vercel.md` | Vercel + Supabase 免费上线指南。 |
| `vercel.json` | Vercel 前后端同域名部署配置。 |
| `api/index.py` | Vercel FastAPI 入口文件。 |
| `render.yaml` | Render 免费方案的后端与静态前端 Blueprint。 |
| `deploy/write_frontend_config.py` | Render 静态站点构建时写入公网 API 地址。 |

本地快速启动可以执行：

```powershell
Set-Location "D:\yxy1.0"
.\deploy\start-local-product.ps1
```

本地检查可以执行：

```powershell
Set-Location "D:\yxy1.0"
.\deploy\check-local-product.ps1
```

真正部署到公网服务器前，需要准备服务器登录方式、域名或公网 IP、PostgreSQL 连接信息和 HTTPS 证书。当前仓库不提交真实密码；`.env.production` 和 `.env.local` 已被 `.gitignore` 忽略。

如果暂时没有服务器，推荐先用免费方案 B：Supabase 提供 PostgreSQL，Vercel 通过 `vercel.json` 部署前端和 FastAPI 后端。具体申请和部署步骤见 `deploy/README-vercel.md`。如果 Vercel 不适合，再使用 Render 方案，步骤见 `deploy/README-deploy.md` 第 10 节。

## 7. PyCharm 逐行调试

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

## 8. 自动化测试

先设置 `SESSION_DATABASE_URL`，再执行：

```powershell
.\.venv\Scripts\python.exe -m unittest discover `
  -s tests -p "test_*.py" -v

node --test tests/*.test.js

.\.venv\Scripts\python.exe -m py_compile `
  main.py test_observability.py admin_metrics_service.py

git diff --check
```

Python 测试会创建临时 Session，并在结束后从 PostgreSQL 删除这些测试数据。

测试指标交付的完整检查也可以直接使用上面四条命令的无 `-v` 版本；如果 PostgreSQL 不可用，Python 测试可能在模块启动时等待数据库连接，应记录被阻塞的原始命令和环境限制，不要把离线检查写成真实集成通过。

管理员看板只适用于本地或受控环境。不要公开暴露 `/admin.html`、不要复用生产用户密码、不要把真实姓名或联系方式写入匿名测试记录；公网部署必须使用 HTTPS、受限的 `FRONTEND_ORIGINS` 和密钥管理。

## 9. 实机链路检查

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

## 10. 本次任务库与十条推荐验收

在仓库根目录执行：

```powershell
.\.venv-debug\Scripts\python.exe -m unittest `
  tests.test_task_repository_expansion `
  tests.test_recommendation_reasons `
  tests.test_mvp_integration `
  tests.test_scheduling_module -q

node --test tests/frontend-flow.test.js `
  tests/frontend-visual.test.js `
  tests/frontend-api.test.js `
  tests/demo-v2-logic.test.js
```

通过标准：

- 任务库总数为 700 条，五个分类各 140 条。
- 推荐响应中的 `recommended_task_count` 为 10。
- `task_ids` 与 `tasks` 均包含 10 项，且任务 ID 不重复。
- 前端计划结果页出现“本次推荐任务 10 个”。
- 时间线根据用户空闲时间显示可排入的任务，并保留休息块。

如果全量 Python 测试提示缺少 `SESSION_DATABASE_URL`，先按照第 3 节设置 PostgreSQL 连接变量；任务库和推荐逻辑的离线测试不依赖在线数据库。

## 11. 真实生活条件与视觉优化验收

启动 PostgreSQL、后端和前端后，在浏览器访问 `http://127.0.0.1:5173/`，按下面步骤验证：

1. 在第一步选择至少一个方向，例如“活力充电”和“松弛疗愈”。
2. 在“今日状态”页设置：天气为“下雨/不稳定”，时间段为“晚上”，精力为“有点累”，心情为“有点焦虑”。
3. 保存条件并完成问卷，进入画像解释页。
4. 画像页应出现“今天的真实生活条件”信息区，展示下雨、晚上、低精力和焦虑等标签。
5. 点击生成计划，计划页应出现“本次推荐参考了”信息条。
6. 推荐任务应更倾向居家、低体力、低社交压力、短时间任务；任务卡片中的推荐理由应解释天气、时间段、精力或情绪为什么影响推荐。
7. 再创建一个新会话，将天气改为“适合外出”、精力改为“精力充足”，对比推荐结果，应更容易看到附近活动、探索或活力类任务。

对应自动化测试：

```powershell
.\.venv\Scripts\python.exe -m unittest `
  tests.test_recommendation_life_context `
  tests.test_recommendation_reasons `
  tests.test_mvp_integration `
  tests.test_api_flow.PreferencesInputTests

node --test tests/frontend-flow.test.js tests/frontend-api.test.js
```

## 12. 历史计划与偏好学习验收

启动 PostgreSQL、后端和前端后，在浏览器访问 `http://127.0.0.1:5173/`，按下面步骤验证：

1. 新开一个会话，完成兴趣选择、偏好配置、问卷和计划生成。
2. 在计划结果页点击“我的历史”。如果还没有完成、跳过、替换或低分反馈，应看到空状态提示。
3. 返回计划，开始一个任务并完成它，再提交一次任务反馈。
4. 跳过或替换另一个任务。
5. 再次点击“我的历史”，应看到本周完成数、累计完成数、跳过/替换数发生变化。
6. 查看“系统学到了什么”和“下次会如何推荐”，应能看到系统如何利用完成、跳过、替换和低分反馈解释后续推荐策略。

对应自动化测试：

```powershell
node --test tests/frontend-api.test.js tests/frontend-visual.test.js

$env:SESSION_DATABASE_URL = "postgresql://postgres:<password>@127.0.0.1:5433/free_time_agent"
.\.venv-debug\Scripts\python.exe -m unittest `
  tests.test_history_insight_service `
  tests.test_user_history_api -v
```

## 13. PWA 验收

启动前端后打开 `http://127.0.0.1:5173/`：

1. 进入首页，应看到“像 App 一样使用留白计划”的提示区域。
2. 在支持 PWA 安装的浏览器中，地址栏或页面会出现安装入口。
3. 打开浏览器开发者工具的 Application / 应用 面板，应能看到 Manifest 和 Service Worker。
4. 刷新页面后，前端静态资源应能继续加载；业务数据仍然从后端和 PostgreSQL 读取。
5. 线上部署时必须使用 HTTPS，否则大多数手机浏览器不会显示正式安装入口。
