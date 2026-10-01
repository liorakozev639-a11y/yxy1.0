const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const {
  ADMIN_TOKEN_STORAGE_KEY,
  TEST_ANONYMOUS_ID_KEY,
  createApi,
} = require('../frontend/api.js');

function storage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem(key) { return values.has(key) ? values.get(key) : null; },
    setItem(key, value) { values.set(key, String(value)); },
    removeItem(key) { values.delete(key); },
  };
}

function response(data, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    async json() { return { data, error: null }; },
  };
}

test('testing API persists anonymous identity and posts observation feedback', async () => {
  const calls = [];
  const store = storage({ [TEST_ANONYMOUS_ID_KEY]: 'student_001' });
  const api = createApi({
    storage: store,
    fetchImpl: async (url, options) => {
      calls.push({ url, options });
      return response({ token: 'admin-token', recorded: true });
    },
  });

  assert.equal(api.getTestAnonymousId(), 'student_001');

  await api.identifyTestUser('student_001', 'student_2026_09');
  await api.recordTestEvent({
    anonymous_id: 'student_001',
    event_type: 'task_completed',
    session_id: 'sess_1',
    idempotency_key: 'task_completed:sess_1:item_1',
  });
  await api.saveTestFeedback({
    anonymous_id: 'student_001',
    session_id: 'sess_1',
    plan_item_id: 'item_1',
    rating: 5,
    comment: '很好开始',
  });

  assert.deepEqual(calls.map(({ url, options }) => [url, options.method]), [
    ['http://127.0.0.1:8000/api/v1/test-users/identify', 'POST'],
    ['http://127.0.0.1:8000/api/v1/test-events', 'POST'],
    ['http://127.0.0.1:8000/api/v1/test-feedback', 'POST'],
  ]);
  assert.equal(JSON.parse(calls[2].options.body).comment, '很好开始');
});

test('testing identity is generated once and reused from localStorage', () => {
  const store = storage();
  const api = createApi({ storage: store, fetchImpl: async () => response({}) });
  const first = api.getTestAnonymousId();
  const second = api.getTestAnonymousId();

  assert.match(first, /^student_\d{6}$/);
  assert.equal(second, first);
  assert.equal(store.getItem(TEST_ANONYMOUS_ID_KEY), first);
});

test('admin login stores token and metric requests send filters without user state', async () => {
  const calls = [];
  const store = storage({ [TEST_ANONYMOUS_ID_KEY]: 'student_002' });
  const api = createApi({
    storage: store,
    fetchImpl: async (url, options) => {
      calls.push({ url, options });
      return response(url.endsWith('/login')
        ? { token: 'admin-token', expires_at: '2026-10-01T12:00:00Z' }
        : { user_count: 2 });
    },
  });

  await api.adminLogin('admin', 'secret');
  await api.adminMetrics('summary', {
    from: '2026-09-01',
    to: '2026-09-30',
    cohort: 'student_2026_09',
    anonymous_id: 'student_002',
  });

  assert.equal(store.getItem(ADMIN_TOKEN_STORAGE_KEY), 'admin-token');
  assert.match(calls[1].url, /\/api\/v1\/admin\/metrics\/summary\?/);
  assert.match(calls[1].url, /anonymous_id=student_002/);
  assert.equal(calls[1].options.headers.Authorization, 'Bearer admin-token');
  assert.equal(store.getItem(TEST_ANONYMOUS_ID_KEY), 'student_002');
});

test('frontend wires success-only telemetry and swallows telemetry failures', () => {
  const app = fs.readFileSync(path.join(__dirname, '..', 'frontend', 'app.js'), 'utf8');
  assert.match(app, /mvp_test_anonymous_id/);
  assert.match(app, /function reportTestEvent\(/);
  assert.match(app, /console\.debug\(/);
  for (const eventType of [
    'session_created',
    'questionnaire_started',
    'questionnaire_completed',
    'recommendations_viewed',
    'task_started',
    'task_completed',
    'task_skipped',
    'task_replaced',
    'feedback_submitted',
  ]) {
    assert.match(app, new RegExp(eventType));
  }
  assert.match(app, /saveTestFeedback/);
  assert.match(app, /reason_code/);
});

test('admin dashboard is isolated and requests all required metric views', () => {
  const frontendDir = path.join(__dirname, '..', 'frontend');
  const html = fs.readFileSync(path.join(frontendDir, 'admin.html'), 'utf8');
  const js = fs.readFileSync(path.join(frontendDir, 'admin.js'), 'utf8');
  const css = fs.readFileSync(path.join(frontendDir, 'admin.css'), 'utf8');

  assert.match(html, /admin\.js/);
  assert.match(html, /admin\.css/);
  assert.match(html, /admin-login/);
  assert.match(html, /anonymous_id/);
  assert.match(js, /adminLogin/);
  for (const view of ['summary', 'funnel', 'recommendations', 'reasons', 'errors']) {
    assert.match(js, new RegExp(`adminMetrics\\(['"]${view}['"]`));
  }
  for (const filter of ['from', 'cohort', 'anonymous_id', 'task_category']) {
    assert.match(html, new RegExp(filter));
  }
  assert.match(js, /FormData\(filterForm\)/);
  assert.match(html, /个人|identity|姓名/);
  assert.match(css, /@media/);
});
