import test from 'node:test';
import assert from 'node:assert/strict';
import { averageScore, canonicalScores, DIMENSION_KEYS, levelFromScore, trajectoryScores } from '../../../../plugins/zgc_ai_native_2026/view/capabilityScores.ts';

const historical = { spec_quality: 55, cloud_architecture: 15, ai_engineering: 34, mastery_professionalism: 71, commits_merged: 868 };

test('metadata never affects canonical averages or trajectory dimensions', () => {
  assert.equal(averageScore(historical), 43.75);
  assert.equal(levelFromScore(averageScore(historical)), 'L2');
  assert.deepEqual(Object.keys(trajectoryScores(historical, 'zgc_ai_native_2026')), DIMENSION_KEYS);
});

test('all level boundaries agree with evaluator rubric', () => {
  for (const [score, level] of [[0, 'L1'], [29.9, 'L1'], [30, 'L2'], [49.9, 'L2'], [50, 'L3'], [69.9, 'L3'], [70, 'L4'], [84.9, 'L4'], [85, 'L5'], [100, 'L5']]) {
    assert.equal(levelFromScore(score), level);
  }
});

test('invalid and missing dimensions remain incomplete, zero and aliases work', () => {
  for (const value of [null, undefined, '', true, [], NaN, Infinity, -1, 101, 'bad']) {
    assert.equal(averageScore({ ...historical, spec_quality: value }), null);
  }
  assert.equal(averageScore({ spec_quality: 55 }), null);
  assert.equal(averageScore(Object.fromEntries(DIMENSION_KEYS.map(key => [key, 0]))), 0);
  assert.equal(canonicalScores({ technical_capability: '55', professionalism: { score: 71 } }).spec_quality, 55);
  assert.equal(canonicalScores({ spec_quality: 'bad', technical_capability: 55 }).spec_quality, null);
  assert.equal(levelFromScore(null), null);
});
