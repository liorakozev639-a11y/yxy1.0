const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const repoDir = path.join(__dirname, '..');
const read = (name) => fs.readFileSync(path.join(repoDir, name), 'utf8');

test('vercel config serves FastAPI and the pixel frontend from one domain', () => {
  const config = JSON.parse(read('vercel.json'));

  assert.deepEqual(config.version, 2);
  assert.ok(config.builds.some((build) => build.src === 'api/index.py' && build.use === '@vercel/python'));
  assert.ok(config.builds.some((build) => build.src === 'frontend/**' && build.use === '@vercel/static'));

  const routePairs = config.routes.map((route) => `${route.src} -> ${route.dest}`);
  assert.ok(routePairs.includes('/api/(.*) -> /api/index.py'));
  assert.ok(routePairs.includes('/health -> /api/index.py'));
  assert.ok(routePairs.includes('/docs -> /api/index.py'));
  assert.ok(routePairs.includes('/openapi.json -> /api/index.py'));
  assert.ok(routePairs.includes('/(.*) -> /frontend/index.html'));
});

test('vercel Python entry exports the repository FastAPI app', () => {
  const entry = read('api/index.py');

  assert.match(entry, /sys\.path\.insert\(0, str\(ROOT\)\)/);
  assert.match(entry, /from main import app/);
});

test('frontend uses localhost port 8000 locally and same-origin API in production', () => {
  const source = read('frontend/api.js');

  assert.match(source, /isLocalHostname/);
  assert.match(source, /hostname === 'localhost'/);
  assert.match(source, /hostname === '127\.0\.0\.1'/);
  assert.match(source, /return `\$\{window\.location\.protocol\}\/\/\$\{hostname\}:8000`/);
  assert.match(source, /return window\.location\.origin/);
});

test('vercel ignore excludes local-only files without hiding deploy source', () => {
  const ignored = read('.vercelignore');

  assert.match(ignored, /\.venv\//);
  assert.match(ignored, /\.venv-debug\//);
  assert.match(ignored, /backup-before-github-20260814-1\//);
  assert.doesNotMatch(ignored, /^frontend\//m);
  assert.doesNotMatch(ignored, /^api\//m);
});
