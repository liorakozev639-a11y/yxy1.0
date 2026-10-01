(function (root) {
  if (!root || !root.document || !root.FreeTimeApi) return;

  const api = root.FreeTimeApi;
  const document = root.document;
  const loginPanel = document.querySelector('#admin-login');
  const dashboard = document.querySelector('#admin-dashboard');
  const loginForm = document.querySelector('#admin-login-form');
  const filterForm = document.querySelector('#admin-filters');
  const loginError = document.querySelector('#admin-login-error');
  const dashboardError = document.querySelector('#admin-error');
  const logout = document.querySelector('#admin-logout');

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>'"]/g, (character) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
    }[character]));
  }

  function filters() {
    const values = new FormData(filterForm);
    return Object.fromEntries([...values.entries()].filter(([, value]) => value));
  }

  function renderTable(target, columns, rows, empty = '暂无数据') {
    const element = document.querySelector(target);
    if (!rows || rows.length === 0) {
      element.innerHTML = `<p class="muted">${empty}</p>`;
      return;
    }
    element.innerHTML = `<div class="table-scroll"><table><thead><tr>${columns.map(([, label]) => `<th>${label}</th>`).join('')}</tr></thead><tbody>${rows.map((row) => `<tr>${columns.map(([key]) => `<td>${escapeHtml(row[key])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  }

  function renderSummary(summary) {
    const labels = [
      ['user_count', '匿名用户'],
      ['session_count', '会话数'],
      ['full_flow_success_rate', '完整流程成功率', '%'],
      ['average_rating', '平均评分'],
      ['replacement_rate', '替换率', '%'],
      ['skip_rate', '跳过率', '%'],
    ];
    document.querySelector('#summary').innerHTML = labels.map(([key, label, suffix = '']) => `<article class="metric"><span>${label}</span><strong>${escapeHtml(summary?.[key] ?? 0)}${suffix}</strong></article>`).join('');
  }

  async function loadDashboard() {
    dashboardError.textContent = '';
    const selected = filters();
    try {
      const [summary, funnel, recommendations, reasons, errors] = await Promise.all([
        api.adminMetrics('summary', selected),
        api.adminMetrics('funnel', selected),
        api.adminMetrics('recommendations', selected),
        api.adminMetrics('reasons', selected),
        api.adminMetrics('errors', selected),
      ]);
      renderSummary(summary);
      renderTable('#funnel', [['event_type', '事件'], ['count', '次数']], funnel?.steps);
      renderTable('#recommendations', [
        ['task_category', '任务分类'], ['recommendation_count', '推荐次数'],
        ['average_rating', '平均评分'], ['replacement_rate', '替换率'], ['skip_rate', '跳过率'],
      ], recommendations);
      renderTable('#reasons', [['reason_code', '原因'], ['count', '次数']], reasons);
      renderTable('#errors', [['error_code', '错误代码'], ['count', '次数']], errors);
    } catch (error) {
      dashboardError.textContent = error.message || '指标暂时无法加载';
      if (error.status === 401) showLogin();
    }
  }

  function showDashboard() {
    loginPanel.hidden = true;
    dashboard.hidden = false;
    logout.hidden = false;
    void loadDashboard();
  }

  function showLogin() {
    loginPanel.hidden = false;
    dashboard.hidden = true;
    logout.hidden = true;
  }

  loginForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    loginError.textContent = '';
    const values = new FormData(loginForm);
    try {
      await api.adminLogin(values.get('username'), values.get('password'));
      loginForm.reset();
      showDashboard();
    } catch (error) {
      loginError.textContent = '登录失败';
    }
  });

  filterForm.addEventListener('submit', (event) => {
    event.preventDefault();
    void loadDashboard();
  });

  logout.addEventListener('click', async () => {
    try { await api.adminLogout(); } finally { showLogin(); }
  });

  if (api.getAdminToken()) showDashboard();
}(typeof window !== 'undefined' ? window : null));
