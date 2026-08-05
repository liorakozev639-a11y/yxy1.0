const test = require('node:test');
const assert = require('node:assert/strict');

const logic = require('../outputs/free-time-agent-demo-v2/logic.js');

test('activity library includes at least sixteen generic activities across five categories', () => {
  const library = logic.getActivityLibrary();
  const categories = new Set(library.map((activity) => activity.category));

  assert.ok(Array.isArray(library));
  assert.ok(library.length >= 16);
  assert.deepEqual(
    categories,
    new Set(['energy', 'calm', 'social', 'explore', 'growth']),
  );
});

test('activity library avoids specific merchants, distances, prices, and business hours', () => {
  const library = logic.getActivityLibrary();

  library.forEach((activity) => {
    assert.equal(typeof activity.title, 'string');
    assert.equal(typeof activity.reason, 'string');
    assert.doesNotMatch(activity.title, /\d+\s?(km|公里|minutes|分钟|元|￥|RMB|am|pm|AM|PM)/);
    assert.doesNotMatch(activity.reason, /\d+\s?(km|公里|minutes|分钟|元|￥|RMB|am|pm|AM|PM)/);
    assert.doesNotMatch(activity.title, /(星巴克|manner|seesaw|costa|迪士尼|万达|iapm)/i);
    assert.doesNotMatch(activity.reason, /(星巴克|manner|seesaw|costa|迪士尼|万达|iapm)/i);
  });
});

test('filterActivities applies category, outing, company, budget, and duration constraints', () => {
  const filtered = logic.filterActivities({
    selectedCategories: ['calm'],
    outing: 'home',
    company: 'solo',
    budget: 'low',
    duration: 'short',
  });

  assert.ok(filtered.length > 0);
  filtered.forEach((activity) => {
    assert.equal(activity.category, 'calm');
    assert.equal(activity.mode, 'home');
    assert.notEqual(activity.company, 'pair');
    assert.ok(activity.budget === 'free' || activity.budget === 'low');
    assert.ok(activity.duration <= 90);
  });
});

test('recommendActivities returns ten activities from the built-in library with matching reasons', () => {
  const result = logic.recommendActivities(
    {
      selectedCategories: ['calm', 'growth'],
      company: 'either',
      budget: 'medium',
      duration: 'half-day',
    },
    {},
  );
  const ids = new Set(logic.getActivityLibrary().map((item) => item.id));

  assert.equal(result.tasks.length, 10);
  assert.equal(result.tasks.every((task) => ids.has(task.id)), true);
  assert.equal(result.tasks.every((task) => typeof task.matchReason === 'string' && task.matchReason.length > 0), true);
});

test('restFirst mode sorts low-pressure activities to the front', () => {
  const result = logic.recommendActivities(
    {
      selectedCategories: ['calm'],
      restFirst: true,
    },
    {},
    10,
  );

  assert.equal(result.tasks.length, 10);
  assert.equal(result.tasks.slice(0, 3).every((task) => task.restFirst === true), true);
});

test('recommendActivities favors selected categories before filling with other generic activities', () => {
  const result = logic.recommendActivities(
    {
      selectedCategories: ['social'],
      company: 'either',
      budget: 'high',
      duration: 'half-day',
    },
    {},
    10,
  );

  assert.ok(result.tasks.length >= 4);
  assert.equal(result.tasks.slice(0, 4).every((task) => task.category === 'social'), true);
});

test('recommendActivities only relaxes selectedCategories when filling fallback results', () => {
  const result = logic.recommendActivities(
    {
      selectedCategories: ['social'],
      outing: 'home',
      company: 'solo',
      budget: 'free',
      duration: 'short',
    },
    {},
    10,
  );

  assert.equal(result.totalMatches, 0);
  assert.equal(result.fallbackUsed, true);
  assert.ok(result.tasks.length > 0);
  assert.ok(result.tasks.length < 10);
  result.tasks.forEach((task) => {
    assert.equal(task.mode, 'home');
    assert.notEqual(task.company, 'pair');
    assert.equal(task.budget, 'free');
    assert.ok(task.duration <= 90);
  });
});
