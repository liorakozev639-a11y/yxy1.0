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
  assert.match(index, /styles\.css\?v=pixel-v2/);
  assert.match(index, /app\.js\?v=pixel-v2/);
  assert.match(app, /class="screen pixel-screen/);
  assert.match(app, /pixel-plan-layout/);
  assert.match(app, /pixel-plan-hero/);
  assert.match(app, /pixel-companion-panel/);
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
});

test('formal frontend shows profile insight before generating the plan', () => {
  const app = read('app.js');
  const css = read('styles.css');

  assert.match(app, /renderInsight/);
  assert.match(app, /你的空闲偏好画像/);
  assert.match(app, /data-action="generate-plan"/);
  assert.match(css, /\.profile-insight-grid/);
  assert.match(css, /\.profile-insight-card/);
});

test('task detail dialog exposes score, preference matches, warnings, and replacement note', () => {
  const app = read('app.js');
  const css = read('styles.css');

  assert.match(app, /reason-score-row/);
  assert.match(app, /matchedPreferences/);
  assert.match(app, /warningText/);
  assert.match(app, /replacementReason/);
  assert.match(css, /\.matched-preferences/);
  assert.match(css, /\.replacement-note/);
});
