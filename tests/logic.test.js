const test = require('node:test');
const assert = require('node:assert/strict');

const {
  allocateQuestionCounts,
  buildQuestions,
  buildCandidates,
  buildSchedule,
} = require('../logic.js');

test('allocates four ordered categories as 8/8/7/7', () => {
  assert.deepEqual(
    allocateQuestionCounts(['energy', 'calm', 'social', 'explore']),
    { energy: 8, calm: 8, social: 7, explore: 7 },
  );
});

test('builds exactly thirty questions across selected categories', () => {
  const questions = buildQuestions(['energy', 'growth', 'social']);

  assert.equal(questions.length, 30);
  assert.deepEqual(
    questions.reduce((counts, question) => {
      counts[question.category] = (counts[question.category] || 0) + 1;
      return counts;
    }, {}),
    { energy: 10, growth: 10, social: 10 },
  );
});

test('returns ten candidate tasks that cover every selected category', () => {
  const categories = ['energy', 'calm', 'social', 'explore', 'growth'];
  const tasks = buildCandidates(categories, { budget: 'medium', outing: true });

  assert.equal(tasks.length, 10);
  assert.deepEqual(new Set(tasks.map((task) => task.category)), new Set(categories));
});

test('carries location, home preference, and company preference into task context', () => {
  const [task] = buildCandidates(['calm'], {
    budget: 'medium',
    outing: false,
    location: '复旦大学邯郸校区',
    company: 'solo',
  });

  assert.equal(task.location, '复旦大学邯郸校区');
  assert.equal(task.mode, '居家完成');
  assert.equal(task.company, '适合独处');
});

test('builds a non-overlapping half-day schedule within the time limit', () => {
  const tasks = buildCandidates(['energy', 'calm', 'social'], { budget: 'low', outing: true });
  const schedule = buildSchedule(tasks.slice(0, 4), 'half');

  assert.ok(schedule.length > 0);
  assert.ok(schedule.every((item, index) => index === 0 || item.start >= schedule[index - 1].end));
  assert.ok(schedule.at(-1).end <= 270);
});
