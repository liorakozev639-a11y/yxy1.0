# 空闲时间规划 Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将已确认的产品方案实现为一个可执行的休闲时间规划 Agent，覆盖速测/深测、条件约束、任务推荐、可调整排程、任务执行、实时地点、双向日历和隐私控制。

**Architecture:** 前端采用分步向导、任务时间线和执行状态界面；后端拆分为问卷编排、偏好计算、任务检索、Agent 推荐、排程、执行状态和交付服务。实时地点 API、日历 Provider、邮件/PDF Provider 都通过适配器接入，外部服务不可用时回退到审核任务库和网页/PDF 交付。

**Tech Stack:** 沿用现有前端框架与组件约定；后端使用现有项目的 API 框架；关系型数据库存储题库、任务、计划和反馈；浏览器 `localStorage` 用于匿名问卷草稿；OAuth 连接日历；Web Push 发送浏览器通知；Node.js 测试覆盖规则和 API 契约。

## Global Constraints

- 问卷分为 5 题速测和 30 题深测，用户可以主动切换。
- 深测使用四级量表：`非常同意｜比较同意｜不太同意｜完全不同意`，分值为 4 至 1 分。
- 首屏只选择兴趣方向，不强制输入城市、身份或工作状态。
- 计划密度有“轻松留白、张弛平衡、充实一点”三档。
- 任务必须支持开始、完成、跳过、换一个和失败后重排。
- 用户可自定义开始时间和持续时间；冲突或超出可用时间时阻止保存。
- 首版实时地点 API 只用于搜索和推荐，不提供预约、购票或支付。
- 首版支持读取和写入日历，但写入必须在用户确认最终计划后一次性执行。
- 匿名用户无需注册即可生成计划；登录后才保存历史计划和偏好。
- 定位、日历、浏览器通知和邮件发送必须单独授权。

---

### Task 1: 建立领域模型与数据契约

**Files:**
- Create: `src/domain/question.ts`
- Create: `src/domain/task.ts`
- Create: `src/domain/plan.ts`
- Create: `src/domain/user-preferences.ts`
- Create: `src/domain/validation.ts`
- Test: `tests/domain/validation.test.ts`

**Interfaces:**
- Produces `Question`, `Task`, `UserPreferences`, `PlanItem`, `Plan`, `PlanSession`, `QuestionnaireSession`, `RecommendationResult`, `ExecutionEvent`, `NotificationJob`, `Feedback`, `UnavailableWindow`, `LocationContext` and `CalendarWriteResult` types, plus validation functions.
- Required functions: `validateQuestion()`, `validateTask()`, `validateUserPreferences()`, `validatePlanItem()`.

- [ ] **Step 1: Write failing validation tests**

```ts
it('rejects a deep question that does not have exactly four scale options', () => {
  expect(() => validateQuestion({ mode: 'deep', options: ['非常同意', '同意'] })).toThrow();
});

it('rejects a plan item that overlaps an existing item', () => {
  expect(() => validatePlanItem({ start: 600, end: 720 }, [{ start: 660, end: 780 }])).toThrow();
});
```

- [ ] **Step 2: Run the focused tests and verify they fail because the validators are missing**

Run: `npm test -- tests/domain/validation.test.ts`

- [ ] **Step 3: Implement the minimal domain types and validators**

Deep questions must expose the four fixed labels and a reverse-scoring flag. Plan items must validate start/end ordering, available time, budget, and overlap.

- [ ] **Step 4: Run the focused tests and the full domain suite**

Run: `npm test -- tests/domain/validation.test.ts`

Expected: all domain tests pass with zero failures.

### Task 2: 实现前置分流与双问卷引擎

**Files:**
- Create: `src/questionnaire/question-bank.ts`
- Create: `src/questionnaire/question-allocation.ts`
- Create: `src/questionnaire/question-session.ts`
- Modify: `src/domain/user-preferences.ts`
- Test: `tests/questionnaire/question-allocation.test.ts`
- Test: `tests/questionnaire/question-session.test.ts`

**Interfaces:**
- `createQuickSession(preferences): QuestionnaireSession` creates five core questions, one per direction.
- `createDeepSession(preferences): QuestionnaireSession` creates thirty questions using priority allocation.
- `answerQuestion(sessionId, questionId, value): QuestionnaireSession` persists progress.
- `skipQuestion(sessionId, questionId): QuestionnaireSession` records a neutral default without blocking progress.
- `switchMode(sessionId, mode): QuestionnaireSession` preserves already valid answers where possible.

- [ ] **Step 1: Write failing tests for quick/deep modes, priority allocation, skip and mode switching**

```ts
it('creates five quick questions covering the five directions', () => {
  expect(createQuickSession(defaultPreferences()).questions).toHaveLength(5);
});

it('allocates deep questions by priority as 18/12 for two directions', () => {
  expect(createDeepSession(preferencesWith(['energy', 'calm'])).counts).toEqual({ energy: 18, calm: 12 });
});
```

- [ ] **Step 2: Run the tests and confirm the missing engine causes failure**

Run: `npm test -- tests/questionnaire`

- [ ] **Step 3: Implement the question bank and allocation engine**

Filter by mode, user type, outing range, company preference and available duration before applying priority allocation. Use reviewed generic questions when a category lacks enough questions.

- [ ] **Step 4: Implement local draft persistence**

Persist every answer, selected mode, current question and timestamp to a versioned `localStorage` key. Add `restoreSession()` and `clearSession()` with expiry handling.

- [ ] **Step 5: Run questionnaire tests**

Run: `npm test -- tests/questionnaire`

Expected: quick mode, deep mode, skip, restore, clear and switching tests pass.

### Task 3: 建立任务库、实时地点适配器与推荐接口

**Files:**
- Create: `src/tasks/task-repository.ts`
- Create: `src/tasks/location-provider.ts`
- Create: `src/tasks/task-search.ts`
- Create: `src/recommendation/recommendation-service.ts`
- Create: `src/recommendation/recommendation-schema.ts`
- Test: `tests/tasks/task-search.test.ts`
- Test: `tests/recommendation/recommendation-service.test.ts`

**Interfaces:**
- `searchTasks(criteria): Promise<Task[]>` returns tasks matching budget, location, outing, company and duration.
- `searchLivePlaces(criteria): Promise<LivePlace[]>` calls map/activity/merchant adapters without booking.
- `recommendTasks(input): Promise<RecommendationResult>` returns exactly ten candidates, coverage metadata and matching reasons.
- `fallbackToReviewedTasks(criteria): Promise<Task[]>` is used when live APIs fail.

- [ ] **Step 1: Write failing tests for constraints, coverage and fallback**

```ts
it('does not return an outdoor task for a home-only request', async () => {
  const tasks = await searchTasks({ outing: 'home', location: '上海' });
  expect(tasks.every((task) => task.mode !== 'outdoor')).toBe(true);
});

it('returns ten candidates covering every selected direction', async () => {
  const result = await recommendTasks(inputFor(['energy', 'social']));
  expect(result.tasks).toHaveLength(10);
  expect(result.coveredCategories).toEqual(expect.arrayContaining(['energy', 'social']));
});
```

- [ ] **Step 2: Run tests and verify the adapters are missing**

Run: `npm test -- tests/tasks tests/recommendation`

- [ ] **Step 3: Implement reviewed-task filtering and live-provider adapters**

Live results must include provider, name, location, distance, price, open status, retrieved time and freshness status. Never let the Agent invent these fields.

- [ ] **Step 4: Implement recommendation schema validation**

Reject outputs with fewer than ten tasks, uncovered selected categories, missing reasons or tasks outside hard constraints. Retry once, then use deterministic reviewed-task ranking.

- [ ] **Step 5: Implement API fallback**

When a live provider times out or returns an error, use the reviewed task repository and label the result as a general or possibly stale suggestion.

- [ ] **Step 6: Run task and recommendation tests**

Run: `npm test -- tests/tasks tests/recommendation`

### Task 4: 实现计划密度、时间冲突与自定义任务

**Files:**
- Create: `src/planner/schedule-engine.ts`
- Create: `src/planner/conflict-service.ts`
- Create: `src/planner/custom-task-service.ts`
- Test: `tests/planner/schedule-engine.test.ts`
- Test: `tests/planner/conflict-service.test.ts`

**Interfaces:**
- `buildSchedule(tasks, preferences, density): Plan`
- `validateTimeWindow(item, existingItems, unavailableWindows): ValidationResult`
- `createCustomTask(input): Task`
- `replanAfterFailure(plan, failedTaskId): Plan`

- [ ] **Step 1: Write failing tests for density, manual time, conflict blocking and failure recovery**

```ts
it('creates fewer tasks and longer breaks in relaxed mode', () => {
  expect(buildSchedule(tasks, preferences, 'relaxed').items.length)
    .toBeLessThan(buildSchedule(tasks, preferences, 'full').items.length);
});

it('rejects overlapping manual task windows', () => {
  expect(validateTimeWindow({ start: 660, end: 750 }, [{ start: 700, end: 780 }], [])).toEqual({ valid: false });
});
```

- [ ] **Step 2: Run planner tests and confirm failure**

Run: `npm test -- tests/planner`

- [ ] **Step 3: Implement density-aware scheduling and hard constraint validation**

Block overlap, unavailable calendar windows, over-budget plans and end times outside the user’s available duration. Return the nearest valid slot when a manual time is rejected.

- [ ] **Step 4: Implement custom task creation and insertion**

Validate task name, duration, category, budget, outing mode and company preference, then rerun coverage and schedule validation.

- [ ] **Step 5: Implement failed-task recovery**

Return actions `replan`, `replace`, and `abandon`; replan only uses remaining available time and never overwrites completed tasks.

- [ ] **Step 6: Run planner tests**

Run: `npm test -- tests/planner`

### Task 5: 实现任务执行状态、提醒与反馈

**Files:**
- Create: `src/execution/execution-service.ts`
- Create: `src/execution/notification-service.ts`
- Create: `src/feedback/feedback-service.ts`
- Test: `tests/execution/execution-service.test.ts`
- Test: `tests/feedback/feedback-service.test.ts`

**Interfaces:**
- `startTask(planId, taskId, now): ExecutionEvent`
- `completeTask(planId, taskId, now, rating?): ExecutionEvent`
- `skipTask(planId, taskId, reason?): ExecutionEvent`
- `evaluateTaskDeadline(task, now): 'pending' | 'failed' | 'completed'`
- `scheduleReminder(task, minutesBefore): NotificationJob`
- `recordFeedback(taskId, rating, reasons?): Feedback`

- [ ] **Step 1: Write failing tests for state transitions and deadlines**

```ts
it('marks a task failed when it was not started by its start time', () => {
  expect(evaluateTaskDeadline(taskStartingAt(600), 601)).toBe('failed');
});

it('accepts optional reasons with a one-to-five satisfaction rating', () => {
  expect(recordFeedback('task-1', 5, ['很适合当前精力'])).toMatchObject({ rating: 5 });
});
```

- [ ] **Step 2: Run tests and verify the execution service is missing**

Run: `npm test -- tests/execution tests/feedback`

- [ ] **Step 3: Implement state machine and deadline evaluation**

Support `pending`, `in_progress`, `completed`, `not_started_failed`, `timed_out_failed` and `abandoned`. Keep completed history immutable.

- [ ] **Step 4: Implement reminder delivery**

Default to ten minutes before start, allow five, fifteen or thirty minutes, show in-app notification, and send browser notification only after explicit permission.

- [ ] **Step 5: Implement feedback storage and aggregation**

Store rating and optional reasons; expose aggregates for recommendation ranking without retaining unnecessary free-text personal data.

- [ ] **Step 6: Run execution tests**

Run: `npm test -- tests/execution tests/feedback`

### Task 6: 接入双向日历、定位与身份授权

**Files:**
- Create: `src/integrations/calendar-provider.ts`
- Create: `src/integrations/location-provider.ts`
- Create: `src/auth/anonymous-session.ts`
- Create: `src/auth/oauth-consent.ts`
- Create: `src/privacy/data-retention.ts`
- Test: `tests/integrations/calendar-provider.test.ts`
- Test: `tests/privacy/data-retention.test.ts`

**Interfaces:**
- `readCalendarWindows(consent): Promise<UnavailableWindow[]>`
- `writePlanToCalendar(plan, consent, calendarId): Promise<CalendarWriteResult>`
- `revokeCalendarConsent(connectionId): Promise<void>`
- `resolveLocation(manualLocation, preciseLocationConsent): Promise<LocationContext>`
- `deleteSessionData(sessionId): Promise<void>`

- [ ] **Step 1: Write failing tests for consent, read/write behavior and retention**

```ts
it('does not write calendar events before final plan confirmation', async () => {
  await expect(writePlanToCalendar(unconfirmedPlan, consent, 'primary')).rejects.toThrow();
});

it('deletes anonymous session data without deleting an unrelated logged-in account', async () => {
  await deleteSessionData('anonymous-session');
  expect(await hasData('anonymous-session')).toBe(false);
});
```

- [ ] **Step 2: Run integration tests and verify missing adapters fail**

Run: `npm test -- tests/integrations tests/privacy`

- [ ] **Step 3: Implement read-only calendar availability**

Read existing events only after user authorization; convert them to unavailable windows consumed by the conflict service.

- [ ] **Step 4: Implement confirmed one-shot calendar write**

After final confirmation, show the target calendar, write all selected items once, persist external event IDs, and never delete external events on an internal replan without another confirmation.

- [ ] **Step 5: Implement manual-first location resolution**

Use manually entered city/campus by default. Only use precise browser location after explicit consent, and provide a revoke action.

- [ ] **Step 6: Implement anonymous-first retention rules**

Anonymous sessions use local drafts and short-lived server state. Logged-in users can opt into history, saved preferences and reuse. Account deletion removes history, preferences and stored feedback.

- [ ] **Step 7: Run integration and privacy tests**

Run: `npm test -- tests/integrations tests/privacy`

### Task 7: 完成前端闭环、交付渠道与验收

**Files:**
- Modify: `src/features/onboarding/*`
- Modify: `src/features/questionnaire/*`
- Modify: `src/features/planner/*`
- Modify: `src/features/execution/*`
- Create: `src/delivery/pdf-renderer.ts`
- Create: `src/delivery/email-delivery.ts`
- Create: `tests/e2e/free-time-plan.spec.ts`

**Interfaces:**
- Frontend screens: `onboarding`, `mode-select`, `questionnaire`, `recommendations`, `plan-editor`, `task-execution`, `delivery`.
- User actions: `selectDirection`, `chooseMode`, `answer`, `skip`, `saveManualTime`, `start`, `complete`, `replace`, `replan`, `createCustomTask`, `confirmCalendarWrite`.

- [ ] **Step 1: Write the end-to-end acceptance tests**

```ts
test('quick flow creates, executes, completes and rates a plan', async ({ page }) => {
  await selectDirections(page, ['活力充电', '松弛疗愈']);
  await page.getByRole('button', { name: '5 题速测' }).click();
  await answerAllQuickQuestions(page);
  await chooseDensity(page, '轻松留白');
  await startFirstTask(page);
  await completeFirstTask(page);
  await rateTask(page, 5);
  await expect(page.getByText('反馈已记录')).toBeVisible();
});
```

- [ ] **Step 2: Run the end-to-end test and verify the new UI flow fails**

Run: `npm run test:e2e -- tests/e2e/free-time-plan.spec.ts`

- [ ] **Step 3: Implement the onboarding and mode selection screens**

Keep the first screen click-only, collect optional conditions in later steps, show estimated effort, and never force the deep questionnaire.

- [ ] **Step 4: Implement questionnaire interaction and recovery UI**

Show one question at a time, fixed bottom controls, progress, remaining-time estimate, previous, skip, copy-answer, clear-data and resume states.

- [ ] **Step 5: Implement recommendation, plan editor and execution cards**

Show three default recommendations first, keep the remaining candidates available behind “换一个”, support manual start/duration, conflict blocking, failure recovery and custom tasks.

- [ ] **Step 6: Implement delivery channels**

Render the confirmed plan consistently in the webpage and PDF. Email requires one-time address entry and explicit consent. Calendar write requires a separate explicit confirmation.

- [ ] **Step 7: Run end-to-end and accessibility checks**

Run: `npm run test:e2e -- tests/e2e/free-time-plan.spec.ts`

Expected: quick and deep flows, interruption recovery, manual conflict blocking, failed-task replan, custom task creation, PDF rendering and consent-gated calendar write pass.

## Spec Coverage Review

- Questionnaire cost reduction: Tasks 2 and 7.
- Four-level scale, smart question selection and reverse scoring: Tasks 1 and 2.
- Local autosave, resume, skip and anomaly fallback: Tasks 2 and 5.
- Real-time location/activity search and reviewed fallback: Task 3.
- Three plan densities, manual time windows and conflict blocking: Task 4.
- Start/complete/fail/replan/custom task/feedback loop: Tasks 4, 5 and 7.
- Browser notifications and calendar read/write consent: Tasks 5 and 6.
- Anonymous-first account, retention and deletion: Task 6.
- Web, PDF and email delivery: Task 7.

## Recommended Execution Order

1. Tasks 1-2: domain and questionnaire foundation.
2. Tasks 3-4: recommendations and scheduling.
3. Task 5: execution loop, which is the primary MVP success criterion.
4. Tasks 6-7: integrations, delivery and production acceptance.
