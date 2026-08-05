const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.join(__dirname, '..', 'outputs', 'free-time-agent-demo-v2');
const logic = require(path.join(root, 'logic.js'));

class FakeElement {
  constructor(id, dataset) {
    this.id = id || null;
    this.dataset = dataset || {};
    this.innerHTML = '';
    this.textContent = '';
    this.hidden = false;
    this.style = {};
    this.value = '';
    this.listeners = {};
    this.classList = {
      toggle: () => {},
    };
  }

  addEventListener(type, handler) {
    this.listeners[type] = handler;
  }

  closest() {
    return this;
  }
}

function createStorage(initial) {
  const store = Object.assign({}, initial);
  return {
    getItem(key) {
      return Object.prototype.hasOwnProperty.call(store, key) ? store[key] : null;
    },
    setItem(key, value) {
      store[key] = String(value);
    },
    removeItem(key) {
      delete store[key];
    },
  };
}

function bootDemo() {
  const elements = {
    app: new FakeElement('app'),
    'stage-view': new FakeElement('stage-view'),
    'stage-label': new FakeElement('stage-label'),
    'stage-count': new FakeElement('stage-count'),
    'progress-bar': new FakeElement('progress-bar'),
    'stage-panel-title': new FakeElement('stage-panel-title'),
    'global-status': new FakeElement('global-status'),
    'live-region': new FakeElement('live-region'),
    'modal-root': new FakeElement('modal-root'),
  };

  const stageCards = [
    'welcome',
    'interests',
    'conditions',
    'questionnaire',
    'recommendations',
    'plan',
    'execution',
    'summary',
  ].map((stage) => new FakeElement(null, { stage }));

  const context = {
    window: {},
    document: {
      getElementById(id) {
        return elements[id] || null;
      },
      querySelectorAll(selector) {
        if (selector === '.stage-card') {
          return stageCards;
        }
        return [];
      },
    },
    localStorage: createStorage(),
    console,
    setTimeout,
    clearTimeout,
  };

  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(root, 'logic.js'), 'utf8'), context, { filename: 'logic.js' });
  vm.runInContext(fs.readFileSync(path.join(root, 'app.js'), 'utf8'), context, { filename: 'app.js' });

  return {
    demo: context.window.FreeTimeDemoV2,
    elements,
  };
}

test('validateTimeWindow rejects overlap and out-of-window custom tasks', () => {
  const overlap = logic.validateTimeWindow(
    { start: 10 * 60, duration: 60 },
    [{ start: 10 * 60, end: 11 * 60 }],
    { startMinute: 9 * 60, endMinute: 18 * 60 },
  );
  const outOfWindow = logic.validateTimeWindow(
    { start: 17 * 60 + 30, duration: 90 },
    [],
    { startMinute: 9 * 60, endMinute: 18 * 60 },
  );

  assert.equal(overlap.valid, false);
  assert.match(overlap.message || '', /冲突|重叠|overlap/i);
  assert.equal(outOfWindow.valid, false);
  assert.match(outOfWindow.message || '', /可用|时段|window/i);
});

test('buildSchedule respects density tiers and includes a rest block for light mode', () => {
  const tasks = logic.recommendActivities(
    {
      selectedCategories: ['calm', 'growth'],
      outing: 'home',
      company: 'solo',
      budget: 'medium',
      duration: 'half-day',
      density: 'balanced',
      restFirst: true,
    },
    {},
    6,
  ).tasks;

  const light = logic.buildSchedule(tasks, {
    density: 'light',
    restFirst: true,
    startMinute: 9 * 60,
    endMinute: 15 * 60,
  });
  const balanced = logic.buildSchedule(tasks, {
    density: 'balanced',
    restFirst: true,
    startMinute: 9 * 60,
    endMinute: 15 * 60,
  });
  const full = logic.buildSchedule(tasks, {
    density: 'full',
    restFirst: false,
    startMinute: 9 * 60,
    endMinute: 15 * 60,
  });

  assert.equal(light.some((item) => item.type === 'rest'), true);
  assert.ok(light.filter((item) => item.type === 'task').length <= balanced.filter((item) => item.type === 'task').length);
  assert.ok(full.filter((item) => item.type === 'task').length >= balanced.filter((item) => item.type === 'task').length);
  assert.ok(full.every((item) => item.start >= 9 * 60 && item.end <= 15 * 60));
});

test('addCustomTask accepts empty optional reason and updateTaskStatus records execution state', () => {
  const base = logic.createInitialState();
  base.schedule = [
    { taskId: 'task-1', start: 9 * 60, end: 10 * 60, type: 'task', status: 'pending' },
  ];
  base.preferences.startMinute = 9 * 60;
  base.preferences.endMinute = 18 * 60;

  const withCustom = logic.addCustomTask(base, {
    title: '自定义练琴',
    category: 'growth',
    start: 10 * 60 + 30,
    duration: 45,
    budget: 'free',
    reasonTag: '',
  });
  const customTask = withCustom.customTasks[0];
  const updated = logic.updateTaskStatus(withCustom, 'task-1', 'missed');

  assert.equal(withCustom.customTasks.length, 1);
  assert.equal(customTask.reasonTag, '');
  assert.equal(withCustom.schedule.some((item) => item.taskId === customTask.id), true);
  assert.equal(updated.executionState['task-1'].status, 'missed');
  assert.equal(updated.executionState['task-1'].needsAdjustment, true);
});

test('app flows from recommendations into plan and exposes adjustment actions after a missed task', () => {
  const { demo, elements } = bootDemo();
  const scale = demo.createQuestionnaire('quick', ['calm'])[0].options;

  demo.handleAction('go-to-interests');
  demo.toggleCategory('calm');
  demo.toggleCategory('growth');
  demo.handleAction('go-to-conditions');
  demo.updatePreference('duration', 'half-day');
  demo.updatePreference('budget', 'medium');
  demo.updatePreference('outing', 'home');
  demo.updatePreference('company', 'solo');
  demo.updatePreference('density', 'light');
  demo.updatePreference('restFirst', true);
  demo.handleAction('go-to-questionnaire');

  for (let index = 0; index < demo.getState().questionnaire.questions.length; index += 1) {
    demo.answerCurrentQuestion(scale[0]);
  }

  demo.handleAction('submit-questionnaire');
  assert.equal(demo.getState().stage, 'recommendations');

  demo.handleAction('toggle-task-selection', { taskId: demo.getState().candidates[0].id });
  demo.handleAction('toggle-task-selection', { taskId: demo.getState().candidates[1].id });
  demo.handleAction('go-to-plan');

  assert.equal(demo.getState().stage, 'plan');
  assert.ok(demo.getState().schedule.length > 0);
  assert.match(elements['stage-view'].innerHTML, /data-action="open-custom-task"/);

  const firstTask = demo.getState().schedule.find((item) => item.type === 'task');
  demo.handleAction('update-task-status', { taskId: firstTask.taskId, status: 'missed' });

  assert.equal(demo.getState().executionState[firstTask.taskId].needsAdjustment, true);
  assert.equal(demo.getState().stage, 'execution');
  assert.match(elements['stage-view'].innerHTML, /计划需要调整/);
  assert.match(elements['stage-view'].innerHTML, /data-action="replace-task"/);
  assert.match(elements['stage-view'].innerHTML, /data-action="pause-task-for-today"/);
});
