const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFileSync } = require('node:child_process');

const repoDir = path.join(__dirname, '..');
const read = (name) => fs.readFileSync(path.join(repoDir, name), 'utf8');

test('render blueprint declares backend and static frontend services', () => {
  const blueprint = read('render.yaml');

  assert.match(blueprint, /name:\s*free-time-agent-api/);
  assert.match(blueprint, /runtime:\s*python/);
  assert.match(blueprint, /buildCommand:\s*pip install -r requirements\.txt/);
  assert.match(blueprint, /startCommand:\s*python -m uvicorn main:app --host 0\.0\.0\.0 --port \$PORT/);
  assert.match(blueprint, /key:\s*SESSION_DATABASE_URL/);
  assert.match(blueprint, /key:\s*FRONTEND_ORIGINS/);
  assert.match(blueprint, /name:\s*free-time-agent-web/);
  assert.match(blueprint, /runtime:\s*static/);
  assert.match(blueprint, /staticPublishPath:\s*\.\/frontend/);
  assert.match(blueprint, /python deploy\/write_frontend_config\.py/);
  assert.match(blueprint, /key:\s*FREE_TIME_API_BASE_URL/);
});

test('frontend config writer injects the public backend url without secrets', () => {
  const output = path.join(os.tmpdir(), `free-time-config-${Date.now()}.js`);
  const python = process.env.PYTHON || path.join(repoDir, '.venv', 'Scripts', 'python.exe');

  execFileSync(python, ['deploy/write_frontend_config.py'], {
    cwd: repoDir,
    env: {
      ...process.env,
      FREE_TIME_API_BASE_URL: 'https://api.example.com',
      FRONTEND_CONFIG_OUTPUT: output,
    },
    stdio: 'pipe',
  });

  const generated = fs.readFileSync(output, 'utf8');
  assert.match(generated, /root\.FREE_TIME_API_BASE_URL = 'https:\/\/api\.example\.com';/);
  assert.doesNotMatch(generated, /password|SESSION_DATABASE_URL|postgresql:\/\//i);
});

