(function () {
  const { buildQuestions, buildCandidates, buildSchedule, categoryNames } = window.FreeTimeLogic;
  const app = document.querySelector('.app-shell');
  const toast = document.querySelector('#toast');
  const categories = [
    { id: 'energy', name: '活力充电', description: '运动、户外与身体恢复', icon: 'activity' },
    { id: 'calm', name: '松弛疗愈', description: '减压、安静休息与情绪恢复', icon: 'wind' },
    { id: 'social', name: '社交连接', description: '朋友、同学与亲友互动', icon: 'users' },
    { id: 'explore', name: '乐享探索', description: '美食、观影与新鲜体验', icon: 'compass' },
    { id: 'growth', name: '自我成长', description: '学习、创作与整理复盘', icon: 'sparkles' },
  ];

  const state = {
    step: 'welcome',
    selectedCategories: [],
    profile: { persona: 'student', workload: 'light', availableDate: 'weekend', timeMode: 'half', budget: 'medium', location: '', outing: 'open', company: 'solo', pace: 'balanced' },
    questions: [],
    answers: {},
    candidates: [],
    selectedTasks: [],
    schedule: [],
  };

  const steps = { welcome: 1, profile: 2, quiz: 3, candidates: 4, plan: 5 };
  let toastTimer;

  function showToast(message) {
    toast.textContent = message;
    toast.classList.add('is-visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('is-visible'), 2600);
  }

  function categoryById(id) { return categories.find((category) => category.id === id); }
  function formatTime(minutes) {
    const total = 570 + minutes;
    return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
  }
  function answerCount() { return Object.keys(state.answers).length; }
  function selectedTasks() { return state.candidates.filter((task) => state.selectedTasks.includes(task.id)); }
  function renderIcons() { if (window.lucide) window.lucide.createIcons(); }

  function header() {
    const current = steps[state.step];
    return `<div class="progress-row"><span class="step-name">第 ${current} 步</span><div class="progress-track"><div class="progress-bar" style="width:${current / 5 * 100}%"></div></div><span class="step-count">${current} / 5</span></div>`;
  }

  function renderWelcome() {
    const hasSelection = state.selectedCategories.length > 0;
    return `<section class="screen">
      <p class="eyebrow">为突然到来的自由时段，留一份清醒的安排</p>
      <h1>这段时间，你想把自己放在哪个方向？</h1>
      <p class="lead">适合周末、假期或临时空出的半天到一天。选择一个或多个方向，我们会据此生成专属问卷与计划。</p>
      <div class="section-heading"><h3>此刻最重要的事</h3><p>可多选</p></div>
      <div class="direction-grid">${categories.map((category) => `<button class="direction-card ${state.selectedCategories.includes(category.id) ? 'is-selected' : ''}" data-action="toggle-category" data-id="${category.id}" aria-pressed="${state.selectedCategories.includes(category.id)}"><span class="direction-icon ${category.id}"><i data-lucide="${category.icon}" aria-hidden="true"></i></span><h3>${category.name}</h3><p>${category.description}</p></button>`).join('')}</div>
      <div class="priority-panel ${hasSelection ? '' : 'is-empty'}">${hasSelection ? `<strong>优先级</strong><div class="priority-list">${state.selectedCategories.map((id, index) => `<div class="priority-item"><span class="priority-number">${index + 1}</span><span>${categoryById(id).name}</span><button class="icon-button" data-action="move-category" data-direction="up" data-id="${id}" aria-label="提高 ${categoryById(id).name} 优先级" ${index === 0 ? 'disabled' : ''}><i data-lucide="arrow-up" aria-hidden="true"></i></button><button class="icon-button" data-action="move-category" data-direction="down" data-id="${id}" aria-label="降低 ${categoryById(id).name} 优先级" ${index === state.selectedCategories.length - 1 ? 'disabled' : ''}><i data-lucide="arrow-down" aria-hidden="true"></i></button></div>`).join('')}</div>` : '请选择至少一个方向。'}</div>
      <div class="actions"><span></span><div class="actions-right"><button class="button primary" data-action="go-profile" ${hasSelection ? '' : 'disabled'}>继续<i data-lucide="arrow-right" aria-hidden="true"></i></button></div></div>
    </section>`;
  }

  function segmented(name, current, values) {
    return `<div class="segmented">${values.map(([value, label]) => `<label class="choice"><input type="radio" name="${name}" value="${value}" ${current === value ? 'checked' : ''}><span>${label}</span></label>`).join('')}</div>`;
  }

  function renderProfile() {
    return `<section class="screen"><p class="eyebrow">第 2 步 · 可用条件</p><h2>让计划适合你真正拥有的时间</h2><p class="lead">这些条件只用于本次演示中的本地推荐。</p>
      <div class="form-grid">
        <div class="form-block"><span class="form-label">身份</span>${segmented('persona', state.profile.persona, [['student', '在校学生'], ['worker', '职场人']])}</div>
        <div class="form-block"><span class="form-label">近期学习或工作状态</span>${segmented('workload', state.profile.workload, [['light', '节奏平稳'], ['busy', '忙碌/加班中'], ['off', '休假或调休']])}</div>
        <div class="form-block"><span class="form-label">可用日期</span>${segmented('availableDate', state.profile.availableDate, [['today', '今天'], ['weekend', '本周末'], ['next', '下个休息日']])}</div>
        <div class="form-block"><span class="form-label">可用时长</span>${segmented('timeMode', state.profile.timeMode, [['half', '半天'], ['full', '全天']])}</div>
        <div class="form-block"><span class="form-label">预算区间</span>${segmented('budget', state.profile.budget, [['low', '20 元以内'], ['medium', '40 元以内'], ['high', '80 元以内']])}</div>
        <div class="form-block"><label class="form-label" for="location">所在城市或校园</label><input id="location" class="text-field" name="location" value="${state.profile.location}" placeholder="例如：复旦大学邯郸校区 / 上海徐汇区"></div>
        <div class="form-block"><span class="form-label">活动方式</span>${segmented('outing', state.profile.outing, [['home', '居家完成'], ['nearby', '附近出门'], ['open', '自由出门']])}</div>
        <div class="form-block"><span class="form-label">同行偏好</span>${segmented('company', state.profile.company, [['solo', '独处'], ['friends', '结伴'], ['either', '都可以']])}</div>
        <div class="form-block full"><span class="form-label">安排节奏</span>${segmented('pace', state.profile.pace, [['relaxed', '轻松留白'], ['balanced', '张弛平衡'], ['full', '充实一点']])}</div>
      </div>
      <div class="actions"><button class="button ghost" data-action="go-welcome">返回</button><div class="actions-right"><button class="button primary" data-action="start-quiz">开始 30 题评估<i data-lucide="arrow-right" aria-hidden="true"></i></button></div></div>
    </section>`;
  }

  function renderQuiz() {
    const questionIndex = Math.min(answerCount(), state.questions.length - 1);
    const question = state.questions[questionIndex];
    const categoryCounts = state.questions.reduce((map, item) => { map[item.category] = (map[item.category] || 0) + 1; return map; }, {});
    if (!question) return '';
    return `<section class="screen"><p class="eyebrow">第 3 步 · 偏好评估</p><div class="quiz-layout"><div class="question-card"><div class="question-meta"><span>${question.categoryName}</span><span>${questionIndex + 1} / 30</span></div><h2>${question.prompt}</h2><div class="option-list">${question.options.map((option, index) => `<button class="option ${state.answers[question.id] === index ? 'is-selected' : ''}" data-action="answer" data-question="${question.id}" data-value="${index}">${option}</button>`).join('')}</div><div class="actions"><button class="button ghost" data-action="previous-question" ${questionIndex === 0 ? 'disabled' : ''}>上一步</button><div class="actions-right">${answerCount() === 30 ? '<button class="button primary" data-action="show-candidates">查看推荐<i data-lucide="arrow-right" aria-hidden="true"></i></button>' : ''}</div></div></div><aside class="quiz-summary"><span class="eyebrow">完成进度</span><strong>${answerCount()} / 30</strong><div class="progress-track"><div class="progress-bar" style="width:${answerCount() / 30 * 100}%"></div></div><div class="mini-list">${state.selectedCategories.map((id) => `<div class="mini-row"><span>${categoryNames[id]}</span><span>${categoryCounts[id]} 题</span></div>`).join('')}</div></aside></div></section>`;
  }

  function renderCandidates() {
    const selected = selectedTasks();
    const coverage = new Set(selected.map((task) => task.category));
    const covered = state.selectedCategories.filter((id) => coverage.has(id)).length;
    return `<section class="screen"><p class="eyebrow">第 4 步 · 十项候选任务</p><h2>先给你十种可能，再由你决定今天的样子</h2><p class="lead">已选 ${selected.length} 项，覆盖 ${covered} / ${state.selectedCategories.length} 个优先方向。勾选后可随时重新排程。</p><div class="candidate-grid">${state.candidates.map((task) => `<label class="task-card ${state.selectedTasks.includes(task.id) ? 'is-selected' : ''}"><input type="checkbox" data-action="toggle-task" data-id="${task.id}" ${state.selectedTasks.includes(task.id) ? 'checked' : ''}><span><span class="badge">${task.categoryName}</span><h3>${task.title}</h3><div class="task-meta"><span>${task.duration} 分钟</span><span>${task.budget}</span><span>${task.mode}</span><span>${task.location}</span><span>${task.company}</span></div></span></label>`).join('')}</div><div class="actions"><button class="button ghost" data-action="go-profile">修改条件</button><div class="actions-right"><button class="button secondary" data-action="refresh-candidates"><i data-lucide="refresh-cw" aria-hidden="true"></i>换一组</button><button class="button primary" data-action="build-plan" ${selected.length ? '' : 'disabled'}>生成计划<i data-lucide="arrow-right" aria-hidden="true"></i></button></div></div></section>`;
  }

  function renderPlan() {
    const persona = state.profile.persona === 'student' ? '学生' : '忙碌职场人';
    return `<section class="screen"><p class="eyebrow">第 5 步 · 你的留白计划</p><h2>一份可以随时调整的 ${state.profile.timeMode === 'half' ? '半天' : '全天'}安排</h2><p class="lead">为${persona}准备，保留节奏，也留出一点意外发生的空间。</p><div class="plan-grid"><div class="timeline">${state.schedule.length ? state.schedule.map((item) => `<div class="timeline-item"><span class="time">${formatTime(item.start)} - ${formatTime(item.end)}</span><div><span class="badge">${item.categoryName}</span><h3>${item.title}</h3><p>${item.duration} 分钟 · ${item.budget}</p></div></div>`).join('') : '<div class="empty-state">当前没有可排入计划的任务。</div>'}</div><aside class="summary-box"><span class="eyebrow">今日摘要</span><h3>给自己一段有余地的时间</h3><p>已围绕 ${state.selectedCategories.map((id) => categoryNames[id]).join('、')} 生成安排。</p><ul class="summary-list"><li>${state.schedule.length} 个时间段</li><li>${state.profile.budget === 'low' ? '轻预算' : state.profile.budget === 'medium' ? '适中预算' : '舒适预算'}</li><li>${state.profile.outing === 'indoor' ? '室内优先' : '可自由出门'}</li></ul><div class="delivery-actions"><button class="button secondary" data-action="demo-web"><i data-lucide="monitor" aria-hidden="true"></i>网页查看</button><button class="button secondary" data-action="demo-pdf"><i data-lucide="download" aria-hidden="true"></i>下载 PDF</button><button class="button primary" data-action="demo-email"><i data-lucide="mail" aria-hidden="true"></i>发送到邮箱</button></div></aside></div><div class="actions"><button class="button ghost" data-action="go-candidates">返回调整任务</button><div class="actions-right"><button class="button secondary" data-action="rebuild-plan"><i data-lucide="refresh-cw" aria-hidden="true"></i>重新排程</button><button class="button primary" data-action="restart">重新开始</button></div></div></section>`;
  }

  function render() {
    const body = { welcome: renderWelcome, profile: renderProfile, quiz: renderQuiz, candidates: renderCandidates, plan: renderPlan }[state.step]();
    app.innerHTML = `${header()}${body}`;
    renderIcons();
  }

  function createDefaultSelection() {
    const selected = [];
    state.selectedCategories.forEach((category) => {
      const first = state.candidates.find((task) => task.category === category);
      if (first) selected.push(first.id);
    });
    const target = state.profile.timeMode === 'half' ? 4 : 6;
    state.candidates.forEach((task) => { if (selected.length < target && !selected.includes(task.id)) selected.push(task.id); });
    return selected;
  }

  function generateCandidates() {
    state.candidates = buildCandidates(state.selectedCategories, { budget: state.profile.budget, outing: state.profile.outing !== 'home', location: state.profile.location, company: state.profile.company });
    state.selectedTasks = createDefaultSelection();
  }

  app.addEventListener('click', (event) => {
    const control = event.target.closest('[data-action]');
    if (!control || control.disabled) return;
    const action = control.dataset.action;
    if (action === 'toggle-category') {
      const id = control.dataset.id;
      state.selectedCategories = state.selectedCategories.includes(id) ? state.selectedCategories.filter((item) => item !== id) : [...state.selectedCategories, id];
    }
    if (action === 'move-category') {
      const index = state.selectedCategories.indexOf(control.dataset.id);
      const next = control.dataset.direction === 'up' ? index - 1 : index + 1;
      [state.selectedCategories[index], state.selectedCategories[next]] = [state.selectedCategories[next], state.selectedCategories[index]];
    }
    if (action === 'go-profile') state.step = 'profile';
    if (action === 'go-welcome') state.step = 'welcome';
    if (action === 'start-quiz') { state.questions = buildQuestions(state.selectedCategories); state.answers = {}; state.step = 'quiz'; }
    if (action === 'answer') { state.answers[control.dataset.question] = Number(control.dataset.value); }
    if (action === 'previous-question') { const index = answerCount() - 1; if (index >= 0) delete state.answers[state.questions[index].id]; }
    if (action === 'show-candidates') { generateCandidates(); state.step = 'candidates'; }
    if (action === 'refresh-candidates') { generateCandidates(); showToast('已生成另一组本地演示任务。'); }
    if (action === 'build-plan' || action === 'rebuild-plan') { state.schedule = buildSchedule(selectedTasks(), state.profile.timeMode); state.step = 'plan'; }
    if (action === 'go-candidates') state.step = 'candidates';
    if (action === 'restart') { state.step = 'welcome'; state.selectedCategories = []; state.answers = {}; state.candidates = []; state.selectedTasks = []; state.schedule = []; }
    if (action === 'demo-web') showToast('当前即为网页查看模式。');
    if (action === 'demo-pdf') showToast('演示模式：第一版不会生成实际 PDF 文件。');
    if (action === 'demo-email') showToast('演示模式：第一版不会发送真实邮件。');
    render();
  });

  app.addEventListener('change', (event) => {
    const control = event.target;
    if (control.name && Object.prototype.hasOwnProperty.call(state.profile, control.name)) state.profile[control.name] = control.value;
    if (control.dataset.action === 'toggle-task') {
      state.selectedTasks = control.checked ? [...state.selectedTasks, control.dataset.id] : state.selectedTasks.filter((id) => id !== control.dataset.id);
    }
    render();
  });

  render();
}());
