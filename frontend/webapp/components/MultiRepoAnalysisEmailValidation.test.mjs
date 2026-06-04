import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(resolve(__dirname, './MultiRepoAnalysis.tsx'), 'utf8');

test('multi repo analysis validates and sends email identities', () => {
  assert.match(source, /parseEmailList/);
  assert.match(source, /author_emails/);
  assert.doesNotMatch(source, /author_aliases:\s*authorAliases/);
});
