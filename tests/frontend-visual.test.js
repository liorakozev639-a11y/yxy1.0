const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const frontendDir = path.join(__dirname, '..', 'frontend');
const read = (name) => fs.readFileSync(path.join(frontendDir, name), 'utf8');

test('formal frontend exposes the pixel visual shell', () => {
  const index = read('index.html');
  const app = read('app.js');
  const css = read('styles.css');

  assert.match(index, /class="site-header pixel-header"/);
  assert.match(index, /class="app-shell pixel-app-shell"/);
  assert.match(index, /styles\.css\?v=pixel-v4/);
  assert.match(index, /api\.js\?v=pixel-v4/);
  assert.match(index, /flow\.js\?v=pixel-v4/);
  assert.match(index, /app\.js\?v=pixel-v4/);
  assert.match(app, /class="screen pixel-screen/);
  assert.match(app, /pixel-plan-layout/);
  assert.match(app, /pixel-plan-hero/);
  assert.match(app, /pixel-companion-panel/);
  assert.match(app, /recommendedItems/);
  assert.match(app, /buildRecommendedItems/);
  assert.match(app, /persistRecommendation/);
  assert.match(app, /restoreRecommendation/);
  assert.match(css, /--pixel-paper/);
  assert.match(css, /image-rendering:\s*pixelated/);
  assert.match(css, /\.pixel-plan-layout/);
  assert.ok(fs.existsSync(path.join(frontendDir, 'pixel-companions.png')));
});

test('formal result markup keeps real plan actions inside pixel timeline', () => {
  const app = read('app.js');

  assert.match(app, /pixel-timeline/);
  assert.match(app, /data-action="edit-plan-item"/);
  assert.match(app, /data-action="replace-plan-item"/);
  assert.match(app, /data-action="skip-plan-item"/);
  assert.match(app, /data-action="add-custom-task"/);
  assert.match(app, /data-action="confirm-plan"/);
  assert.match(app, /data-action="start-execution"/);
  assert.match(app, /recommended-task-card/);
  assert.match(app, /additionalPlanItems/);
});

test('formal frontend shows profile insight before generating the plan', () => {
  const app = read('app.js');
  const css = read('styles.css');

  assert.match(app, /renderInsight/);
  assert.match(app, /你的空闲偏好画像/);
  assert.match(app, /为什么推荐这些任务/);
  assert.match(app, /画像会影响任务推荐/);
  assert.match(app, /data-action="generate-plan"/);
  assert.match(css, /\.profile-insight-grid/);
  assert.match(css, /\.profile-insight-card/);
  assert.match(css, /\.recommendation-basis/);
});

test('task detail dialog exposes score, preference matches, load profile, and warnings', () => {
  const app = read('app.js');
  const css = read('styles.css');

  assert.match(app, /reason-score-row/);
  assert.match(app, /matchedPreferences/);
  assert.match(app, /loadProfile/);
  assert.match(app, /任务轻重/);
  assert.match(app, /warningText/);
  assert.match(css, /\.matched-preferences/);
  assert.match(css, /\.load-profile-grid/);
});

test('execution review keeps pixel reminder and reflection controls', () => {
  const app = read('app.js');
  const css = read('styles.css');

  assert.match(app, /execution-reminder/);
  assert.match(app, /review-panel/);
  assert.match(app, /reflection-choice/);
  assert.match(css, /\.execution-reminder/);
  assert.match(css, /\.review-panel/);
  assert.match(css, /\.reflection-choice/);
});
