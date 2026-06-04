import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { formatEmailListError, isValidEmail, parseEmailList } from './emailIdentity.mjs';

describe('email identity helpers', () => {
  it('parses comma and newline separated email identities', () => {
    assert.deepEqual(parseEmailList('Alice@Example.com, bob@example.dev\nalice@example.com'), {
      emails: ['alice@example.com', 'bob@example.dev'],
      invalidEmails: [],
    });
  });

  it('reports invalid email identities', () => {
    const parsed = parseEmailList('alice@example.com, not-an-email, bob@');

    assert.deepEqual(parsed.emails, ['alice@example.com']);
    assert.deepEqual(parsed.invalidEmails, ['not-an-email', 'bob@']);
    assert.equal(isValidEmail('not-an-email'), false);
    assert.equal(formatEmailListError(parsed.invalidEmails), 'Invalid email format: not-an-email, bob@');
  });
});
