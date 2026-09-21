const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const frontendDir = path.join(__dirname, '..', 'frontend');
const read = (name) => fs.readFileSync(path.join(frontendDir, name), 'utf8');

test('frontend declares installable PWA metadata and runtime config', () => {
  const index = read('index.html');
  const manifest = JSON.parse(read('manifest.json'));

  assert.match(index, /<link rel="manifest" href="manifest\.json\?v=pwa-v2">/);
  assert.match(index, /<meta name="apple-mobile-web-app-capable" content="yes">/);
  assert.match(index, /config\.js\?v=pwa-v2/);
  assert.equal(manifest.name, '留白计划');
  assert.equal(manifest.short_name, '留白计划');
  assert.equal(manifest.start_url, './');
  assert.equal(manifest.display, 'standalone');
  assert.equal(manifest.theme_color, '#f7f6f1');
  assert.ok(manifest.icons.some((icon) => icon.src === 'icons/icon-192.png' && icon.sizes === '192x192'));
  assert.ok(manifest.icons.some((icon) => icon.src === 'icons/icon-512.png' && icon.sizes === '512x512'));
});

test('service worker caches the app shell without caching API calls', () => {
  const worker = read('service-worker.js');

  assert.match(worker, /const APP_SHELL/);
  assert.match(worker, /index\.html/);
  assert.match(worker, /free-time-agent-pwa-v6/);
  assert.match(worker, /styles\.css\?v=pixel-v12/);
  assert.match(worker, /api\.js\?v=pixel-v12/);
  assert.match(worker, /flow\.js\?v=pixel-v12/);
  assert.match(worker, /app\.js\?v=pixel-v12/);
  assert.match(worker, /icons\/icon-192\.png/);
  assert.match(worker, /icons\/icon-512\.png/);
  assert.match(worker, /request\.url\.includes\('\/api\/v1\/'\)/);
  assert.match(worker, /return fetch\(request\)/);
  assert.match(worker, /request\.mode === 'navigate'/);
  assert.match(worker, /fetch\(request\)\.catch\(\(\) => caches\.match\('\.\/'\)\)/);
});

test('app registers service worker and shows an install hint', () => {
  const app = read('app.js');
  const css = read('styles.css');

  assert.match(app, /beforeinstallprompt/);
  assert.match(app, /registerServiceWorker/);
  assert.match(app, /data-action="install-pwa"/);
  assert.match(app, /添加到桌面/);
  assert.match(css, /\.pwa-install-card/);
});
