const assert = require('node:assert/strict');
const test = require('node:test');

const { STORAGE_KEY, USER_STORAGE_KEY, createApi } = require('../frontend/api.js');

function createStorage() {
  const values = new Map();
  return {
    getItem(key) { return values.has(key) ? values.get(key) : null; },
    setItem(key, value) { values.set(key, String(value)); },
    removeItem(key) { values.delete(key); },
    keys() { return [...values.keys()]; },
  };
}

function jsonResponse(data, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    async json() { return data; },
  };
}

test('createSession stores only the session id and sends no authorization', async () => {
  const calls = [];
  const storage = createStorage();
  const api = createApi({
    storage,
    fetchImpl: async (url, options) => {
      calls.push({ url, options });
      return jsonResponse({
        data: { session_id: 'sess_test', stage: 'interests' },
        error: null,
      }, 201);
    },
  });

  const result = await api.createSession();

  assert.equal(result.session_id, 'sess_test');
  assert.equal(storage.getItem(STORAGE_KEY), 'sess_test');
  assert.deepEqual(storage.keys(), [STORAGE_KEY]);
  assert.equal(calls[0].url, 'http://127.0.0.1:8000/api/v1/sessions');
  assert.equal(calls[0].options.method, 'POST');
  assert.equal('Authorization' in calls[0].options.headers, false);
});

test('questionnaire methods use the unified API contract', async () => {
  const calls = [];
  const storage = createStorage();
  storage.setItem(STORAGE_KEY, 'sess_test');
  const api = createApi({
    storage,
    baseUrl: 'http://localhost:9000/',
    fetchImpl: async (url, options) => {
      calls.push({ url, options });
      return jsonResponse({ data: { saved: true }, error: null });
    },
  });

  await api.savePreferences({ categories: ['energy'] });
  await api.startQuestionnaire('quick');
  await api.saveAnswer('q_energy', 4);
  await api.skipQuestion('q_rest');
  await api.getProgress();
  await api.submitQuestionnaire();
  await api.getProfileInsight();
  await api.generatePlan({
    free_start: '2026-08-09T10:00:00Z',
    free_end: '2026-08-09T14:00:00Z',
    density: 'balanced',
  });
  await api.getPlan();

  assert.deepEqual(calls.map((call) => call.options.method), [
    'PUT', 'POST', 'PATCH', 'POST', 'GET', 'POST', 'GET', 'POST', 'GET',
  ]);
  assert.ok(calls.every((call) => call.url.startsWith('http://localhost:9000/api/v1/sessions/sess_test/')));
  assert.ok(calls.every((call) => !('Authorization' in call.options.headers)));
});

test('recommended task methods add a task to an existing plan', async () => {
  const calls = [];
  const storage = createStorage();
  const api = createApi({
    storage,
    fetchImpl: async (url, options) => {
      calls.push({ url, options });
      return jsonResponse({ data: { plan_id: 'plan_1', version: 2 }, error: null });
    },
  });

  await api.addRecommendedTask('plan_1', 'task_energy_01', { expected_version: 1 });

  assert.equal(calls[0].url, 'http://127.0.0.1:8000/api/v1/plans/plan_1/recommended-tasks/task_energy_01');
  assert.equal(calls[0].options.method, 'POST');
  assert.deepEqual(JSON.parse(calls[0].options.body), { expected_version: 1 });
});

test('API errors preserve status and backend message', async () => {
  const api = createApi({
    storage: createStorage(),
    fetchImpl: async () => jsonResponse({
      data: null,
      error: { code: 'session_not_found', message: '会话不存在' },
    }, 404),
  });

  await assert.rejects(
    api.restoreSession('sess_missing'),
    (error) => error.status === 404
      && error.code === 'session_not_found'
      && error.message === '会话不存在',
  );
});

test('health methods expose API and database status endpoints', async () => {
  const calls = [];
  const api = createApi({
    storage: createStorage(),
    fetchImpl: async (url, options) => {
      calls.push({ url, options });
      return jsonResponse({ data: { status: 'ok' }, error: null });
    },
  });

  await api.getHealth();
  await api.getDatabaseHealth();

  assert.equal(calls[0].url, 'http://127.0.0.1:8000/health');
  assert.equal(calls[1].url, 'http://127.0.0.1:8000/api/v1/health/database');
  assert.deepEqual(calls.map((call) => call.options.method), ['GET', 'GET']);
});

test('network failures become actionable Chinese messages', async () => {
  const api = createApi({
    storage: createStorage(),
    fetchImpl: async () => {
      throw new TypeError('Failed to fetch');
    },
  });

  await assert.rejects(
    api.getHealth(),
    (error) => error.code === 'service_unreachable'
      && error.message === '本地后端服务未启动，请先启动后端',
  );
});

test('ensureAnonymousUser creates and persists the anonymous user id', async () => {
  const calls = [];
  const storage = createStorage();
  const api = createApi({
    storage,
    fetchImpl: async (url, options) => {
      calls.push({ url, options });
      return jsonResponse({ data: { user_id: 'user_001', created: true }, error: null });
    },
  });

  const user = await api.ensureAnonymousUser();

  assert.equal(user.user_id, 'user_001');
  assert.equal(storage.getItem(USER_STORAGE_KEY), 'user_001');
  assert.equal(calls[0].url, 'http://127.0.0.1:8000/api/v1/users/anonymous');
  assert.deepEqual(JSON.parse(calls[0].options.body), {});
});

test('ensureAnonymousUser reuses the persisted id and execution preparation routes', async () => {
  const calls = [];
  const storage = createStorage();
  storage.setItem(USER_STORAGE_KEY, 'user_existing');
  const api = createApi({
    storage,
    fetchImpl: async (url, options) => {
      calls.push({ url, options });
      return jsonResponse({ data: { user_id: 'user_existing' }, error: null });
    },
  });

  await api.ensureAnonymousUser();
  await api.prepareExecution('plan_1', 'item_1', { energy: 'low', user_id: 'user_1' });
  await api.replacePlanItemEasier('plan_1', 'item_1', { expected_version: 2, user_id: 'user_1' });

  assert.deepEqual(JSON.parse(calls[0].options.body), { user_id: 'user_existing' });
  assert.equal(calls[1].url, 'http://127.0.0.1:8000/api/v1/plans/plan_1/items/item_1/execution/prepare');
  assert.equal(calls[2].url, 'http://127.0.0.1:8000/api/v1/plans/plan_1/items/item_1/replace-easier');
});
