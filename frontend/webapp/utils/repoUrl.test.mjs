import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { parseRepoUrl, validateRepoUrl } from './repoUrl.mjs';

describe('repoUrl helpers', () => {
  it('accepts GitHub and Gitee tree URLs with branch or commit refs', () => {
    assert.equal(
      validateRepoUrl('https://github.com/bjzgcai/oscanner/tree/9ba36e6a104ab1ffe296e0f71cf596bca12b2d6a'),
      true
    );
    assert.deepEqual(
      parseRepoUrl('https://github.com/bjzgcai/oscanner/tree/9ba36e6a104ab1ffe296e0f71cf596bca12b2d6a'),
      {
        platform: 'github',
        owner: 'bjzgcai',
        repo: 'oscanner',
        ref: '9ba36e6a104ab1ffe296e0f71cf596bca12b2d6a',
      }
    );
    assert.deepEqual(
      parseRepoUrl('https://gitee.com/zgcai/oscanner/tree/feat/update-gitee-ci-pipelines'),
      {
        platform: 'gitee',
        owner: 'zgcai',
        repo: 'oscanner',
        ref: 'feat/update-gitee-ci-pipelines',
      }
    );
  });

  it('accepts existing repository URL formats', () => {
    assert.deepEqual(parseRepoUrl('github.com/octocat/Hello-World.git'), {
      platform: 'github',
      owner: 'octocat',
      repo: 'Hello-World',
    });
    assert.deepEqual(parseRepoUrl('git@gitee.com:zgcai/oscanner.git'), {
      platform: 'gitee',
      owner: 'zgcai',
      repo: 'oscanner',
    });
  });

  it('rejects substring host attacks and unsupported deep paths', () => {
    assert.equal(validateRepoUrl('https://evilgithub.com/octocat/Hello-World'), false);
    assert.equal(validateRepoUrl('https://github.com/octocat/Hello-World/pull/1'), false);
  });
});
