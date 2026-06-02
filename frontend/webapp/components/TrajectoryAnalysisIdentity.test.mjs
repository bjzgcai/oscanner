import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(resolve(__dirname, './TrajectoryAnalysis.tsx'), 'utf8');

test('trajectory author selection uses email instead of author name as the row identity', () => {
  assert.match(source, /rowKey=\{\(record\) => getAuthorSelectionKey\(record\)\}/);
  assert.doesNotMatch(source, /rowKey="author"/);
  assert.doesNotMatch(source, /prev\.includes\(record\.author\)/);
});
