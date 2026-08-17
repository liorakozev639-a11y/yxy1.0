const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

test('frontend derives API host from the LAN page host', () => {
  const source = fs.readFileSync(
    path.join(__dirname, '..', 'frontend', 'api.js'),
    'utf8',
  );
  assert.match(source, /window\.location\.hostname/);
  assert.match(source, /:8000/);
});

test('backend allows configured LAN frontend origins', () => {
  const source = fs.readFileSync(path.join(__dirname, '..', 'main.py'), 'utf8');
  assert.match(source, /FRONTEND_ORIGINS/);
  assert.match(source, /allow_origins=ALLOWED_ORIGINS/);
});
