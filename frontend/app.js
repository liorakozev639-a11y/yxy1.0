(function () {
  const api = window.FreeTimeApi;
  const flow = window.FreeTimeFlow;
  const app = document.querySelector('.app-shell');
  const toast = document.querySelector('#toast');
  const categories = [
    { id: 'energy', name: '活力充电', description: '运动、走动与身体恢复', icon: 'activity' },
    { id: 'calm', name: '松弛疗愈', description: '减压、休息与情绪恢复', icon: 'wind' },
    { id: 'social', name: '社交连接', description: '朋友、同学与亲友互动', icon: 'users' },
    { id: 'explore', name: '乐享探索', description: '美食、娱乐与轻度探索', icon: 'compass' },
    { id: 'growth', name: '自我成长', description: '阅读、学习与兴趣提升', icon: 'sparkles' },
  ];

  function defaultProfile() {
    return {
      persona: 'student',
      workload: 'light',
      timeMode: 'half',
      budget: 'medium',
      location: '',
      outing: 'nearby',
      company: 'solo',
      pace: 'balanced',
    };
  }

  const state = {
    step: 'booting',
    sessionId: null,
    selectedCategories: [],
    profile: defaultProfile(),
    mode: null,
    questions: [],
    scale: [],
    answers: {},
    currentIndex: 0,
    result: null,
    busy: false,
    error: '',
    retryTask: null,
  };
  const stepNumbers = { welcome: 1, profile: 2, mode: 3, quiz: 4, result: 5 };
  let toastTimer;

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>'"]/g, (character) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
    }[character]));
  }

  function showToast(message) {
    toast.textContent = message;
    toast.classList.add('is-visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('is-visible'), 2600);
  }

  function renderIcons() {
    if (window.lucide) window.lucide.createIcons();
  }

  function categoryById(id) {
    return categories.find((category) => category.id === id);
  }

  function categoryIdByName(name) {
    const category = categories.find((item) => item.name === name);
    return category ? category.id : name;
  }

  function header() {
    const current = stepNumbers[state.step] || 1;
    const pets = ['dog', 'pig', 'cat', 'rabbit', 'bear'];
    return `<div class="progress-row">
      <span class="step-name"><span class="pixel-pet ${pets[current - 1]}" aria-hidden="true"></span>第 ${current} 步</span>
      <div class="progress-track"><div class="progress-bar" style="width:${current / 5 * 100}%"></div></div>
      <span class="step-count">${current} / 5</span>
    </div>`;
  }

  function errorBanner() {
    if (!state.error) return '';
    return `<div class="error-banner" role="alert">
      <span>${escapeHtml(state.error)}</span>
      ${state.retryTask ? '<button class="button secondary compact" data-action="retry">重试</button>' : ''}
    </div>`;
  }

  function renderBooting() {
    return `<section class="status-screen">
      <span class="status-icon"><i data-lucide="loader-circle" aria-hidden="true"></i></span>
      <h1>正在恢复你的留白</h1>
      <p class="lead">正在连接本地服务并读取问卷进度。</p>
      ${errorBanner()}
    </section>`;
  }

  function renderWelcome() {
    const hasSelection = state.selectedCategories.length > 0;
    return `<section class="screen">
      <p class="eyebrow">为突然到来的自由时段，留一份清醒的安排</p>
      <h1>这段时间，你想把自己放在哪个方向？</h1>
      <p class="lead">选择一个或多个方向，我们会据此准备与你当前状态更相关的问题。</p>
      <div class="section-heading"><h3>此刻最重要的事</h3><p>可多选</p></div>
      <div class="direction-grid">${categories.map((category) => `<button class="direction-card ${state.selectedCategories.includes(category.id) ? 'is-selected' : ''}" data-action="toggle-category" data-id="${category.id}" aria-pressed="${state.selectedCategories.includes(category.id)}" ${state.busy ? 'disabled' : ''}>
        <span class="direction-icon ${category.id}"><i data-lucide="${category.icon}" aria-hidden="true"></i></span>
        <h3>${category.name}</h3><p>${category.description}</p>
      </button>`).join('')}</div>
      <div class="priority-panel ${hasSelection ? '' : 'is-empty'}">${hasSelection ? `<strong>优先级</strong><div class="priority-list">${state.selectedCategories.map((id, index) => `<div class="priority-item">
        <span class="priority-number">${index + 1}</span><span>${categoryById(id).name}</span>
        <button class="icon-button" data-action="move-category" data-direction="up" data-id="${id}" aria-label="提高 ${categoryById(id).name} 优先级" ${index === 0 || state.busy ? 'disabled' : ''}><i data-lucide="arrow-up"></i></button>
        <button class="icon-button" data-action="move-category" data-direction="down" data-id="${id}" aria-label="降低 ${categoryById(id).name} 优先级" ${index === state.selectedCategories.length - 1 || state.busy ? 'disabled' : ''}><i data-lucide="arrow-down"></i></button>
      </div>`).join('')}</div>` : '请选择至少一个方向。'}</div>
      <div class="actions"><span></span><div class="actions-right"><button class="button primary" data-action="go-profile" ${!hasSelection || state.busy ? 'disabled' : ''}>继续<i data-lucide="arrow-right"></i></button></div></div>
    </section>`;
  }

  function segmented(name, current, values) {
    return `<div class="segmented">${values.map(([value, label]) => `<label class="choice"><input type="radio" name="${name}" value="${value}" ${current === value ? 'checked' : ''} ${state.busy ? 'disabled' : ''}><span>${label}</span></label>`).join('')}</div>`;
  }

  function renderProfile() {
    return `<section class="screen">
      <p class="eyebrow">第 2 步 · 可用条件</p>
      <h2>让安排适合你真正拥有的时间</h2>
      <p class="lead">条件会保存到当前会话，并用于筛选本次问卷。</p>
      <div class="form-grid">
        <div class="form-block"><span class="form-label">身份</span>${segmented('persona', state.profile.persona, [['student', '在校学生'], ['worker', '职场人']])}</div>
        <div class="form-block"><span class="form-label">近期学习或工作状态</span>${segmented('workload', state.profile.workload, [['light', '节奏平稳'], ['busy', '忙碌/加班中'], ['off', '休假或调休']])}</div>
        <div class="form-block"><span class="form-label">可用时长</span>${segmented('timeMode', state.profile.timeMode, [['half', '半天'], ['day', '全天']])}</div>
        <div class="form-block"><span class="form-label">预算区间</span>${segmented('budget', state.profile.budget, [['low', '20 元以内'], ['medium', '40 元以内'], ['high', '80 元以内']])}</div>
        <div class="form-block"><label class="form-label" for="location">所在城市或校园（选填）</label><input id="location" class="text-field" name="location" value="${escapeHtml(state.profile.location)}" placeholder="例如：上海徐汇区" ${state.busy ? 'disabled' : ''}></div>
        <div class="form-block"><span class="form-label">活动方式</span>${segmented('outing', state.profile.outing, [['home', '居家完成'], ['nearby', '附近出门'], ['city', '全城范围'], ['any', '都可以']])}</div>
        <div class="form-block"><span class="form-label">同行偏好</span>${segmented('company', state.profile.company, [['solo', '独处'], ['group', '结伴'], ['both', '都可以']])}</div>
        <div class="form-block"><span class="form-label">安排节奏</span>${segmented('pace', state.profile.pace, [['relaxed', '轻松留白'], ['balanced', '张弛平衡'], ['full', '充实一点']])}</div>
      </div>
      <div class="actions"><button class="button ghost" data-action="go-welcome" ${state.busy ? 'disabled' : ''}>返回</button><div class="actions-right"><button class="button primary" data-action="save-profile" ${state.busy ? 'disabled' : ''}>${state.busy ? '正在保存' : '选择问卷'}<i data-lucide="arrow-right"></i></button></div></div>
    </section>`;
  }

  function renderMode() {
    return `<section class="screen">
      <p class="eyebrow">第 3 步 · 问卷模式</p>
      <h2>今天想了解得多深入？</h2>
      <p class="lead">两种模式都可以随时刷新恢复，开始后本次会话将保持所选模式。</p>
      <div class="mode-grid">
        <button class="mode-card" data-action="start-mode" data-mode="quick" ${state.busy ? 'disabled' : ''}>
          <span class="mode-icon"><i data-lucide="zap"></i></span><span class="badge">快速版</span>
          <h3>5 道题</h3><p>适合临时空出的一小段时间，快速得到偏好摘要。</p><strong>约 30 秒</strong>
        </button>
        <button class="mode-card" data-action="start-mode" data-mode="deep" ${state.busy ? 'disabled' : ''}>
          <span class="mode-icon deep"><i data-lucide="scan-search"></i></span><span class="badge">深度版</span>
          <h3>30 道题</h3><p>覆盖五个方向，适合半天或全天的精细规划准备。</p><strong>约 3 分钟</strong>
        </button>
      </div>
      <div class="actions"><button class="button ghost" data-action="go-profile" ${state.busy ? 'disabled' : ''}>修改条件</button><span></span></div>
    </section>`;
  }

  function handledCount() {
    return Object.keys(state.answers).length;
  }

  function renderQuiz() {
    const question = state.questions[state.currentIndex];
    if (!question) return `<section class="status-screen"><h2>暂时没有可展示的问题</h2></section>`;
    const answer = state.answers[question.id];
    const total = state.questions.length;
    const completed = handledCount() === total;
    return `<section class="screen">
      <p class="eyebrow">第 4 步 · 空闲偏好小调查</p>
      <div class="quiz-layout">
        <div class="question-card">
          <div class="question-meta"><span>${escapeHtml(question.category)}</span><span>${state.currentIndex + 1} / ${total}</span></div>
          <h2>${escapeHtml(question.prompt)}</h2>
          <div class="option-list">${state.scale.map((option) => `<button class="option ${answer && !answer.skipped && answer.value === option.value ? 'is-selected' : ''}" data-action="answer" data-question="${question.id}" data-value="${option.value}" ${state.busy ? 'disabled' : ''}>${escapeHtml(option.label)}</button>`).join('')}</div>
          <div class="question-tools"><button class="button ghost" data-action="skip-question" ${state.busy ? 'disabled' : ''}>跳过本题</button>${answer && answer.skipped ? '<span class="skip-label">本题已跳过</span>' : ''}</div>
          <div class="actions"><button class="button ghost" data-action="previous-question" ${state.currentIndex === 0 || state.busy ? 'disabled' : ''}>上一题</button><div class="actions-right">${completed ? `<button class="button primary" data-action="submit-questionnaire" ${state.busy ? 'disabled' : ''}>提交问卷<i data-lucide="check"></i></button>` : ''}</div></div>
        </div>
        <aside class="quiz-summary"><span class="eyebrow">完成进度</span><strong>${handledCount()} / ${total}</strong><div class="progress-track"><div class="progress-bar" style="width:${handledCount() / total * 100}%"></div></div><div class="mini-list"><div class="mini-row"><span>模式</span><span>${state.mode === 'quick' ? '快速版' : '深度版'}</span></div><div class="mini-row"><span>刷新恢复</span><span>已开启</span></div></div></aside>
      </div>
    </section>`;
  }

  function renderResult() {
    const result = state.result || {};
    const plan = state.plan || {};
    const items = Array.isArray(plan.items) ? plan.items : [];
    const formatTime = (value) => {
      if (!value) return '--:--';
      return new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    };
    return `<section class="screen result-screen">
      <p class="eyebrow"><span class="pixel-pet rabbit" aria-hidden="true"></span>第 5 步 · 你的留白安排</p>
      <h1>这份时间，现在有了落点</h1>
      <p class="lead">问卷、画像、任务推荐和时间排程已通过统一接口完成，并保存到 PostgreSQL。</p>
      <div class="result-grid">
        <div class="result-stat"><span>问卷模式</span><strong>${result.mode === 'deep' ? '深度版' : '快速版'}</strong></div>
        <div class="result-stat"><span>题目总数</span><strong>${result.total ?? 0}</strong></div>
        <div class="result-stat"><span>已回答</span><strong>${result.answered_count ?? 0}</strong></div>
        <div class="result-stat"><span>已跳过</span><strong>${result.skipped_count ?? 0}</strong></div>
      </div>
      <div class="timeline-list">${items.map((item) => `<div class="timeline-item ${item.status === 'skipped' ? 'is-skipped' : ''}">
        <div class="timeline-time">${formatTime(item.start_at)}<br>${formatTime(item.end_at)}</div>
        <div><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.category)} · ${escapeHtml(item.status || 'pending')}</span><div class="timeline-actions">
          <button class="button ghost compact" data-action="edit-plan-item" data-item-id="${escapeHtml(item.id)}" ${item.status === 'skipped' ? 'disabled' : ''}>修改时间</button>
          <button class="button ghost compact" data-action="replace-plan-item" data-item-id="${escapeHtml(item.id)}" ${item.status === 'skipped' ? 'disabled' : ''}>替换</button>
          <button class="button ghost compact" data-action="skip-plan-item" data-item-id="${escapeHtml(item.id)}" ${item.status === 'skipped' ? 'disabled' : ''}>跳过</button>
        </div></div>
      </div>`).join('') || '<p class="lead">暂时没有可展示的计划任务。</p>'}</div>
      <div class="session-box"><span>Session ID</span><code>${escapeHtml(state.sessionId)}</code></div>
      <div class="actions"><div class="actions-right"><button class="button secondary" data-action="add-custom-task" ${state.busy ? 'disabled' : ''}>添加自定义任务</button><button class="button secondary" data-action="replan" ${state.busy ? 'disabled' : ''}>重新排程</button><button class="button primary" data-action="confirm-plan" ${state.busy || plan.status === 'confirmed' ? 'disabled' : ''}>${plan.status === 'confirmed' ? '已确认' : '确认计划'}</button><button class="button ghost" data-action="restart" ${state.busy ? 'disabled' : ''}><i data-lucide="rotate-ccw"></i>重新开始</button></div></div>
    </section>`;
  }

  function render() {
    const renderers = {
      booting: renderBooting,
      welcome: renderWelcome,
      profile: renderProfile,
      mode: renderMode,
      quiz: renderQuiz,
      result: renderResult,
    };
    const body = renderers[state.step]();
    app.innerHTML = `${state.step === 'booting' ? '' : header()}${state.step === 'booting' ? '' : errorBanner()}${body}`;
    renderIcons();
  }

  function resetLocalState() {
    state.selectedCategories = [];
    state.profile = defaultProfile();
    state.mode = null;
    state.questions = [];
    state.scale = [];
    state.answers = {};
    state.currentIndex = 0;
    state.result = null;
    state.plan = null;
  }

  function buildPreferences() {
    return {
      categories: state.selectedCategories.map((id) => categoryById(id).name),
      duration: state.profile.timeMode,
      budget: state.profile.budget,
      outing: state.profile.outing,
      company: state.profile.company,
      city_or_campus: state.profile.location.trim() || null,
      rest_only: state.profile.workload === 'busy' || state.profile.pace === 'relaxed',
    };
  }

  function hydratePreferences(preferences) {
    state.selectedCategories = Array.isArray(preferences.categories)
      ? preferences.categories.map(categoryIdByName)
      : [];
    state.profile.timeMode = preferences.duration || state.profile.timeMode;
    state.profile.budget = preferences.budget || state.profile.budget;
    state.profile.outing = preferences.outing || state.profile.outing;
    state.profile.company = preferences.company || state.profile.company;
    state.profile.location = preferences.city_or_campus || '';
    if (preferences.rest_only) state.profile.pace = 'relaxed';
  }

  function hydrateQuestionnaire(started, progress) {
    state.mode = started.mode;
    state.questions = started.questions;
    state.scale = started.scale;
    state.answers = progress ? progress.answers || {} : {};
    state.currentIndex = flow.firstUnansweredIndex(
      state.questions,
      state.answers,
    );
  }

  async function createFreshSession() {
    const created = await api.createSession();
    resetLocalState();
    state.sessionId = created.session_id;
    state.step = 'welcome';
  }

  async function recoverExpiredSession() {
    api.forgetSession();
    await createFreshSession();
    showToast('原会话已失效，已创建新的本地会话。');
  }

  async function runTask(task) {
    state.busy = true;
    state.error = '';
    state.retryTask = null;
    render();
    try {
      await task();
    } catch (error) {
      if (error.status === 404 || error.status === 410) {
        try {
          await recoverExpiredSession();
        } catch (recoveryError) {
          state.error = recoveryError.message || '无法创建新会话';
          state.retryTask = task;
        }
      } else {
        state.error = error.message || '请求失败，请稍后重试';
        state.retryTask = task;
      }
    } finally {
      state.busy = false;
      render();
    }
  }

  function goToNextUnhandled() {
    const next = state.questions.findIndex(
      (question, index) => index > state.currentIndex && !state.answers[question.id],
    );
    if (next >= 0) {
      state.currentIndex = next;
      return;
    }
    const first = state.questions.findIndex((question) => !state.answers[question.id]);
    if (first >= 0) state.currentIndex = first;
  }

  async function initialize() {
    state.step = 'booting';
    state.busy = true;
    state.error = '';
    render();
    try {
      const storedSessionId = api.getSessionId();
      if (!storedSessionId) {
        await createFreshSession();
        return;
      }
      const restored = await api.restoreSession(storedSessionId);
      state.sessionId = restored.session_id;
      hydratePreferences(restored.preferences || {});
      const initialDestination = flow.resumeDestination({
        preferences: restored.preferences || {},
        progress: null,
      });
      if (initialDestination === 'welcome') {
        state.step = 'welcome';
        return;
      }
      try {
        const progress = await api.getProgress();
        const destination = flow.resumeDestination({
          preferences: restored.preferences || {},
          progress,
        });
        if (destination === 'result') {
          state.mode = progress.mode;
          state.result = progress;
          try { state.plan = await api.getPlan(); } catch (_) { state.plan = null; }
          state.step = 'result';
          return;
        }
        const started = await api.startQuestionnaire(progress.mode);
        hydrateQuestionnaire(started, progress);
        state.step = 'quiz';
      } catch (error) {
        if (error.status !== 409) throw error;
        state.step = 'mode';
      }
    } catch (error) {
      const recovery = await flow.recoverInitialization(api, error);
      if (recovery.recovered) {
        resetLocalState();
        state.sessionId = recovery.session.session_id;
        state.step = 'welcome';
        showToast('原会话已失效，已创建新的本地会话。');
      } else {
        state.error = recovery.message;
        state.retryTask = initialize;
      }
    } finally {
      state.busy = false;
      render();
    }
  }

  app.addEventListener('click', async (event) => {
    const control = event.target.closest('[data-action]');
    if (!control || control.disabled) return;
    const action = control.dataset.action;
    if (action === 'toggle-category') {
      const id = control.dataset.id;
      state.selectedCategories = state.selectedCategories.includes(id)
        ? state.selectedCategories.filter((item) => item !== id)
        : [...state.selectedCategories, id];
      render();
      return;
    }
    if (action === 'move-category') {
      const index = state.selectedCategories.indexOf(control.dataset.id);
      const next = control.dataset.direction === 'up' ? index - 1 : index + 1;
      if (next >= 0 && next < state.selectedCategories.length) {
        [state.selectedCategories[index], state.selectedCategories[next]] = [state.selectedCategories[next], state.selectedCategories[index]];
      }
      render();
      return;
    }
    if (action === 'go-profile') { state.step = 'profile'; render(); return; }
    if (action === 'go-welcome') { state.step = 'welcome'; render(); return; }
    if (action === 'previous-question') { state.currentIndex -= 1; render(); return; }
    if (action === 'retry' && state.retryTask) { await runTask(state.retryTask); return; }
    if (action === 'save-profile') {
      await runTask(async () => {
        await api.savePreferences(buildPreferences());
        state.step = 'mode';
      });
      return;
    }
    if (action === 'start-mode') {
      await runTask(async () => {
        const started = await api.startQuestionnaire(control.dataset.mode);
        hydrateQuestionnaire(started, null);
        state.step = 'quiz';
      });
      return;
    }
    if (action === 'answer') {
      await runTask(async () => {
        const value = Number(control.dataset.value);
        await api.saveAnswer(control.dataset.question, value);
        state.answers[control.dataset.question] = { value, skipped: false };
        goToNextUnhandled();
      });
      return;
    }
    if (action === 'skip-question') {
      const question = state.questions[state.currentIndex];
      await runTask(async () => {
        await api.skipQuestion(question.id);
        state.answers[question.id] = { value: null, skipped: true };
        goToNextUnhandled();
      });
      return;
    }
    if (action === 'submit-questionnaire') {
      await runTask(async () => {
      state.result = await api.submitQuestionnaire();
        const freeStart = new Date();
        freeStart.setSeconds(0, 0);
        const freeEnd = new Date(freeStart.getTime() + (state.profile.timeMode === 'day' ? 8 : 4) * 60 * 60 * 1000);
        const generated = await api.generatePlan({
          free_start: freeStart.toISOString(),
          free_end: freeEnd.toISOString(),
          density: state.profile.pace === 'relaxed' ? 'light' : state.profile.pace === 'full' ? 'full' : 'balanced',
        });
        state.plan = generated.plan;
        state.step = 'result';
      });
      return;
    }
    if (action === 'edit-plan-item') {
      const plan = state.plan;
      const item = plan && plan.items.find((entry) => entry.id === control.dataset.itemId);
      if (!plan || !item) return;
      const startInput = window.prompt('请输入开始时间（例如 2026-08-16T14:00）', item.start_at.slice(0, 16));
      if (!startInput) return;
      const endInput = window.prompt('请输入结束时间（例如 2026-08-16T14:40）', item.end_at.slice(0, 16));
      if (!endInput) return;
      await runTask(async () => {
        state.plan = await api.updatePlanItem(plan.plan_id, item.id, {
          expected_version: plan.version,
          start_at: new Date(startInput).toISOString(),
          end_at: new Date(endInput).toISOString(),
        });
      });
      return;
    }
    if (action === 'replace-plan-item') {
      const plan = state.plan;
      if (!plan) return;
      await runTask(async () => {
        state.plan = await api.replacePlanItem(plan.plan_id, control.dataset.itemId, {
          expected_version: plan.version,
        });
      });
      return;
    }
    if (action === 'skip-plan-item') {
      const plan = state.plan;
      if (!plan) return;
      await runTask(async () => {
        state.plan = await api.skipPlanItem(plan.plan_id, control.dataset.itemId, {
          expected_version: plan.version,
        });
      });
      return;
    }
    if (action === 'add-custom-task') {
      const plan = state.plan;
      if (!plan) return;
      const title = window.prompt('请输入自定义任务名称');
      if (!title) return;
      const duration = Number(window.prompt('请输入持续时间（分钟）', '30'));
      if (!Number.isFinite(duration) || duration <= 0) return;
      await runTask(async () => {
        state.plan = await api.addCustomTask(plan.plan_id, {
          expected_version: plan.version,
          title,
          duration_minutes: duration,
          category: '自我成长',
        });
      });
      return;
    }
    if (action === 'confirm-plan') {
      const plan = state.plan;
      if (!plan) return;
      await runTask(async () => {
        state.plan = await api.confirmPlan(plan.plan_id, { expected_version: plan.version });
      });
      return;
    }
    if (action === 'replan') {
      const plan = state.plan;
      if (!plan) return;
      await runTask(async () => {
        state.plan = await api.replan(plan.plan_id, {
          expected_version: plan.version,
          density: plan.density,
        });
      });
      return;
    }
    if (action === 'restart') {
      await runTask(async () => {
        await api.clearSession();
        await createFreshSession();
      });
    }
  });

  app.addEventListener('change', (event) => {
    const control = event.target;
    if (control.name && Object.prototype.hasOwnProperty.call(state.profile, control.name)) {
      state.profile[control.name] = control.value;
      render();
    }
  });

  app.addEventListener('input', (event) => {
    if (event.target.name === 'location') state.profile.location = event.target.value;
  });

  initialize();
}());
