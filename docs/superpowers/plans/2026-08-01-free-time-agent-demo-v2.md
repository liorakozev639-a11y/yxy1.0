# 空闲时间规划 Agent Demo V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建一个独立的、无外部 API 的空闲时间规划 Agent 测试版，验证从偏好采集到通用活动推荐、排程、执行和调整的核心闭环。

**Architecture:** 保留现有原生 HTML/CSS/JS 技术栈，在 `outputs/free-time-agent-demo-v2/` 生成独立交付目录。逻辑层使用本地通用活动库和纯函数排程，页面层使用单页多阶段状态机，所有会话状态存储在浏览器 `localStorage` 中。现有 `index.html`、`app.js`、`logic.js` 和 `styles.css` 不覆盖、不修改。

**Tech Stack:** 原生 HTML5、CSS3、Browser JavaScript、CommonJS-compatible Node tests、`localStorage`。

## Global Constraints

- Demo 不接入实时地图、商户、活动、天气或交通 API。
- Demo 不调用大模型、不使用后端、不包含真实账号、支付、预约、邮件、PDF 或日历写入。
- 默认进入 5 题速测，可主动切换 30 题深测。
- 深测量表固定为：`非常同意｜比较同意｜不太同意｜完全不同意`。
- 推荐活动必须来自本地通用活动库，不得虚构具体商户、距离、价格或营业时间。
- MVP 聚焦 1 至 3 小时和半天空闲规划，使用单城市或单校园的通用场景文案。
- 用户界面使用“计划需要调整”，不把“失败”作为主提示。
- 自定义任务的原因标签可以为空。
- 现有原型文件不得被覆盖。

---

### Task 1: 建立独立 Demo 目录和页面骨架

**Files:**
- Create: `outputs/free-time-agent-demo-v2/index.html`
- Create: `outputs/free-time-agent-demo-v2/styles.css`
- Create: `outputs/free-time-agent-demo-v2/app.js`
- Create: `outputs/free-time-agent-demo-v2/logic.js`
- Test: `tests/demo-v2-smoke.test.js`

**Interfaces:**
- Produces a standalone page whose script paths are relative to `outputs/free-time-agent-demo-v2/`.
- Exposes `window.FreeTimeDemoV2` with `createInitialState`, `renderStage`, and `resetDemo`.

- [ ] **Step 1: Write the smoke test**

```js
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..', 'outputs', 'free-time-agent-demo-v2');
test('demo v2 has an independent runnable bundle', () => {
  expect(fs.existsSync(path.join(root, 'index.html'))).toBe(true);
  expect(fs.existsSync(path.join(root, 'styles.css'))).toBe(true);
  expect(fs.existsSync(path.join(root, 'app.js'))).toBe(true);
  expect(fs.existsSync(path.join(root, 'logic.js'))).toBe(true);
  expect(fs.readFileSync(path.join(root, 'index.html'), 'utf8')).toContain('app.js');
});
```

- [ ] **Step 2: Run the smoke test and verify the new bundle is missing**

Run: `node tests/demo-v2-smoke.test.js`

Expected: FAIL because the new independent directory does not exist yet.

- [ ] **Step 3: Create the page skeleton**

Create an accessible single-page shell with a header, progress indicator, `<main id="app">`, live status region, and hidden modal root. Include stage containers for welcome, interests, conditions, questionnaire, recommendations, plan, execution, and summary. Link only local `styles.css`, `logic.js`, and `app.js`.

- [ ] **Step 4: Add the initial state and stage renderer**

Implement `createInitialState()` with `stage: 'welcome'`, empty preferences, quick questionnaire mode, empty tasks and schedule. Implement `renderStage(state)` so the page can move between stages without relying on external libraries.

- [ ] **Step 5: Run smoke and syntax checks**

Run: `node tests/demo-v2-smoke.test.js` and `node --check outputs/free-time-agent-demo-v2/app.js`.

Expected: PASS.

### Task 2: Implement the local activity library and recommendation logic

**Files:**
- Modify: `outputs/free-time-agent-demo-v2/logic.js`
- Modify: `outputs/free-time-agent-demo-v2/app.js`
- Test: `tests/demo-v2-logic.test.js`

**Interfaces:**
- `getActivityLibrary(): Activity[]`
- `filterActivities(preferences): Activity[]`
- `recommendActivities(preferences, answers, count = 10): RecommendationResult`
- `Activity` fields: `id`, `title`, `category`, `duration`, `budget`, `mode`, `company`, `energy`, `restFirst`, `reason`

- [ ] **Step 1: Write failing tests for the activity constraints**

```js
test('recommendations come from the built-in activity library', () => {
  const result = logic.recommendActivities({ selectedCategories: ['calm'], outing: 'home' }, {}, 10);
  const ids = new Set(logic.getActivityLibrary().map((item) => item.id));
  expect(result.tasks).toHaveLength(10);
  expect(result.tasks.every((task) => ids.has(task.id))).toBe(true);
});

test('rest-first mode favors low-pressure activities', () => {
  const result = logic.recommendActivities({ selectedCategories: ['calm'], restFirst: true }, {}, 10);
  expect(result.tasks.slice(0, 3).every((task) => task.restFirst)).toBe(true);
});
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `node tests/demo-v2-logic.test.js`

Expected: FAIL because the activity functions do not exist.

- [ ] **Step 3: Add the local activity library**

Add at least 16 generic activities covering all five categories, including coffee, park walk, stretching at home, music, movie, reading, room reset, learning, dinner with friends, board games, city walk and rest-first activities. Do not include real venue names or fake live metadata.

- [ ] **Step 4: Implement filtering and ranking**

Filter by `outing`, `company`, budget and duration. Rank selected categories first, apply `restFirst` preference, then fill missing categories with generic activities. Always return 10 tasks when the library has enough entries and include a short matching reason.

- [ ] **Step 5: Run focused and existing tests**

Run: `node tests/demo-v2-logic.test.js` and `node tests/logic.test.js`.

Expected: both pass; existing prototype tests remain unchanged.

### Task 3: Implement the questionnaire and preference collection flow

**Files:**
- Modify: `outputs/free-time-agent-demo-v2/app.js`
- Modify: `outputs/free-time-agent-demo-v2/styles.css`
- Test: `tests/demo-v2-questionnaire.test.js`

**Interfaces:**
- `createQuestionnaire(mode, selectedCategories): Question[]`
- `Question` fields: `id`, `category`, `prompt`, `options`, `reverse`
- `quick` returns 5 questions; `deep` returns 30 questions using the fixed four-level scale.

- [ ] **Step 1: Write failing questionnaire tests**

```js
test('quick mode creates five questions', () => {
  expect(logic.createQuestionnaire('quick', ['energy'])).toHaveLength(5);
});

test('deep mode uses the fixed four-level scale', () => {
  const questions = logic.createQuestionnaire('deep', ['energy']);
  expect(questions).toHaveLength(30);
  expect(questions[0].options).toEqual(['非常同意', '比较同意', '不太同意', '完全不同意']);
});
```

- [ ] **Step 2: Run questionnaire tests and verify failure**

Run: `node tests/demo-v2-questionnaire.test.js`

Expected: FAIL because questionnaire generation is missing.

- [ ] **Step 3: Implement question generation and answer scoring**

Create a deterministic local question bank. Use one question per category in quick mode and priority-weighted selection in deep mode. Treat skipped questions as neutral and preserve answers when switching modes where question IDs overlap.

- [ ] **Step 4: Implement the staged UI**

Render interest cards, condition controls, mode selector, one-question-at-a-time questionnaire, progress, previous, skip, and submit actions. Make “今天只想休息” a visible optional toggle. Keep city/work status optional and non-blocking.

- [ ] **Step 5: Add autosave and restoration**

Persist the state after every meaningful interaction under a versioned key. On load, restore valid state; on malformed state, clear only the Demo V2 key and show a non-blocking reset message.

- [ ] **Step 6: Run questionnaire tests and syntax checks**

Run: `node tests/demo-v2-questionnaire.test.js` and `node --check outputs/free-time-agent-demo-v2/app.js`.

Expected: PASS.

### Task 4: Implement planning, custom tasks, and execution adjustment

**Files:**
- Modify: `outputs/free-time-agent-demo-v2/logic.js`
- Modify: `outputs/free-time-agent-demo-v2/app.js`
- Modify: `outputs/free-time-agent-demo-v2/styles.css`
- Test: `tests/demo-v2-planning.test.js`

**Interfaces:**
- `buildSchedule(tasks, preferences): ScheduleResult`
- `validateTimeWindow(task, schedule, preferences): { valid: boolean, message?: string }`
- `addCustomTask(state, input): State`
- `updateTaskStatus(state, taskId, status): State`

- [ ] **Step 1: Write failing tests for schedule rules**

```js
test('overlapping custom task is rejected', () => {
  const result = logic.validateTimeWindow({ start: 10 * 60, duration: 60 }, [{ start: 10 * 60, end: 11 * 60 }], { startMinute: 9 * 60, endMinute: 18 * 60 });
  expect(result.valid).toBe(false);
});

test('rest-first schedule contains a rest block', () => {
  const result = logic.buildSchedule([{ id: 'coffee', duration: 45, category: 'calm' }], { density: 'light', restFirst: true, startMinute: 9 * 60, endMinute: 15 * 60 });
  expect(result.some((item) => item.type === 'rest')).toBe(true);
});
```

- [ ] **Step 2: Run planning tests and verify failure**

Run: `node tests/demo-v2-planning.test.js`

Expected: FAIL because schedule helpers are missing.

- [ ] **Step 3: Implement density-aware schedule generation**

Generate a half-day schedule with explicit rest blocks. `light` must include at least one rest block and fewer activities than `balanced`; `full` may use more of the available window but must not exceed it.

- [ ] **Step 4: Implement custom task modal and validation**

Allow empty optional reason tags. Validate title, category, start time, duration, and budget. Prevent overlaps and out-of-window tasks with an actionable message.

- [ ] **Step 5: Implement execution statuses and soft adjustment**

Support start, complete, skip, replace, and “今天先不做”. When a task is missed or exceeds its window, render “计划需要调整” and expose immediate reschedule and replacement actions.

- [ ] **Step 6: Run planning tests and full syntax checks**

Run: `node tests/demo-v2-planning.test.js`, `node --check outputs/free-time-agent-demo-v2/app.js`, and `node --check outputs/free-time-agent-demo-v2/logic.js`.

Expected: PASS.

### Task 5: Polish responsive UI and verify delivery

**Files:**
- Modify: `outputs/free-time-agent-demo-v2/index.html`
- Modify: `outputs/free-time-agent-demo-v2/styles.css`
- Modify: `outputs/free-time-agent-demo-v2/app.js`
- Test: `tests/demo-v2-delivery.test.js`

**Interfaces:**
- Final output is usable at desktop and mobile widths without external assets.
- Test buttons for PDF and email show explicit “测试版暂未接入” feedback.

- [ ] **Step 1: Write delivery tests**

```js
test('delivery actions are clearly marked as test-only', () => {
  const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
  expect(html).toContain('测试版暂未接入');
  expect(html).toContain('今天只想休息');
});
```

- [ ] **Step 2: Implement the visual hierarchy**

Use restrained light background, strong dark text, blue accent, compact cards, clear progress, generous mobile controls, and a visible timeline. Do not add marketing-style hero sections or external images.

- [ ] **Step 3: Add final interaction states**

Add empty states, loading-like generation feedback, toast messages, restart action, and a visible local-only notice. Keep all controls keyboard reachable and labels associated with inputs.

- [ ] **Step 4: Run all tests and inspect the output**

Run: `node tests/demo-v2-smoke.test.js`, `node tests/demo-v2-logic.test.js`, `node tests/demo-v2-questionnaire.test.js`, `node tests/demo-v2-planning.test.js`, `node tests/demo-v2-delivery.test.js`, `node --check outputs/free-time-agent-demo-v2/app.js`, and `node --check outputs/free-time-agent-demo-v2/logic.js`.

Expected: all tests and syntax checks pass. Open `outputs/free-time-agent-demo-v2/index.html` locally for a manual smoke test; if browser file navigation is blocked, report that limitation without modifying the existing prototype.
