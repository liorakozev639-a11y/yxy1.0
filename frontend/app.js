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
    userId: null,
    selectedCategories: [],
    profile: defaultProfile(),
    mode: null,
    questions: [],
    scale: [],
    answers: {},
    currentIndex: 0,
    result: null,
    recommendation: null,
    profileInsight: null,
    busy: false,
    error: '',
    retryTask: null,
    detailItemId: null,
    feedbackItemId: null,
    feedbackRating: null,
    feedbackReasons: [],
    executionReminders: null,
    review: null,
    showingReview: false,
    reflectionItemId: null,
    reflectionSentiment: null,
    energyItemId: null,
    energyChoice: null,
    energyReplacementSuggested: false,
  };
  const stepNumbers = { welcome: 1, profile: 2, mode: 3, quiz: 4, insight: 5, result: 6 };
  let toastTimer;
  let executionRefreshTimer;

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>'"]/g, (character) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
    }[character]));
  }

  function recommendationStorageKey() {
    return state.sessionId ? `free_time_agent_recommendation_${state.sessionId}` : '';
  }

  function persistRecommendation(recommendation) {
    const key = recommendationStorageKey();
    if (!key || !recommendation || !Array.isArray(recommendation.tasks)) return;
    try {
      window.localStorage.setItem(key, JSON.stringify(recommendation));
    } catch (_) {
      // Local storage can be unavailable in private browsing; the live state still works.
    }
  }

  function restoreRecommendation() {
    const key = recommendationStorageKey();
    if (!key) return null;
    try {
      const stored = JSON.parse(window.localStorage.getItem(key) || 'null');
      return stored && Array.isArray(stored.tasks) ? stored : null;
    } catch (_) {
      return null;
    }
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
      <span class="step-name"><span class="pixel-pet ${pets[(current - 1) % pets.length]}" aria-hidden="true"></span>第 ${current} 步</span>
      <div class="progress-track"><div class="progress-bar" style="width:${current / 6 * 100}%"></div></div>
      <span class="step-count">${current} / 6</span>
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
    return `<section class="status-screen pixel-screen">
      <span class="status-icon"><i data-lucide="loader-circle" aria-hidden="true"></i></span>
      <h1>正在恢复你的留白</h1>
      <p class="lead">正在连接本地服务并读取问卷进度。</p>
      ${errorBanner()}
    </section>`;
  }

  function renderWelcome() {
    const hasSelection = state.selectedCategories.length > 0;
    return `<section class="screen pixel-screen">
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
    return `<section class="screen pixel-screen">
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
    return `<section class="screen pixel-screen">
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
    return `<section class="screen pixel-screen">
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

  function renderInsight() {
    const insight = state.profileInsight || {};
    const dimensions = Array.isArray(insight.top_dimensions) ? insight.top_dimensions : [];
    const cards = Array.isArray(insight.constraint_cards) ? insight.constraint_cards : [];
    const suggestions = Array.isArray(insight.suggestions) ? insight.suggestions : [];
    return `<section class="screen pixel-screen profile-insight-screen">
      <div class="pixel-plan-hero">
        <div>
          <p class="eyebrow"><span class="pixel-pet bear" aria-hidden="true"></span>第 5 步 · 问卷结果解释</p>
          <h1>你的空闲偏好画像</h1>
          <p class="lead">${escapeHtml(insight.summary || '问卷已提交，我们正在整理你的偏好画像。')}</p>
        </div>
        <div class="pixel-hero-stamp" aria-label="画像已生成">PROFILE<br><strong>READY</strong></div>
      </div>
      <div class="profile-insight-grid">
        <section class="profile-insight-card profile-insight-card-main">
          <span class="eyebrow">偏好排序</span>
          <div class="insight-bars">${dimensions.map((item) => `<div class="insight-bar-row">
            <div class="insight-bar-label"><strong>${escapeHtml(item.label)}</strong><span>${escapeHtml(item.level || '')}</span></div>
            <div class="insight-bar-track"><span style="width:${Math.round(Number(item.score || 0) * 100)}%"></span></div>
            <p>${escapeHtml(item.text || '')}</p>
          </div>`).join('') || '<p class="lead">暂无可展示的偏好分数。</p>'}</div>
        </section>
        <aside class="profile-insight-card">
          <span class="eyebrow">约束条件</span>
          <div class="constraint-card-list">${cards.map((card) => `<div class="constraint-card">
            <span>${escapeHtml(card.label)}</span>
            <strong>${escapeHtml(card.value)}</strong>
            <p>${escapeHtml(card.text)}</p>
          </div>`).join('')}</div>
        </aside>
      </div>
      <div class="profile-insight-card recommendation-basis">
        <span class="eyebrow">为什么推荐这些任务</span>
        <div class="basis-grid">
          <div>
            <strong>画像会影响任务推荐</strong>
            <p>系统会优先选择你得分更高的休闲方向，再结合预算、出行范围、独处或结伴偏好，过滤掉不适合当前状态的任务。</p>
          </div>
          <div>
            <strong>计划会保留一点弹性</strong>
            <p>如果某个方向得分较低，但你在第一步选择了它，系统仍会保留少量相关任务，避免计划只偏向单一类型。</p>
          </div>
        </div>
      </div>
      <div class="profile-insight-card suggestion-panel">
        <span class="eyebrow">生成计划前的建议</span>
        <div class="suggestion-list">${suggestions.map((item) => `<span>${escapeHtml(item)}</span>`).join('')}</div>
      </div>
      <div class="actions"><button class="button ghost" data-action="go-mode" ${state.busy ? 'disabled' : ''}>返回问卷选择</button><div class="actions-right"><button class="button primary" data-action="generate-plan" ${state.busy ? 'disabled' : ''}>生成计划<i data-lucide="arrow-right"></i></button></div></div>
    </section>`;
  }

  function executionStatusLabel(status) {
    return {
      pending: '待开始',
      active: '进行中',
      completed: '已完成',
      skipped: '已跳过',
      recommended: '推荐候选',
      missed: '已错过',
      overdue: '已超时',
      needs_adjustment: '需要调整',
    }[status] || status || '待开始';
  }

  function feedbackPanel(item) {
    if (state.feedbackItemId !== item.id) return '';
    const reasons = ['容易开始', '符合当前状态', '下次还想做'];
    return `<div class="pixel-feedback-panel">
      <span class="feedback-label">这项任务怎么样？</span>
      <div class="feedback-rating">${[1, 2, 3, 4, 5].map((rating) => `<button class="feedback-star ${state.feedbackRating === rating ? 'is-selected' : ''}" data-action="choose-feedback-rating" data-rating="${rating}" aria-label="${rating} 分">${rating}</button>`).join('')}</div>
      <div class="feedback-reasons">${reasons.map((reason) => `<button class="feedback-reason ${state.feedbackReasons.includes(reason) ? 'is-selected' : ''}" data-action="toggle-feedback-reason" data-reason="${reason}">${reason}</button>`).join('')}</div>
      <button class="button primary compact" data-action="save-feedback" ${state.feedbackRating ? '' : 'disabled'}>保存反馈</button>
    </div>`;
  }

  function reasonTags(item) {
    const summary = flow.taskReasonSummary(item);
    return `<div class="reason-tags">${summary.tags.slice(0, 5).map((tag) => `<span>${escapeHtml(tag)}</span>`).join('')}</div>`;
  }

  function taskLoadSummary(item) {
    const summary = flow.taskReasonSummary(item);
    const values = [
      ['轻松度', summary.loadProfile && summary.loadProfile.ease],
      ['体力消耗', summary.loadProfile && summary.loadProfile.physical],
      ['社交压力', summary.loadProfile && summary.loadProfile.social],
      ['预算', Number.isFinite(Number(item.budget)) ? `${item.budget} 元以内` : '--'],
      ['地点依赖', summary.loadProfile && summary.loadProfile.location],
    ];
    return `<div class="task-load-summary" aria-label="任务轻重与限制">${values.map(([label, value]) => `<span><small>${escapeHtml(label)}</small><b>${escapeHtml(value || '--')}</b></span>`).join('')}</div>`;
  }

  function loadProfile(summary) {
    if (!summary.loadProfile) return '';
    const items = [
      ['轻松度', summary.loadProfile.ease],
      ['体力消耗', summary.loadProfile.physical],
      ['社交压力', summary.loadProfile.social],
      ['地点依赖', summary.loadProfile.location],
    ];
    return `<section class="load-profile-grid" aria-label="任务轻重">
      <strong>任务轻重</strong>
      <div>${items.map(([label, value]) => `<span><small>${escapeHtml(label)}</small><b>${escapeHtml(value || '--')}</b></span>`).join('')}</div>
    </section>`;
  }

  function executionReminder() {
    const reminders = state.executionReminders || {};
    if (reminders.needs_adjustment_count > 0) {
      return `<div class="execution-reminder needs-adjustment" role="status">有 ${escapeHtml(reminders.needs_adjustment_count)} 项任务需要调整</div>`;
    }
    if (Array.isArray(reminders.ending_soon_titles) && reminders.ending_soon_titles.length) {
      return `<div class="execution-reminder ending-soon" role="status">任务即将结束：${escapeHtml(reminders.ending_soon_titles[0])}</div>`;
    }
    if (Array.isArray(reminders.startable_titles) && reminders.startable_titles.length) {
      return `<div class="execution-reminder startable" role="status">现在可以开始：${escapeHtml(reminders.startable_titles[0])}</div>`;
    }
    return '';
  }

  function reflectionControls(item) {
    if (item.outcome !== 'completed') return '';
    const selected = state.reflectionItemId === item.item_id
      ? state.reflectionSentiment
      : item.sentiment;
    const labels = [
      ['satisfied', '满意'],
      ['neutral', '一般'],
      ['dissatisfied', '不满意'],
    ];
    return `<div class="reflection-controls"><span>完成感受（可选）</span><div class="reflection-choices">${labels.map(([value, label]) => `<button class="reflection-choice ${selected === value ? 'is-selected' : ''}" data-action="choose-reflection" data-item-id="${escapeHtml(item.item_id)}" data-sentiment="${value}" ${state.busy ? 'disabled' : ''}>${label}</button>`).join('')}</div><button class="button primary compact" data-action="save-reflection" data-item-id="${escapeHtml(item.item_id)}" ${state.reflectionItemId === item.item_id && state.reflectionSentiment ? '' : 'disabled'}>保存感受</button></div>`;
  }

  function reviewPanel() {
    const review = state.review;
    if (!review) return '';
    const summary = review.summary || {};
    return `<section class="review-panel" aria-label="本次复盘">
      <div class="pixel-section-label"><strong>本次复盘</strong><span>计划已结束</span></div>
      <div class="review-summary"><span>完成 ${escapeHtml(summary.completed_count ?? 0)}</span><span>跳过 ${escapeHtml(summary.skipped_count ?? 0)}</span><span>未完成 ${escapeHtml(summary.unfinished_count ?? 0)}</span></div>
      <div class="review-items">${(review.items || []).map((item) => `<article class="review-item outcome-${escapeHtml(item.outcome)}"><div><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.outcome === 'completed' ? '已完成' : item.outcome === 'skipped' ? '已跳过' : '未完成')}</span></div>${reflectionControls(item)}</article>`).join('')}</div>
      <div class="review-suggestions"><strong>下次建议</strong>${(review.suggestions || []).map((suggestion) => `<p>${escapeHtml(suggestion)}</p>`).join('')}</div>
      <button class="button ghost" data-action="back-to-plan" ${state.busy ? 'disabled' : ''}>返回计划</button>
    </section>`;
  }

  function reasonModal(items) {
    const item = items.find((entry) => entry.id === state.detailItemId);
    if (!item) return '';
    const summary = flow.taskReasonSummary(item);
    return `<div class="detail-backdrop" data-action="close-detail">
      <article class="detail-dialog" role="dialog" aria-modal="true" aria-label="任务推荐理由" onclick="event.stopPropagation()">
        <div class="detail-header">
          <div><span class="eyebrow">推荐理由</span><h2>${escapeHtml(item.title)}</h2></div>
          <button class="icon-button" data-action="close-detail" aria-label="关闭详情"><i data-lucide="x"></i></button>
        </div>
        ${reasonTags(item)}
        <div class="reason-score-row">
          <span>匹配分</span>
          <strong>${summary.matchScore === null ? '--' : Math.round(summary.matchScore * 100)}</strong>
        </div>
        ${loadProfile(summary)}
        ${summary.matchedPreferences.length ? `<div class="matched-preferences">${summary.matchedPreferences.map((entry) => `<span>${escapeHtml(entry)}</span>`).join('')}</div>` : ''}
        ${summary.warningText ? `<div class="warning-note">${escapeHtml(summary.warningText)}</div>` : ''}
        <div class="reason-text">${escapeHtml(summary.text).replace(/\n/g, '<br>')}</div>
      </article>
    </div>`;
  }

  function energyPanel(item) {
    if (state.energyItemId !== item.id) return '';
    const disabled = state.busy ? 'disabled' : '';
    if (state.energyReplacementSuggested) {
      return `<div class="energy-panel"><strong>现在先换成更轻松的任务吧</strong><p>低精力时，我们会为这项任务找一个更容易开始的替代方案。</p><button class="button primary compact" data-action="replace-easier" ${disabled}>换个更轻松的</button></div>`;
    }
    return `<div class="energy-panel"><strong>开始前，确认一下现在的精力</strong><div class="energy-options">${[['high', '精力充足'], ['medium', '还可以'], ['low', '有点累']].map(([energy, label]) => `<button class="button secondary compact energy-option ${state.energyChoice === energy ? 'is-selected' : ''}" data-action="choose-energy" data-energy="${energy}" ${disabled}>${label}</button>`).join('')}</div><button class="button primary compact" data-action="confirm-energy-start" ${!state.energyChoice || state.busy ? 'disabled' : ''}>确认并开始</button></div>`;
  }

  function executionActions(item, plan) {
    if (item.recommendationOnly) {
      return `<button class="button primary compact" data-action="add-recommended-task" data-item-id="${escapeHtml(item.task_id)}" ${state.busy ? 'disabled' : ''}>加入时间线</button><span class="execution-status recommendation-status">待安排到当前时间线</span>`;
    }
    const disabled = state.busy ? 'disabled' : '';
    if (item.status === 'pending') {
      return `<button class="button primary compact" data-action="start-execution" data-item-id="${escapeHtml(item.id)}" ${disabled}>开始任务</button><button class="button ghost compact" data-action="skip-execution" data-item-id="${escapeHtml(item.id)}" ${disabled}>跳过</button><button class="button ghost compact" data-action="check-deadline" data-item-id="${escapeHtml(item.id)}" ${disabled}>检查截止</button>${energyPanel(item)}`;
    }
    if (item.status === 'active') {
      return `<button class="button primary compact" data-action="complete-execution" data-item-id="${escapeHtml(item.id)}" ${disabled}>完成任务</button><button class="button ghost compact" data-action="skip-execution" data-item-id="${escapeHtml(item.id)}" ${disabled}>跳过</button><button class="button ghost compact" data-action="check-deadline" data-item-id="${escapeHtml(item.id)}" ${disabled}>检查截止</button>`;
    }
    if (item.status === 'completed') {
      return `<button class="button secondary compact" data-action="open-feedback" data-item-id="${escapeHtml(item.id)}" ${disabled}>${state.feedbackItemId === item.id ? '收起反馈' : '任务反馈'}</button>`;
    }
    if (item.status === 'needs_adjustment' || item.status === 'missed' || item.status === 'overdue') {
      return `<button class="button secondary compact" data-action="replan" ${disabled}>重新排程</button>`;
    }
    return `<span class="execution-status">${executionStatusLabel(item.status)}</span>`;
  }

  function buildRecommendedItems(items, recommendedTasks) {
    const scheduledByTaskId = new Map(
      items
        .filter((item) => item.kind === 'task' && item.task_id)
        .map((item) => [item.task_id, item]),
    );
    return recommendedTasks.map((task, index) => {
      const scheduled = scheduledByTaskId.get(task.id);
      if (scheduled) {
        return {
          ...task,
          ...scheduled,
          recommendationIndex: index,
          recommendationOnly: false,
        };
      }
      return {
        ...task,
        id: `recommendation-${task.id}`,
        task_id: task.id,
        kind: 'task',
        status: 'recommended',
        start_at: null,
        end_at: null,
        recommendationIndex: index,
        recommendationOnly: true,
      };
    });
  }

  function renderTaskCard(item, index, plan, formatTime) {
    const isScheduled = !item.recommendationOnly;
    const status = item.status || 'pending';
    const time = isScheduled
      ? `${formatTime(item.start_at)}<br>${formatTime(item.end_at)}`
      : '<span class="recommendation-time-pending">待安排</span>';
    const replaceButton = isScheduled && item.kind === 'task' && status !== 'skipped'
      ? `<button class="button secondary compact" data-action="replace-plan-item" data-item-id="${escapeHtml(item.id)}" ${state.busy ? 'disabled' : ''}>换一个</button>`
      : '';
    const detailButton = `<button class="button ghost compact" data-action="open-detail" data-item-id="${escapeHtml(item.id)}">详情</button>`;
    const editButton = isScheduled
      ? `<button class="button ghost compact" data-action="edit-plan-item" data-item-id="${escapeHtml(item.id)}" ${status === 'skipped' ? 'disabled' : ''}>调整时间</button>`
      : '';
    const skipButton = isScheduled && (status === 'pending' || status === 'active')
      ? `<button class="button ghost compact" data-action="skip-plan-item" data-item-id="${escapeHtml(item.id)}">编辑跳过</button>`
      : '';
    return `<article class="timeline-item pixel-timeline-item recommended-task-card status-${escapeHtml(status)} ${item.recommendationOnly ? 'is-recommendation-only' : ''} ${status === 'skipped' ? 'is-skipped' : ''}">
      <div class="timeline-time"><span class="pixel-time-index">${String(index + 1).padStart(2, '0')}</span><span class="timeline-time-label">推荐时间</span>${time}</div>
      <div class="pixel-task-content"><div class="pixel-task-header"><div><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.category)} · ${executionStatusLabel(status)}</span></div>${replaceButton}</div>${reasonTags(item)}${taskLoadSummary(item)}<div class="timeline-actions">
        ${executionActions(item, plan)}
        ${detailButton}
        ${editButton}
        ${skipButton}
      </div>${feedbackPanel(item)}</div>
    </article>`;
  }

  function renderResult() {
    const result = state.result || {};
    const plan = state.plan || {};
    const items = Array.isArray(plan.items) ? plan.items : [];
    const recommendedTasks = state.recommendation && Array.isArray(state.recommendation.tasks)
      ? state.recommendation.tasks
      : [];
    const recommendedItems = buildRecommendedItems(items, recommendedTasks);
    const recommendedItemIds = new Set(recommendedItems.map((item) => item.id));
    const additionalPlanItems = items.filter((item) => !recommendedItemIds.has(item.id));
    const displayItems = recommendedItems.length > 0
      ? [...recommendedItems, ...additionalPlanItems]
      : items;
    const formatTime = (value) => {
      if (!value) return '--:--';
      return new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    };
    return `<section class="screen pixel-screen result-screen">
      <div class="pixel-plan-hero">
        <div>
          <p class="eyebrow"><span class="pixel-pet rabbit" aria-hidden="true"></span>第 5 步 · 你的留白安排</p>
          <h1>这份时间，现在有了落点</h1>
          <p class="lead">问卷、画像、任务推荐和时间排程已通过统一接口完成，并保存到 PostgreSQL。</p>
        </div>
        <div class="pixel-hero-stamp" aria-label="计划已生成">PLAN<br><strong>READY</strong></div>
      </div>
      <div class="pixel-plan-layout">
        <div class="pixel-plan-main">
          <div class="pixel-section-label"><strong>今日任务推荐时间线</strong><span>版本 v${escapeHtml(plan.version ?? 1)}</span></div>
          <div class="result-grid pixel-stat-grid">
            <div class="result-stat"><span>问卷模式</span><strong>${result.mode === 'deep' ? '深度版' : '快速版'}</strong></div>
            <div class="result-stat"><span>题目总数</span><strong>${result.total ?? 0}</strong></div>
            <div class="result-stat"><span>已回答</span><strong>${result.answered_count ?? 0}</strong></div>
            <div class="result-stat"><span>已跳过</span><strong>${result.skipped_count ?? 0}</strong></div>
          </div>
          ${executionReminder()}
          ${state.showingReview ? reviewPanel() : `<div class="timeline-list pixel-timeline">${displayItems.map((item, index) => renderTaskCard(item, index, plan, formatTime)).join('') || '<p class="lead">暂时没有可展示的计划任务。</p>'}</div>`}
          ${state.review && !state.showingReview ? '<button class="button secondary" data-action="view-review">查看本次复盘</button>' : ''}
          <div class="session-box"><span>Session ID</span><code>${escapeHtml(state.sessionId)}</code></div>
          <div class="actions pixel-result-actions"><div class="actions-right"><button class="button secondary" data-action="add-custom-task" ${state.busy ? 'disabled' : ''}>添加自定义任务</button><button class="button secondary" data-action="replan" ${state.busy ? 'disabled' : ''}>重新排程</button><button class="button primary" data-action="confirm-plan" ${state.busy || plan.status === 'confirmed' ? 'disabled' : ''}>${plan.status === 'confirmed' ? '已按流程执行' : '按此流程执行'}</button><button class="button ghost" data-action="restart" ${state.busy ? 'disabled' : ''}><i data-lucide="rotate-ccw"></i>重新开始</button></div></div>
        </div>
        <aside class="pixel-companion-panel">
          <div class="pixel-companion-art"><span class="pixel-pet bear" aria-hidden="true"></span><span class="pixel-pet cat" aria-hidden="true"></span></div>
          <span class="eyebrow">你的像素伙伴</span>
          <h2>先完成一件，剩下的慢慢来。</h2>
          <p>每个任务显示的是推荐时间，你可以先调整起止时间，再按当前流程执行；也可以提前开始或提前完成。</p>
          <div class="pixel-category-list">${state.selectedCategories.map((id) => `<span>${escapeHtml(categoryById(id)?.name || id)}</span>`).join('') || '<span>自由安排</span>'}</div>
          <div class="pixel-status-note"><span class="pixel-dot"></span>${plan.status === 'confirmed' ? '已按当前流程执行' : '计划草稿，可继续调整'}</div>
        </aside>
      </div>
      ${reasonModal([...items, ...recommendedItems])}
    </section>`;
  }

  function render() {
    const renderers = {
      booting: renderBooting,
      welcome: renderWelcome,
      profile: renderProfile,
      mode: renderMode,
      quiz: renderQuiz,
      insight: renderInsight,
      result: renderResult,
    };
    const body = renderers[state.step]();
    app.innerHTML = `${state.step === 'booting' ? '' : header()}${state.step === 'booting' ? '' : errorBanner()}${body}`;
    renderIcons();
  }

  function resetLocalState() {
    stopExecutionRefresh();
    state.selectedCategories = [];
    state.profile = defaultProfile();
    state.mode = null;
    state.questions = [];
    state.scale = [];
    state.answers = {};
    state.currentIndex = 0;
    state.result = null;
    state.recommendation = null;
    state.profileInsight = null;
    state.plan = null;
    state.feedbackItemId = null;
    state.detailItemId = null;
    state.feedbackRating = null;
    state.feedbackReasons = [];
    state.executionReminders = null;
    state.review = null;
    state.showingReview = false;
    state.reflectionItemId = null;
    state.reflectionSentiment = null;
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
      syncExecutionRefresh();
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
      try {
        const user = await api.ensureAnonymousUser();
        state.userId = user.user_id || null;
      } catch (_) {
        state.userId = api.currentUserId ? api.currentUserId() : null;
      }
      const storedSessionId = api.getSessionId();
      if (!storedSessionId) {
        await createFreshSession();
        return;
      }
      const restored = await api.restoreSession(storedSessionId);
      state.sessionId = restored.session_id;
      state.recommendation = restoreRecommendation();
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
          if (state.plan) {
            state.step = 'result';
          } else {
            state.profileInsight = await api.getProfileInsight();
            state.step = 'insight';
          }
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
      syncExecutionRefresh();
    }
  }

  function applyExecutionPayload(payload) {
    if (!state.plan || !payload || !payload.item) return;
    state.plan = {
      ...state.plan,
      ...(payload.recommendation_memory ? { recommendation_memory: payload.recommendation_memory } : {}),
      items: state.plan.items.map((item) => (
        item.id === payload.item.id
          ? { ...item, status: payload.item.status }
          : item
      )),
    };
  }

  function mergeRefreshedItems(items) {
    if (!state.plan || !Array.isArray(items)) return;
    const refreshedById = new Map(items.map((item) => [item.item_id, item]));
    state.plan = {
      ...state.plan,
      items: state.plan.items.map((item) => {
        const refreshed = refreshedById.get(item.id);
        return refreshed ? { ...item, ...refreshed, id: item.id } : item;
      }),
    };
  }

  async function refreshExecutionState() {
    if (state.step !== 'result' || !state.plan?.plan_id || state.busy) return;
    try {
      const refreshed = await api.refreshExecution(state.plan.plan_id);
      mergeRefreshedItems(refreshed.items);
      state.executionReminders = refreshed.reminders || null;
      const review = await api.getReview(state.plan.plan_id);
      if (review.status === 'finished') state.review = review;
      render();
    } catch (_) {
      showToast('执行状态暂时无法刷新');
    }
  }

  function stopExecutionRefresh() {
    if (executionRefreshTimer) {
      clearInterval(executionRefreshTimer);
      executionRefreshTimer = null;
    }
  }

  function syncExecutionRefresh() {
    if (state.step !== 'result' || !state.plan?.plan_id) {
      stopExecutionRefresh();
      return;
    }
    if (executionRefreshTimer) return;
    void refreshExecutionState();
    executionRefreshTimer = setInterval(() => {
      void refreshExecutionState();
    }, 30000);
  }

  async function generateCurrentPlan() {
    const freeStart = new Date();
    freeStart.setSeconds(0, 0);
    const freeEnd = new Date(freeStart.getTime() + (state.profile.timeMode === 'day' ? 8 : 4) * 60 * 60 * 1000);
    const generated = await api.generatePlan({
      free_start: freeStart.toISOString(),
      free_end: freeEnd.toISOString(),
      density: state.profile.pace === 'relaxed' ? 'light' : state.profile.pace === 'full' ? 'full' : 'balanced',
      user_id: state.userId,
    });
    state.plan = generated.plan;
    state.recommendation = generated.recommendation || null;
    persistRecommendation(state.recommendation);
    state.step = 'result';
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
    if (action === 'go-mode') { state.step = 'mode'; render(); return; }
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
        state.profileInsight = await api.getProfileInsight();
        state.step = 'insight';
      });
      return;
    }
    if (action === 'generate-plan') {
      await runTask(generateCurrentPlan);
      return;
    }
    if (action === 'start-execution') {
      state.energyItemId = control.dataset.itemId;
      state.energyChoice = null;
      state.energyReplacementSuggested = false;
      render();
      return;
    }
    if (action === 'choose-energy') {
      state.energyChoice = control.dataset.energy;
      render();
      return;
    }
    if (action === 'confirm-energy-start') {
      const plan = state.plan;
      if (!plan || !state.energyItemId || !state.energyChoice) return;
      await runTask(async () => {
        const prepare = await api.prepareExecution(plan.plan_id, state.energyItemId, {
          user_id: state.userId,
          energy: state.energyChoice,
        });
        if (prepare.recommended_action === 'replace_easier') {
          state.energyReplacementSuggested = true;
          return;
        }
        const payload = await api.startExecution(plan.plan_id, state.energyItemId, { user_id: state.userId });
        applyExecutionPayload(payload);
        state.energyItemId = null;
        state.energyChoice = null;
        showToast('任务已开始');
      });
      return;
    }
    if (action === 'replace-easier') {
      const plan = state.plan;
      if (!plan || !state.energyItemId) return;
      await runTask(async () => {
        state.plan = await api.replacePlanItemEasier(plan.plan_id, state.energyItemId, {
          expected_version: plan.version,
          user_id: state.userId,
        });
        state.energyItemId = null;
        state.energyChoice = null;
        state.energyReplacementSuggested = false;
        showToast('已换成更轻松的任务');
      });
      return;
    }
    if (action === 'complete-execution' || action === 'skip-execution' || action === 'check-deadline') {
      const plan = state.plan;
      if (!plan) return;
      const itemId = control.dataset.itemId;
      await runTask(async () => {
        const payload = action === 'complete-execution'
          ? await api.completeExecution(plan.plan_id, itemId, { user_id: state.userId })
          : action === 'skip-execution'
            ? await api.skipExecution(plan.plan_id, itemId, { user_id: state.userId })
            : await api.checkExecutionDeadline(plan.plan_id, itemId, { user_id: state.userId });
        applyExecutionPayload(payload);
        showToast(action === 'complete-execution' ? '任务已完成' : action === 'skip-execution' ? '任务已跳过，稍后可重新排程' : '已检查任务截止时间');
      });
      return;
    }
    if (action === 'open-feedback') {
      state.feedbackItemId = state.feedbackItemId === control.dataset.itemId ? null : control.dataset.itemId;
      state.feedbackRating = null;
      state.feedbackReasons = [];
      render();
      return;
    }
    if (action === 'view-review') {
      state.showingReview = true;
      render();
      return;
    }
    if (action === 'back-to-plan') {
      state.showingReview = false;
      render();
      return;
    }
    if (action === 'choose-reflection') {
      state.reflectionItemId = control.dataset.itemId;
      state.reflectionSentiment = control.dataset.sentiment;
      render();
      return;
    }
    if (action === 'save-reflection') {
      const plan = state.plan;
      if (!plan || !state.reflectionItemId || !state.reflectionSentiment) return;
      await runTask(async () => {
        await api.saveReflection(plan.plan_id, state.reflectionItemId, {
          sentiment: state.reflectionSentiment,
        });
        state.review = await api.getReview(plan.plan_id);
        state.reflectionItemId = null;
        state.reflectionSentiment = null;
        showToast('完成感受已保存');
      });
      return;
    }
    if (action === 'open-detail') {
      state.detailItemId = control.dataset.itemId;
      render();
      return;
    }
    if (action === 'close-detail') {
      state.detailItemId = null;
      render();
      return;
    }
    if (action === 'choose-feedback-rating') {
      state.feedbackRating = Number(control.dataset.rating);
      render();
      return;
    }
    if (action === 'toggle-feedback-reason') {
      const reason = control.dataset.reason;
      state.feedbackReasons = state.feedbackReasons.includes(reason)
        ? state.feedbackReasons.filter((item) => item !== reason)
        : [...state.feedbackReasons, reason].slice(-3);
      render();
      return;
    }
    if (action === 'save-feedback') {
      const plan = state.plan;
      if (!plan || !state.feedbackItemId || !state.feedbackRating) return;
      await runTask(async () => {
        const feedback = await api.saveFeedback(plan.plan_id, state.feedbackItemId, {
          rating: state.feedbackRating,
          reasons: state.feedbackReasons,
        });
        if (feedback.recommendation_memory) {
          state.plan = {
            ...state.plan,
            recommendation_memory: feedback.recommendation_memory,
          };
        }
        state.feedbackItemId = null;
        state.feedbackRating = null;
        state.feedbackReasons = [];
        showToast('反馈已保存');
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
        showToast('已更换任务');
      });
      return;
    }
    if (action === 'add-recommended-task') {
      const plan = state.plan;
      if (!plan) return;
      await runTask(async () => {
        state.plan = await api.addRecommendedTask(
          plan.plan_id,
          control.dataset.itemId,
          { expected_version: plan.version },
        );
        showToast('已加入时间线');
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
