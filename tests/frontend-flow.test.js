const assert = require('node:assert/strict');
const test = require('node:test');

const {
  firstUnansweredIndex,
  recoverInitialization,
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
