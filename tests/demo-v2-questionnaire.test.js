const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.join(__dirname, '..', 'outputs', 'free-time-agent-demo-v2');
const logic = require(path.join(root, 'logic.js'));

const FIXED_SCALE = logic.createQuestionnaire('quick', ['energy'])[0].options;

class FakeElement {
  constructor(id, dataset) {
    this.id = id || null;
    this.dataset = dataset || {};
    this.innerHTML = '';
    this.textContent = '';
    this.hidden = false;
    this.style = {};
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
    dump() {
      return Object.assign({}, store);
    },
  };
}

function bootDemo(storageSeed) {
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

  const storage = createStorage(storageSeed);
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
    localStorage: storage,
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
    storage,
  };
}

test('quick mode creates five questions across the five directions', () => {
  const questions = logic.createQuestionnaire('quick', ['energy', 'growth']);

  assert.equal(questions.length, 5);
  assert.deepEqual(new Set(questions.map((question) => question.category)), new Set([
    'energy',
    'calm',
    'social',
    'explore',
    'growth',
  ]));
  questions.forEach((question) => {
    assert.deepEqual(question.options, FIXED_SCALE);
    assert.equal(typeof question.reverse, 'boolean');
  });
});

test('deep mode creates thirty questions with the fixed four-level scale', () => {
  const questions = logic.createQuestionnaire('deep', ['energy']);

  assert.equal(questions.length, 30);
  assert.deepEqual(questions[0].options, FIXED_SCALE);
  assert.equal(questions.every((question) => question.options.join('|') === FIXED_SCALE.join('|')), true);
  assert.equal(questions.some((question) => question.reverse === true), true);
});

test('app requires explicit submit before entering recommendations and keeps hard constraints intact', () => {
  const { demo, elements } = bootDemo();

  assert.equal(demo.getState().stage, 'welcome');
  assert.match(elements['stage-view'].innerHTML, /data-action="go-to-interests"/);

  demo.handleAction('go-to-interests');
  demo.toggleCategory('energy');
  demo.toggleCategory('calm');
  demo.handleAction('go-to-conditions');
  demo.updatePreference('duration', 'half-day');
  demo.updatePreference('budget', 'free');
  demo.updatePreference('outing', 'home');
  demo.updatePreference('company', 'solo');
  demo.updatePreference('density', 'balanced');
  demo.updatePreference('restFirst', true);
  demo.handleAction('go-to-questionnaire');

  assert.equal(demo.getState().stage, 'questionnaire');
  assert.equal(demo.getState().questionnaire.questions.length, 5);

  demo.answerCurrentQuestion(FIXED_SCALE[0]);
  demo.skipCurrentQuestion();
  demo.goPrevQuestion();
  demo.setQuestionnaireMode('deep');

  assert.equal(demo.getState().questionnaire.mode, 'deep');
  assert.equal(demo.getState().questionnaire.questions.length, 30);

  while (demo.getState().questionnaire.currentIndex < demo.getState().questionnaire.questions.length - 1) {
    demo.skipCurrentQuestion();
  }

  assert.equal(demo.getState().stage, 'questionnaire');
  assert.match(elements['stage-view'].innerHTML, /data-action="submit-questionnaire"/);

  demo.skipCurrentQuestion();

  assert.equal(demo.getState().stage, 'questionnaire');
  assert.equal(
    demo.getState().questionnaire.currentIndex,
    demo.getState().questionnaire.questions.length - 1,
  );

  demo.handleAction('submit-questionnaire');

  assert.equal(demo.getState().stage, 'recommendations');
  assert.equal(demo.getState().candidates.length < 10, true);
  assert.equal(demo.getState().candidates.every((task) => task.mode === 'home'), true);
  assert.equal(demo.getState().candidates.every((task) => task.company !== 'pair'), true);
  assert.equal(demo.getState().candidates.every((task) => task.budget === 'free'), true);
  assert.match(elements['stage-view'].innerHTML, /recommendation-list/);
});

test('app autosaves versioned state, restores it after reload, and clears only its own key when corrupted', () => {
  const first = bootDemo();
  const storageKey = first.demo.getStorageKey();

  first.demo.handleAction('go-to-interests');
  first.demo.toggleCategory('social');
  first.demo.handleAction('go-to-conditions');
  first.demo.updatePreference('city', '涓婃捣');

  const saved = first.storage.dump();
  assert.ok(saved[storageKey]);
  assert.equal(JSON.parse(saved[storageKey]).version.startsWith('demo-v2'), true);

  const restored = bootDemo(saved);
  assert.equal(restored.demo.getState().stage, 'conditions');
  assert.deepEqual(Array.from(restored.demo.getState().preferences.selectedCategories), ['social']);
  assert.equal(restored.demo.getState().preferences.city, '涓婃捣');

  const corruptedSeed = {};
  corruptedSeed[storageKey] = '{';
  corruptedSeed.unrelated = 'keep-me';

  const recovered = bootDemo(corruptedSeed);
  assert.equal(recovered.storage.getItem(storageKey), null);
  assert.equal(recovered.storage.getItem('unrelated'), 'keep-me');
  assert.equal(recovered.demo.getState().stage, 'welcome');
  assert.match(recovered.elements['global-status'].textContent, /草稿恢复失败|重新开始/);
});

test('app clears its storage key when saved JSON is structurally invalid', () => {
  const probe = bootDemo();
  const storageKey = probe.demo.getStorageKey();
  const malformedSeed = {
    unrelated: 'keep-me',
  };

  malformedSeed[storageKey] = JSON.stringify({
    version: 'demo-v2-2026-08-01',
    state: {
      stage: 'questionnaire',
      preferences: {
        selectedCategories: 'social',
        mode: 'weird',
        outing: 'near',
        company: 'either',
        budget: 'medium',
        duration: 'half-day',
        restFirst: false,
      },
      questionnaire: {
        answers: [],
        currentIndex: '2',
      },
      candidates: [],
      selectedTasks: [],
      customTasks: [],
      schedule: [],
      executionState: {},
      ui: {
        message: 'bad',
      },
    },
  });

  const recovered = bootDemo(malformedSeed);
  assert.equal(recovered.storage.getItem(storageKey), null);
  assert.equal(recovered.storage.getItem('unrelated'), 'keep-me');
  assert.equal(recovered.demo.getState().stage, 'welcome');
  assert.match(recovered.elements['global-status'].textContent, /草稿恢复失败|重新开始/);
});
