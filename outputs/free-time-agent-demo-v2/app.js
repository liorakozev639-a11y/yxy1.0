(function () {
  var logic = typeof window !== 'undefined' ? window.FreeTimeDemoV2 : require('./logic');
  var STORAGE_KEY = 'free-time-demo-v2:session';
  var STORAGE_VERSION = 'demo-v2-2026-08-01';
  var SCORE_MAP = {
    '非常同意': 4,
    '比较同意': 3,
    '不太同意': 2,
    '完全不同意': 1,
  };

  var CATEGORY_META = {
    energy: { label: '活力充电', hint: '想动起来，给今天一点启动感' },
    calm: { label: '松弛疗愈', hint: '先把节奏放缓，再决定接下来做什么' },
    social: { label: '社交连接', hint: '和人待一会儿，重新接上生活的电流' },
    explore: { label: '乐享探索', hint: '换个画面，给自己一点新鲜感' },
    growth: { label: '自我成长', hint: '做点让今天更有收获的事' },
  };

  var CATEGORIES = Object.keys(CATEGORY_META);
  var CONDITION_GROUPS = {
    duration: [
      { value: 'short', label: '1 小时' },
      { value: 'medium', label: '3 小时' },
      { value: 'half-day', label: '半天' },
    ],
    budget: [
      { value: 'free', label: '0 元' },
      { value: 'low', label: '50 元内' },
      { value: 'medium', label: '200 元内' },
    ],
    outing: [
      { value: 'home', label: '居家' },
      { value: 'near', label: '就近' },
      { value: 'city', label: '全城' },
    ],
    company: [
      { value: 'solo', label: '独处' },
      { value: 'pair', label: '结伴' },
      { value: 'either', label: '都可以' },
    ],
    density: [
      { value: 'light', label: '轻松留白' },
      { value: 'balanced', label: '张弛平衡' },
      { value: 'full', label: '充实一点' },
    ],
  };

  var state = createRuntimeState(logic.createInitialState());
  var app = document.getElementById('app');
  var stageView = document.getElementById('stage-view');
  var stageLabel = document.getElementById('stage-label');
  var stageCount = document.getElementById('stage-count');
  var progressBar = document.getElementById('progress-bar');
  var panelTitle = document.getElementById('stage-panel-title');
  var globalStatus = document.getElementById('global-status');
  var liveRegion = document.getElementById('live-region');
  var modalRoot = document.getElementById('modal-root');
  var stageCards = Array.from(document.querySelectorAll('.stage-card'));

  restoreState();

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function createRuntimeState(baseState) {
    var nextState = clone(baseState || logic.createInitialState());

    nextState.preferences = Object.assign({
      selectedCategories: [],
      mode: 'quick',
      outing: 'near',
      company: 'either',
      budget: 'medium',
      duration: 'half-day',
      density: 'balanced',
      restFirst: false,
      city: '',
      campus: '',
      workStatus: '',
      startMinute: 9 * 60,
      endMinute: 13 * 60,
    }, nextState.preferences || {});

    nextState.questionnaire = Object.assign({
      mode: nextState.preferences.mode === 'deep' ? 'deep' : 'quick',
      questions: [],
      answers: {},
      currentIndex: 0,
      readyToSubmit: false,
    }, nextState.questionnaire || {});

    nextState.candidates = Array.isArray(nextState.candidates) ? nextState.candidates : [];
    nextState.selectedTasks = Array.isArray(nextState.selectedTasks) ? nextState.selectedTasks : [];
    nextState.customTasks = Array.isArray(nextState.customTasks) ? nextState.customTasks : [];
    nextState.schedule = Array.isArray(nextState.schedule) ? nextState.schedule : [];
    nextState.executionState = nextState.executionState && typeof nextState.executionState === 'object'
      ? nextState.executionState
      : {};
    nextState.ui = Object.assign({
      message: '就绪',
      showCustomTaskForm: false,
    }, nextState.ui || {});

    syncTimeWindow(nextState);
    return nextState;
  }

  function syncTimeWindow(targetState) {
    var window = logic.getWindow(targetState.preferences);
    targetState.preferences.startMinute = window.startMinute;
    targetState.preferences.endMinute = window.endMinute;
  }

  function isPlainObject(value) {
    return value !== null && typeof value === 'object' && !Array.isArray(value);
  }

  function isOneOf(value, allowed) {
    return allowed.indexOf(value) >= 0;
  }

  function validateStoredPayload(payload) {
    if (!isPlainObject(payload) || payload.version !== STORAGE_VERSION || !isPlainObject(payload.state)) {
      return false;
    }

    var savedState = payload.state;
    var preferences = savedState.preferences;
    var questionnaire = savedState.questionnaire;

    if (!isOneOf(savedState.stage, logic.stageOrder) || !isPlainObject(preferences) || !isPlainObject(questionnaire)) {
      return false;
    }

    if (!Array.isArray(preferences.selectedCategories) ||
      !preferences.selectedCategories.every(function (category) { return isOneOf(category, CATEGORIES); })) {
      return false;
    }

    if (!isOneOf(preferences.mode, ['quick', 'deep']) ||
      !isOneOf(preferences.outing, ['home', 'near', 'city']) ||
      !isOneOf(preferences.company, ['solo', 'pair', 'either']) ||
      !isOneOf(preferences.budget, ['free', 'low', 'medium']) ||
      !isOneOf(preferences.duration, ['short', 'medium', 'half-day'])) {
      return false;
    }

    if (preferences.density !== undefined && !isOneOf(preferences.density, ['light', 'balanced', 'full'])) {
      return false;
    }

    if (preferences.restFirst !== undefined && typeof preferences.restFirst !== 'boolean') {
      return false;
    }

    if (!isPlainObject(questionnaire.answers)) {
      return false;
    }

    if (questionnaire.currentIndex !== undefined && !Number.isInteger(questionnaire.currentIndex)) {
      return false;
    }

    if (!Array.isArray(savedState.candidates) ||
      !Array.isArray(savedState.selectedTasks) ||
      !Array.isArray(savedState.customTasks) ||
      !Array.isArray(savedState.schedule) ||
      !isPlainObject(savedState.executionState) ||
      !isPlainObject(savedState.ui)) {
      return false;
    }

    return true;
  }

  function restoreState() {
    if (typeof localStorage === 'undefined' || !localStorage) {
      return;
    }

    var raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return;
    }

    try {
      var payload = JSON.parse(raw);
      if (!validateStoredPayload(payload)) {
        throw new Error('invalid-state');
      }
      state = createRuntimeState(payload.state);
      ensureQuestionnaireState();
      setMessage('已恢复上次填写进度。');
    } catch (error) {
      localStorage.removeItem(STORAGE_KEY);
      state = createRuntimeState(logic.createInitialState());
      setMessage('草稿恢复失败，已重新开始。');
    }
  }

  function saveState() {
    if (typeof localStorage === 'undefined' || !localStorage) {
      return;
    }

    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      version: STORAGE_VERSION,
      state: state,
    }));
  }

  function setMessage(message) {
    state.ui.message = message;
  }

  function ensureQuestionnaireState() {
    var mode = state.preferences.mode === 'deep' ? 'deep' : 'quick';
    var questions = logic.createQuestionnaire(mode, state.preferences.selectedCategories);
    var previousAnswers = isPlainObject(state.questionnaire.answers) ? state.questionnaire.answers : {};
    var allowedAnswers = {};

    questions.forEach(function (question) {
      if (Object.prototype.hasOwnProperty.call(previousAnswers, question.id)) {
        allowedAnswers[question.id] = previousAnswers[question.id];
      }
    });

    state.questionnaire = {
      mode: mode,
      questions: questions,
      answers: allowedAnswers,
      currentIndex: normalizeQuestionIndex(state.questionnaire.currentIndex, questions.length),
      readyToSubmit: state.questionnaire.readyToSubmit === true,
    };
  }

  function normalizeQuestionIndex(index, length) {
    if (!length) {
      return 0;
    }
    if (!Number.isInteger(index) || index < 0) {
      return 0;
    }
    if (index >= length) {
      return length - 1;
    }
    return index;
  }

  function buildChoiceButtons(field, options, currentValue) {
    return options.map(function (option) {
      return '<button class="chip-button' + (currentValue === option.value ? ' is-selected' : '') +
        '" type="button" data-action="set-preference" data-field="' + field + '" data-value="' + option.value + '">' +
        option.label + '</button>';
    }).join('');
  }

  function formatTime(minute) {
    var hours = Math.floor(minute / 60);
    var minutes = minute % 60;
    return String(hours).padStart(2, '0') + ':' + String(minutes).padStart(2, '0');
  }

  function getScheduleTaskCount() {
    return state.schedule.filter(function (item) { return item.type === 'task'; }).length;
  }

  function getAdjustmentEntries() {
    return Object.keys(state.executionState).filter(function (taskId) {
      return state.executionState[taskId] && state.executionState[taskId].needsAdjustment;
    });
  }

  function getCurrentQuestion() {
    ensureQuestionnaireState();
    return state.questionnaire.questions[state.questionnaire.currentIndex];
  }

  function buildAnswerScores() {
    ensureQuestionnaireState();
    return state.questionnaire.questions.reduce(function (scores, question) {
      var rawAnswer = state.questionnaire.answers[question.id];
      var mapped = rawAnswer ? SCORE_MAP[rawAnswer] : 2.5;

      if (question.reverse) {
        mapped = 5 - mapped;
      }

      if (!scores[question.category]) {
        scores[question.category] = { total: 0, count: 0 };
      }

      scores[question.category].total += mapped;
      scores[question.category].count += 1;
      return scores;
    }, {});
  }

  function renderWelcomeStage() {
    return [
      '<section class="flow-stack">',
      '<div class="stage-copy">',
      '<p class="eyebrow">开始前</p>',
      '<h4>帮你决定今天适合怎么过</h4>',
      '<p>这是一个无需注册的测试版，会先收集兴趣和前置条件，再给你 10 个本地通用活动候选。</p>',
      '</div>',
      '<div class="button-row">',
      '<button class="button primary" type="button" data-action="go-to-interests">开始选择</button>',
      '</div>',
      '</section>',
    ].join('');
  }

  function renderInterestsStage() {
    var selected = state.preferences.selectedCategories || [];
    return [
      '<section class="flow-stack">',
      '<div class="stage-copy">',
      '<p class="eyebrow">兴趣方向</p>',
      '<h4>先挑一挑今天更想靠近哪几种感觉</h4>',
      '<p>可以多选。已选中的方向会优先影响后面的问卷和推荐顺序。</p>',
      '</div>',
      '<div class="option-grid">',
      CATEGORIES.map(function (category) {
        var active = selected.indexOf(category) >= 0;
        return '<button class="option-card' + (active ? ' is-selected' : '') +
          '" type="button" data-action="toggle-category" data-category="' + category + '">' +
          '<strong>' + CATEGORY_META[category].label + '</strong><span>' + CATEGORY_META[category].hint + '</span></button>';
      }).join(''),
      '</div>',
      '<p class="helper-text">' + (selected.length
        ? '已选择：' + selected.map(function (category) { return CATEGORY_META[category].label; }).join('、')
        : '至少选择一个方向后才能继续。') + '</p>',
      '<div class="button-row">',
      '<button class="button secondary" type="button" data-action="go-to-welcome">返回</button>',
      '<button class="button primary" type="button" data-action="go-to-conditions">继续</button>',
      '</div>',
      '</section>',
    ].join('');
  }

  function renderConditionsStage() {
    return [
      '<section class="flow-stack">',
      '<div class="stage-copy">',
      '<p class="eyebrow">前置条件</p>',
      '<h4>把今天的边界讲清楚一点</h4>',
      '<p>这些条件会直接影响候选活动范围，城市、校园和当前状态都可以留空。</p>',
      '</div>',
      '<div class="condition-grid">',
      '<section class="condition-block"><h5>可用时长</h5><div class="chip-row">' + buildChoiceButtons('duration', CONDITION_GROUPS.duration, state.preferences.duration) + '</div></section>',
      '<section class="condition-block"><h5>预算</h5><div class="chip-row">' + buildChoiceButtons('budget', CONDITION_GROUPS.budget, state.preferences.budget) + '</div></section>',
      '<section class="condition-block"><h5>出行范围</h5><div class="chip-row">' + buildChoiceButtons('outing', CONDITION_GROUPS.outing, state.preferences.outing) + '</div></section>',
      '<section class="condition-block"><h5>同行方式</h5><div class="chip-row">' + buildChoiceButtons('company', CONDITION_GROUPS.company, state.preferences.company) + '</div></section>',
      '<section class="condition-block"><h5>计划密度</h5><div class="chip-row">' + buildChoiceButtons('density', CONDITION_GROUPS.density, state.preferences.density) + '</div></section>',
      '<section class="condition-block"><h5>特殊状态</h5><button class="toggle-card' + (state.preferences.restFirst ? ' is-selected' : '') +
        '" type="button" data-action="toggle-rest">今天只想休息</button></section>',
      '</div>',
      '<div class="field-grid">',
      '<label class="field"><span>城市（选填）</span><input data-field="city" value="' + escapeHtml(state.preferences.city || '') + '" placeholder="例如：上海"></label>',
      '<label class="field"><span>校园（选填）</span><input data-field="campus" value="' + escapeHtml(state.preferences.campus || '') + '" placeholder="例如：邯郸校区"></label>',
      '<label class="field field-wide"><span>当前状态（选填）</span><input data-field="workStatus" value="' + escapeHtml(state.preferences.workStatus || '') + '" placeholder="例如：刚下课 / 刚下班 / 只想慢一点"></label>',
      '</div>',
      '<div class="button-row">',
      '<button class="button secondary" type="button" data-action="go-to-interests">返回</button>',
      '<button class="button primary" type="button" data-action="go-to-questionnaire">进入问卷</button>',
      '</div>',
      '</section>',
    ].join('');
  }

  function renderQuestionnaireStage() {
    ensureQuestionnaireState();
    var total = state.questionnaire.questions.length;
    var current = state.questionnaire.questions[state.questionnaire.currentIndex];
    var answeredCount = Object.keys(state.questionnaire.answers).length;
    var atLastQuestion = state.questionnaire.currentIndex === total - 1;

    return [
      '<section class="flow-stack">',
      '<div class="stage-copy">',
      '<p class="eyebrow">问卷</p>',
      '<h4>一次只看一题，答完后由你决定什么时候生成推荐</h4>',
      '<p>默认 5 题速测，也可以切到 30 题深测。跳过会按中性回答处理。</p>',
      '</div>',
      '<div class="segmented" role="tablist" aria-label="问卷模式">',
      '<button class="segmented-button' + (state.questionnaire.mode === 'quick' ? ' is-selected' : '') +
        '" type="button" data-action="set-mode" data-mode="quick">5 题速测</button>',
      '<button class="segmented-button' + (state.questionnaire.mode === 'deep' ? ' is-selected' : '') +
        '" type="button" data-action="set-mode" data-mode="deep">30 题深测</button>',
      '</div>',
      '<div class="question-card">',
      '<div class="question-meta"><span>第 ' + (state.questionnaire.currentIndex + 1) + ' 题 / ' + total + '</span><span>已记录 ' + answeredCount + ' 题</span></div>',
      '<div class="mini-progress"><span style="width:' + (((state.questionnaire.currentIndex + 1) / total) * 100) + '%"></span></div>',
      '<p class="question-tag">' + CATEGORY_META[current.category].label + '</p>',
      '<h5>' + current.prompt + '</h5>',
      '<div class="answer-list">',
      current.options.map(function (option) {
        var active = state.questionnaire.answers[current.id] === option;
        return '<button class="answer-button' + (active ? ' is-selected' : '') +
          '" type="button" data-action="answer-question" data-value="' + option + '">' + option + '</button>';
      }).join(''),
      '</div>',
      atLastQuestion && state.questionnaire.readyToSubmit
        ? '<p class="helper-text">最后一题已经记录，确认后再生成推荐。</p>'
        : '',
      '</div>',
      '<div class="button-row">',
      '<button class="button secondary" type="button" data-action="prev-question">上一题</button>',
      '<button class="button secondary" type="button" data-action="skip-question">跳过</button>',
      '<button class="button primary" type="button" data-action="submit-questionnaire">生成推荐</button>',
      '</div>',
      '</section>',
    ].join('');
  }

  function renderRecommendations() {
    var selectedIds = new Set(state.selectedTasks.map(function (task) { return task.id; }));

    return [
      '<section class="flow-stack">',
      '<div class="stage-copy">',
      '<p class="eyebrow">推荐结果</p>',
      '<h4>先从候选里挑几项，接着生成今天的时间线</h4>',
      '<p>支持先选、后删，也可以直接在下一步补一个自定义任务。</p>',
      '</div>',
      '<ol class="recommendation-list">',
      state.candidates.map(function (task) {
        var selected = selectedIds.has(task.id);
        return '<li class="recommendation-item">' +
          '<div><strong>' + task.title + '</strong><p>' + task.matchReason + '</p></div>' +
          '<div class="recommendation-meta"><span>' + CATEGORY_META[task.category].label + ' · ' + task.duration + ' 分钟</span>' +
          '<button class="button ' + (selected ? 'secondary' : 'primary') + '" type="button" data-action="toggle-task-selection" data-task-id="' + task.id + '">' +
          (selected ? '移除' : '加入计划') + '</button></div></li>';
      }).join(''),
      '</ol>',
      '<p class="helper-text">已选择 ' + state.selectedTasks.length + ' 项候选。</p>',
      '<div class="button-row">',
      '<button class="button secondary" type="button" data-action="go-to-questionnaire">返回问卷</button>',
      '<button class="button primary" type="button" data-action="go-to-plan">生成排程</button>',
      '</div>',
      '</section>',
    ].join('');
  }

  function renderScheduleList() {
    if (!state.schedule.length) {
      return '<p class="helper-text">还没有时间线，先从上一步挑几个候选。</p>';
    }

    return '<ol class="timeline-list">' + state.schedule.map(function (item) {
      if (item.type === 'rest') {
        return '<li class="timeline-item rest"><div><strong>' + item.title + '</strong><p>留一点空白给休息或切换。</p></div>' +
          '<span>' + formatTime(item.start) + ' - ' + formatTime(item.end) + '</span></li>';
      }

      return '<li class="timeline-item"><div><strong>' + item.title + '</strong><p>' +
        CATEGORY_META[item.category].label + (item.reasonTag ? ' · ' + escapeHtml(item.reasonTag) : '') +
        '</p></div><span>' + formatTime(item.start) + ' - ' + formatTime(item.end) + '</span></li>';
    }).join('') + '</ol>';
  }

  function renderCustomTaskForm() {
    if (!state.ui.showCustomTaskForm) {
      return '';
    }

    return [
      '<section class="custom-task-panel">',
      '<h5>自定义任务</h5>',
      '<p class="helper-text">名称、方向、开始时间、持续时间、预算必填，原因标签可留空。</p>',
      '<div class="field-grid">',
      '<label class="field"><span>名称</span><input data-custom-field="title" value="" placeholder="例如：练琴"></label>',
      '<label class="field"><span>方向</span><select data-custom-field="category">' +
        CATEGORIES.map(function (category) {
          return '<option value="' + category + '">' + CATEGORY_META[category].label + '</option>';
        }).join('') + '</select></label>',
      '<label class="field"><span>开始时间</span><input data-custom-field="start" value="" placeholder="例如：10:30"></label>',
      '<label class="field"><span>持续时间（分钟）</span><input data-custom-field="duration" value="" placeholder="例如：45"></label>',
      '<label class="field"><span>预算</span><select data-custom-field="budget">' +
        CONDITION_GROUPS.budget.map(function (option) {
          return '<option value="' + option.value + '">' + option.label + '</option>';
        }).join('') + '</select></label>',
      '<label class="field"><span>原因标签（选填）</span><input data-custom-field="reasonTag" value="" placeholder="例如：想把练习补上"></label>',
      '</div>',
      '</section>',
    ].join('');
  }

  function renderPlanStage() {
    return [
      '<section class="flow-stack">',
      '<div class="stage-copy">',
      '<p class="eyebrow">计划</p>',
      '<h4>根据你挑的候选，生成 1 到 3 小时或半天时间线</h4>',
      '<p>当前密度：' + CONDITION_GROUPS.density.filter(function (item) { return item.value === state.preferences.density; })[0].label + '。</p>',
      '</div>',
      '<section class="condition-block">',
      '<h5>密度切换</h5>',
      '<div class="chip-row">' + buildChoiceButtons('density', CONDITION_GROUPS.density, state.preferences.density) + '</div>',
      '</section>',
      renderScheduleList(),
      renderCustomTaskForm(),
      '<div class="button-row">',
      '<button class="button secondary" type="button" data-action="open-custom-task">添加自定义任务</button>',
      '<button class="button secondary" type="button" data-action="regenerate-plan">重新排程</button>',
      '<button class="button primary" type="button" data-action="go-to-execution">开始执行</button>',
      '</div>',
      '</section>',
    ].join('');
  }

  function renderExecutionStage() {
    var adjustments = getAdjustmentEntries();
    var taskItems = state.schedule.filter(function (item) { return item.type === 'task'; });

    return [
      '<section class="flow-stack">',
      adjustments.length
        ? '<div class="alert-box"><strong>计划需要调整</strong><p>有任务未开始、跳过或超时，先决定是重排、换一个，还是今天先不做。</p></div>'
        : '',
      '<div class="stage-copy">',
      '<p class="eyebrow">执行</p>',
      '<h4>边做边调，不必一次把今天安排死</h4>',
      '<p>每个任务都支持开始、完成、跳过、换一个和今天先不做。</p>',
      '</div>',
      '<ol class="timeline-list">',
      taskItems.map(function (item) {
        var status = state.executionState[item.taskId] ? state.executionState[item.taskId].status : item.status;
        return '<li class="timeline-item"><div><strong>' + item.title + '</strong><p>' +
          formatTime(item.start) + ' - ' + formatTime(item.end) + ' · 当前状态：' + status +
          '</p></div><div class="action-cluster">' +
          '<button class="button secondary" type="button" data-action="update-task-status" data-task-id="' + item.taskId + '" data-status="in_progress">开始</button>' +
          '<button class="button secondary" type="button" data-action="update-task-status" data-task-id="' + item.taskId + '" data-status="completed">完成</button>' +
          '<button class="button secondary" type="button" data-action="update-task-status" data-task-id="' + item.taskId + '" data-status="skipped">跳过</button>' +
          '<button class="button secondary" type="button" data-action="replace-task" data-task-id="' + item.taskId + '">换一个</button>' +
          '<button class="button secondary" type="button" data-action="pause-task-for-today" data-task-id="' + item.taskId + '">今天先不做</button>' +
          '</div></li>';
      }).join(''),
      '</ol>',
      adjustments.length
        ? '<div class="button-row"><button class="button primary" type="button" data-action="regenerate-plan">立即重排</button></div>'
        : '',
      '</section>',
    ].join('');
  }

  function renderStageBody() {
    if (state.stage === 'welcome') {
      return renderWelcomeStage();
    }
    if (state.stage === 'interests') {
      return renderInterestsStage();
    }
    if (state.stage === 'conditions') {
      return renderConditionsStage();
    }
    if (state.stage === 'questionnaire') {
      return renderQuestionnaireStage();
    }
    if (state.stage === 'recommendations') {
      return renderRecommendations();
    }
    if (state.stage === 'plan') {
      return renderPlanStage();
    }
    if (state.stage === 'execution') {
      return renderExecutionStage();
    }
    return '<p class="helper-text">这个阶段会在后续任务里继续补上。</p>';
  }

  function render() {
    var view = logic.renderStage(state);

    stageLabel.textContent = view.label;
    stageCount.textContent = (view.index + 1) + ' / ' + logic.stageOrder.length;
    progressBar.style.width = Math.max(12.5, view.progress * 100) + '%';
    panelTitle.textContent = view.label;
    globalStatus.textContent = state.ui.message;
    liveRegion.textContent = state.ui.message;
    stageView.innerHTML = renderStageBody();

    if (modalRoot) {
      modalRoot.hidden = true;
      modalRoot.innerHTML = '';
    }

    stageCards.forEach(function (card) {
      card.classList.toggle('is-active', card.dataset.stage === view.stage);
    });
  }

  function moveToStage(nextStage) {
    state.stage = nextStage;
    saveState();
    render();
  }

  function toggleCategory(category) {
    var selected = state.preferences.selectedCategories.slice();
    var index = selected.indexOf(category);

    if (index >= 0) {
      selected.splice(index, 1);
    } else {
      selected.push(category);
    }

    state.preferences.selectedCategories = selected;
    setMessage(selected.length ? '已更新兴趣方向。' : '至少选择一个方向后再继续。');
    saveState();
    render();
  }

  function updatePreference(field, value) {
    state.preferences[field] = value;
    syncTimeWindow(state);

    if (field === 'mode') {
      ensureQuestionnaireState();
    }

    if (field === 'density' && state.stage === 'plan' && state.selectedTasks.length) {
      generatePlan(false);
    }

    setMessage('已保存前置条件。');
    saveState();
    render();
  }

  function setQuestionnaireMode(mode) {
    state.preferences.mode = mode === 'deep' ? 'deep' : 'quick';
    state.questionnaire.readyToSubmit = false;
    ensureQuestionnaireState();
    setMessage(state.preferences.mode === 'deep' ? '已切换到 30 题深测。' : '已切换到 5 题速测。');
    saveState();
    render();
  }

  function advanceQuestionnaire(markReadyOnLast) {
    ensureQuestionnaireState();
    if (state.questionnaire.currentIndex >= state.questionnaire.questions.length - 1) {
      state.questionnaire.readyToSubmit = markReadyOnLast === true;
      setMessage(markReadyOnLast === true ? '最后一题已记录，点生成推荐继续。' : '已停留在最后一题。');
      saveState();
      render();
      return;
    }

    state.questionnaire.currentIndex += 1;
    state.questionnaire.readyToSubmit = false;
    setMessage('已自动保存当前进度。');
    saveState();
    render();
  }

  function answerCurrentQuestion(answer) {
    var question = getCurrentQuestion();
    state.questionnaire.answers[question.id] = answer;
    advanceQuestionnaire(true);
  }

  function skipCurrentQuestion() {
    var question = getCurrentQuestion();
    state.questionnaire.answers[question.id] = null;
    advanceQuestionnaire(false);
  }

  function goPrevQuestion() {
    ensureQuestionnaireState();
    if (state.questionnaire.currentIndex > 0) {
      state.questionnaire.currentIndex -= 1;
      state.questionnaire.readyToSubmit = false;
      setMessage('已回到上一题。');
      saveState();
      render();
      return;
    }
    setMessage('已经是第一题。');
    render();
  }

  function finalizeQuestionnaire() {
    var aggregates = buildAnswerScores();
    var categoryScores = {};
    var result;

    Object.keys(aggregates).forEach(function (category) {
      categoryScores[category] = Number((aggregates[category].total / aggregates[category].count).toFixed(2));
    });

    result = logic.recommendActivities(state.preferences, categoryScores, 10);
    state.candidates = result.tasks;
    state.selectedTasks = [];
    state.schedule = [];
    state.executionState = {};
    state.stage = 'recommendations';
    setMessage(result.tasks.length < 10
      ? '已生成符合硬约束的候选，当前数量不足 10 个。'
      : '已生成 10 个候选活动。');
    saveState();
    render();
  }

  function toggleTaskSelection(taskId) {
    var existing = state.selectedTasks.findIndex(function (task) { return task.id === taskId; });

    if (existing >= 0) {
      state.selectedTasks.splice(existing, 1);
      setMessage('已从计划候选中移除。');
    } else {
      var candidate = state.candidates.find(function (task) { return task.id === taskId; });
      if (!candidate) {
        return;
      }
      state.selectedTasks.push(clone(candidate));
      setMessage('已加入计划候选。');
    }

    saveState();
    render();
  }

  function generatePlan(moveStage) {
    if (!state.selectedTasks.length) {
      setMessage('先至少选一个候选，再生成排程。');
      render();
      return;
    }

    syncTimeWindow(state);
    state.schedule = logic.buildSchedule(state.selectedTasks, state.preferences);
    state.executionState = {};
    if (moveStage !== false) {
      state.stage = 'plan';
    }
    setMessage('已生成时间线。');
    saveState();
    render();
  }

  function goToExecution() {
    if (!state.schedule.length) {
      generatePlan(false);
    }
    state.stage = 'execution';
    setMessage('可以开始，也可以边做边调。');
    saveState();
    render();
  }

  function parseStartInput(value) {
    if (typeof value === 'number') {
      return value;
    }
    if (typeof value !== 'string') {
      return NaN;
    }
    if (/^\d+$/.test(value.trim())) {
      return Number(value.trim());
    }
    var match = value.trim().match(/^(\d{1,2}):(\d{2})$/);
    if (!match) {
      return NaN;
    }
    return Number(match[1]) * 60 + Number(match[2]);
  }

  function addCustomTask(payload) {
    try {
      state = createRuntimeState(logic.addCustomTask(state, {
        title: payload.title,
        category: payload.category,
        start: parseStartInput(payload.start),
        duration: Number(payload.duration),
        budget: payload.budget,
        reasonTag: payload.reasonTag || '',
      }));
      state.ui.showCustomTaskForm = false;
      setMessage('已加入自定义任务。');
      saveState();
      render();
    } catch (error) {
      setMessage(error.message || '自定义任务保存失败。');
      render();
    }
  }

  function updateTaskStatus(taskId, status) {
    state = createRuntimeState(logic.updateTaskStatus(state, taskId, status));
    state.stage = 'execution';
    saveState();
    render();
  }

  function replaceTask(taskId) {
    var usedIds = new Set(state.selectedTasks.map(function (task) { return task.id; }));
    var replacement = state.candidates.find(function (task) { return !usedIds.has(task.id); });
    var selectedIndex = state.selectedTasks.findIndex(function (task) { return task.id === taskId; });

    if (!replacement || selectedIndex < 0) {
      setMessage('暂时没有别的候选可以替换。');
      render();
      return;
    }

    state.selectedTasks[selectedIndex] = clone(replacement);
    generatePlan(false);
    state = createRuntimeState(logic.updateTaskStatus(state, replacement.id, 'pending'));
    state.stage = 'execution';
    setMessage('已换一个任务，并重新排程。');
    saveState();
    render();
  }

  function pauseTaskForToday(taskId) {
    updateTaskStatus(taskId, 'paused');
  }

  function handleAction(action, payload) {
    payload = payload || {};

    if (action === 'reset') {
      resetDemo();
      return;
    }
    if (action === 'go-to-welcome') {
      moveToStage('welcome');
      return;
    }
    if (action === 'go-to-interests') {
      moveToStage('interests');
      return;
    }
    if (action === 'go-to-conditions') {
      if (!state.preferences.selectedCategories.length) {
        setMessage('先选至少一个兴趣方向。');
        render();
        return;
      }
      moveToStage('conditions');
      return;
    }
    if (action === 'go-to-questionnaire') {
      if (!state.preferences.selectedCategories.length) {
        setMessage('先选至少一个兴趣方向。');
        render();
        return;
      }
      ensureQuestionnaireState();
      moveToStage('questionnaire');
      return;
    }
    if (action === 'toggle-category') {
      toggleCategory(payload.category);
      return;
    }
    if (action === 'set-preference') {
      updatePreference(payload.field, payload.value);
      return;
    }
    if (action === 'toggle-rest') {
      updatePreference('restFirst', !state.preferences.restFirst);
      return;
    }
    if (action === 'set-mode') {
      setQuestionnaireMode(payload.mode);
      return;
    }
    if (action === 'answer-question') {
      answerCurrentQuestion(payload.value);
      return;
    }
    if (action === 'skip-question') {
      skipCurrentQuestion();
      return;
    }
    if (action === 'prev-question') {
      goPrevQuestion();
      return;
    }
    if (action === 'submit-questionnaire') {
      finalizeQuestionnaire();
      return;
    }
    if (action === 'toggle-task-selection') {
      toggleTaskSelection(payload.taskId);
      return;
    }
    if (action === 'go-to-plan') {
      generatePlan(true);
      return;
    }
    if (action === 'go-to-execution') {
      goToExecution();
      return;
    }
    if (action === 'open-custom-task') {
      state.ui.showCustomTaskForm = true;
      setMessage('可以补一个自定义任务。');
      saveState();
      render();
      return;
    }
    if (action === 'add-custom-task') {
      addCustomTask(payload);
      return;
    }
    if (action === 'regenerate-plan') {
      generatePlan(false);
      state.stage = getAdjustmentEntries().length ? 'execution' : 'plan';
      saveState();
      render();
      return;
    }
    if (action === 'update-task-status') {
      updateTaskStatus(payload.taskId, payload.status);
      return;
    }
    if (action === 'replace-task') {
      replaceTask(payload.taskId);
      return;
    }
    if (action === 'pause-task-for-today') {
      pauseTaskForToday(payload.taskId);
    }
  }

  function resetDemo() {
    state = createRuntimeState(logic.resetDemo());
    if (typeof localStorage !== 'undefined' && localStorage) {
      localStorage.removeItem(STORAGE_KEY);
    }
    setMessage('已重新开始。');
    render();
  }

  if (app) {
    app.addEventListener('click', function (event) {
      var control = event.target.closest('[data-action]');
      if (!control) {
        return;
      }

      handleAction(control.dataset.action, {
        category: control.dataset.category,
        field: control.dataset.field,
        value: control.dataset.value,
        mode: control.dataset.mode,
        taskId: control.dataset.taskId,
        status: control.dataset.status,
      });
    });

    app.addEventListener('input', function (event) {
      var field = event.target.dataset && event.target.dataset.field;
      if (!field) {
        return;
      }
      updatePreference(field, event.target.value);
    });
  }

  if (typeof window !== 'undefined') {
    window.FreeTimeDemoV2 = Object.assign({}, logic, {
      getState: function () {
        return clone(state);
      },
      getStorageKey: function () {
        return STORAGE_KEY;
      },
      handleAction: function (action, payload) {
        handleAction(action, payload || {});
      },
      toggleCategory: toggleCategory,
      updatePreference: updatePreference,
      setQuestionnaireMode: setQuestionnaireMode,
      answerCurrentQuestion: answerCurrentQuestion,
      skipCurrentQuestion: skipCurrentQuestion,
      goPrevQuestion: goPrevQuestion,
      resetDemo: resetDemo,
      addCustomTask: addCustomTask,
    });
  }

  render();
}());
