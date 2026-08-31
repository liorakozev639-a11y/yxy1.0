const assert = require('node:assert/strict');
const test = require('node:test');

const {
  firstUnansweredIndex,
  recoverInitialization,
  recommendationMemorySummary,
  taskReasonSummary,
  resumeDestination,
} = require('../frontend/flow.js');

test('resumeDestination distinguishes welcome, mode, quiz, and result', () => {
  assert.equal(resumeDestination({ preferences: {}, progress: null }), 'welcome');
  assert.equal(resumeDestination({
    preferences: { categories: ['energy'] },
    progress: null,
  }), 'mode');
  assert.equal(resumeDestination({
    preferences: { categories: ['energy'] },
    progress: { submitted: false },
  }), 'quiz');
  assert.equal(resumeDestination({
    preferences: { categories: ['energy'] },
    progress: { submitted: true },
  }), 'result');
});

test('firstUnansweredIndex resumes at the first missing answer', () => {
  const questions = [{ id: 'q1' }, { id: 'q2' }, { id: 'q3' }];
  assert.equal(firstUnansweredIndex(questions, { q1: { value: 4 } }), 1);
  assert.equal(firstUnansweredIndex(questions, {
    q1: { value: 4 },
    q2: { skipped: true },
    q3: { value: 2 },
  }), 2);
});

test('recoverInitialization exposes replacement-session failures for retry', async () => {
  let forgot = false;
  const replacementError = new Error('数据库离线');
  const result = await recoverInitialization({
    forgetSession() { forgot = true; },
    async createSession() { throw replacementError; },
  }, { status: 410 });

  assert.equal(forgot, true);
  assert.equal(result.recovered, false);
  assert.equal(result.retry, true);
  assert.equal(result.message, '数据库离线');
});

test('recoverInitialization returns the replacement session on success', async () => {
  const result = await recoverInitialization({
    forgetSession() {},
    async createSession() { return { session_id: 'sess_new' }; },
  }, { status: 404 });

  assert.equal(result.recovered, true);
  assert.equal(result.session.session_id, 'sess_new');
});

test('taskReasonSummary normalizes card tags and detail text', () => {
  const item = {
    title: '居家拉伸',
    category: '活力充电',
    reason_tags: ['居家可做', '低预算', '短时间可完成', '适合独处'],
    reason_text: '你选择了「活力充电」，这个任务可以覆盖该方向。',
    match_score: 0.86,
    matched_preferences: ['分类偏好强', '居家可做'],
    warning_text: '预算略高，请确认是否接受。',
    replacement_reason: '已避开你之前看过的任务。',
    load_profile: {
      ease_label: '很轻松',
      physical_label: '低体力',
      social_label: '低社交压力',
      location_label: '居家',
    },
  };

  const summary = taskReasonSummary(item);

  assert.deepEqual(summary.tags, ['居家可做', '低预算', '短时间可完成', '适合独处']);
  assert.equal(summary.text, '你选择了「活力充电」，这个任务可以覆盖该方向。');
  assert.equal(summary.matchScore, 0.86);
  assert.deepEqual(summary.matchedPreferences, ['分类偏好强', '居家可做']);
  assert.equal(summary.warningText, '预算略高，请确认是否接受。');
  assert.equal(summary.replacementReason, '已避开你之前看过的任务。');
  assert.deepEqual(summary.loadProfile, {
    ease: '很轻松',
    physical: '低体力',
    social: '低社交压力',
    location: '居家',
  });
});

test('taskReasonSummary falls back when backend reason fields are missing', () => {
  const summary = taskReasonSummary({ category: '松弛疗愈' });

  assert.deepEqual(summary.tags, ['覆盖松弛疗愈']);
  assert.equal(summary.text, '该任务覆盖「松弛疗愈」，并已进入当前计划。');
  assert.deepEqual(summary.loadProfile, null);
});

test('recommendationMemorySummary gives users a readable exclusion count', () => {
  assert.equal(recommendationMemorySummary({ excluded_group_count: 2 }), '已为你避开 2 组不喜欢的任务');
  assert.equal(recommendationMemorySummary({ excluded_group_count: 0 }), '');
  assert.equal(recommendationMemorySummary(null), '');
});
