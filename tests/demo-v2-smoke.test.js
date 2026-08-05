const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const root = path.join(__dirname, '..', 'outputs', 'free-time-agent-demo-v2');
const frontendRoot = path.join(__dirname, '..', 'frontend');
const demoLogic = require(path.join(root, 'logic.js'));

test('demo v2 has an independent runnable bundle and runtime contract', () => {
  const files = ['index.html', 'styles.css', 'app.js', 'logic.js'];

  for (const file of files) {
    assert.equal(fs.existsSync(path.join(root, file)), true, `${file} should exist`);
  }

  const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
  assert.match(html, /<main[^>]*id="app"/);
  assert.match(html, /<div id="modal-root" hidden><\/div>/);
  assert.match(html, /<script src="logic\.js"><\/script>/);
  assert.match(html, /<script src="app\.js"><\/script>/);

  const source = fs.readFileSync(path.join(root, 'logic.js'), 'utf8');
  assert.match(source, /createInitialState/);
  assert.match(source, /createQuestionnaire/);
  assert.match(source, /renderStage/);
  assert.match(source, /resetDemo/);
  assert.match(source, /getActivityLibrary/);
  assert.match(source, /filterActivities/);
  assert.match(source, /recommendActivities/);
  assert.match(source, /buildSchedule/);
  assert.match(source, /validateTimeWindow/);
  assert.match(source, /addCustomTask/);
  assert.match(source, /updateTaskStatus/);

  const app = fs.readFileSync(path.join(root, 'app.js'), 'utf8');
  assert.match(app, /window\.FreeTimeDemoV2/);

  assert.deepEqual(Object.keys(demoLogic).sort(), [
    'addCustomTask',
    'buildSchedule',
    'createInitialState',
    'createQuestionnaire',
    'filterActivities',
    'getActivityLibrary',
    'getWindow',
    'recommendActivities',
    'renderStage',
    'resetDemo',
    'stageOrder',
    'updateTaskStatus',
    'validateTimeWindow',
  ]);

  const initialState = demoLogic.createInitialState();
  assert.equal(initialState.stage, 'welcome');
  assert.deepEqual(initialState.preferences, {
    selectedCategories: [],
    mode: 'quick',
    outing: 'near',
    company: 'either',
    budget: 'medium',
    duration: 'half-day',
    density: 'balanced',
    restFirst: false,
    startMinute: 9 * 60,
    endMinute: 13 * 60,
  });
  assert.deepEqual(initialState.questionnaire, {
    answers: {},
  });
  assert.deepEqual(initialState.candidates, []);
  assert.deepEqual(initialState.selectedTasks, []);
  assert.deepEqual(initialState.customTasks, []);
  assert.deepEqual(initialState.schedule, []);
  assert.deepEqual(initialState.executionState, {});
  assert.deepEqual(initialState.ui, {
    message: '就绪',
  });

  const welcomeStage = demoLogic.renderStage(initialState);
  assert.equal(welcomeStage.stage, 'welcome');
  assert.equal(welcomeStage.label, '欢迎');
  assert.equal(welcomeStage.index, 0);
  assert.equal(welcomeStage.progress, 1 / 8);
  assert.match(welcomeStage.copy, /Demo V2/);

  const library = demoLogic.getActivityLibrary();
  assert.ok(Array.isArray(library));
  assert.ok(library.length >= 16);
});

test('canonical frontend loads the API client before the questionnaire app', () => {
  const html = fs.readFileSync(path.join(frontendRoot, 'index.html'), 'utf8');
  const app = fs.readFileSync(path.join(frontendRoot, 'app.js'), 'utf8');

  assert.ok(html.indexOf('<script src="api.js"></script>') >= 0);
  assert.ok(
    html.indexOf('<script src="api.js"></script>')
      < html.indexOf('<script src="app.js"></script>'),
  );
  assert.match(app, /booting/);
  assert.match(app, /data-mode="quick"/);
  assert.match(app, /data-mode="deep"/);
  assert.doesNotMatch(app, /buildCandidates|buildSchedule|show-candidates|build-plan/);
});
