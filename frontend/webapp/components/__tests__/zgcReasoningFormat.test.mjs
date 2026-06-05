import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  buildCommitUrl,
  buildRepositoryPathUrl,
  formatReasoningMarkdown,
  normalizeReasoningListBreaks,
} from '../../../../plugins/zgc_ai_native_2026/view/reasoningFormat.mjs';

describe('zgc reasoning formatting helpers', () => {
  it('builds GitHub and Gitee commit URLs from accepted repo URLs', () => {
    assert.equal(
      buildCommitUrl('https://github.com/octocat/Hello-World', 'df652479'),
      'https://github.com/octocat/Hello-World/commit/df652479'
    );
    assert.equal(
      buildCommitUrl('git@gitee.com:zgcai/oscanner.git', 'abcdef12'),
      'https://gitee.com/zgcai/oscanner/commit/abcdef12'
    );
    assert.equal(buildCommitUrl('https://github.com/octocat/%E0%A4%A', 'abcdef12'), null);
  });

  it('builds repository file and directory URLs', () => {
    assert.equal(
      buildRepositoryPathUrl('https://github.com/ZGCA-HMI-Lab/SceneParser', 'evaluation/inference_sceneparser.py', {
        commitSha: '12a27befd11e81bbb73c914c00c73e6a93bac765',
      }),
      'https://github.com/ZGCA-HMI-Lab/SceneParser/blob/12a27befd11e81bbb73c914c00c73e6a93bac765/evaluation/inference_sceneparser.py'
    );
    assert.equal(
      buildRepositoryPathUrl('https://github.com/ZGCA-HMI-Lab/SceneParser', 'evaluation/'),
      'https://github.com/ZGCA-HMI-Lab/SceneParser/tree/HEAD/evaluation'
    );
  });

  it('breaks inline numbered lists onto separate lines', () => {
    assert.equal(
      normalizeReasoningListBreaks(
        '评估判断：1. 无 AI 工程实践。 2. 半自动化脚本存在但无关 AI。 3. 项目性质偏向系统集成。'
      ),
      '评估判断：\n1. 无 AI 工程实践。\n2. 半自动化脚本存在但无关 AI。\n3. 项目性质偏向系统集成。'
    );
  });

  it('links bare collaboration commit SHAs without double-linking markdown links', () => {
    const formatted = formatReasoningMarkdown(
      '协作证据:\n- negative signals: df652479: add all\n- existing: [abcdef12](https://example.com/commit/abcdef12)',
      'https://github.com/octocat/Hello-World'
    );

    assert.match(
      formatted,
      /negative signals: \[df652479\]\(https:\/\/github\.com\/octocat\/Hello-World\/commit\/df652479\): add all/
    );
    assert.equal(
      formatted.includes('[[abcdef12](https://example.com/commit/abcdef12)]'),
      false
    );
  });

  it('cleans existing commit links and uses them to link collaboration SHAs without repoUrl', () => {
    const formatted = formatReasoningMarkdown(
      '证据:\n- commit [[12a27bef](https://github.com/ZGCA-HMI-Lab/SceneParser/commit/12a27bef)](https://github.com/ZGCA-HMI-Lab/SceneParser/commit/12a27befd11e81bbb73c914c00c73e6a93bac765): init\n\n协作证据:\n- negative signals: 12a27bef: init',
      undefined
    );

    assert.equal(
      formatted.includes(
        '[[12a27bef](https://github.com/ZGCA-HMI-Lab/SceneParser/commit/12a27bef)](https://github.com/ZGCA-HMI-Lab/SceneParser/commit/12a27befd11e81bbb73c914c00c73e6a93bac765)'
      ),
      false
    );
    assert.match(
      formatted,
      /commit \[12a27bef\]\(https:\/\/github\.com\/ZGCA-HMI-Lab\/SceneParser\/commit\/12a27befd11e81bbb73c914c00c73e6a93bac765\): init/
    );
    assert.match(
      formatted,
      /negative signals: \[12a27bef\]\(https:\/\/github\.com\/ZGCA-HMI-Lab\/SceneParser\/commit\/12a27befd11e81bbb73c914c00c73e6a93bac765\): init/
    );
  });

  it('links repository files and directories mentioned in reasoning', () => {
    const formatted = formatReasoningMarkdown(
      '证据:\n- commit [12a27bef](https://github.com/ZGCA-HMI-Lab/SceneParser/commit/12a27befd11e81bbb73c914c00c73e6a93bac765): init；文件：.gitignore, LICENSE, README.md, evaluation/inference_sceneparser.py\n评估判断：引入了模块化目录结构（evaluation/、finetuning/）。',
      undefined
    );

    assert.match(
      formatted,
      /\[evaluation\/inference_sceneparser\.py\]\(https:\/\/github\.com\/ZGCA-HMI-Lab\/SceneParser\/blob\/12a27befd11e81bbb73c914c00c73e6a93bac765\/evaluation\/inference_sceneparser\.py\)/
    );
    assert.match(
      formatted,
      /\[evaluation\/\]\(https:\/\/github\.com\/ZGCA-HMI-Lab\/SceneParser\/tree\/12a27befd11e81bbb73c914c00c73e6a93bac765\/evaluation\)/
    );
    assert.match(
      formatted,
      /\[finetuning\/\]\(https:\/\/github\.com\/ZGCA-HMI-Lab\/SceneParser\/tree\/12a27befd11e81bbb73c914c00c73e6a93bac765\/finetuning\)/
    );
  });

  it('uses structured evidence links to link repeated SHAs without repoUrl context', () => {
    const formatted = formatReasoningMarkdown(
      '提交 12a27bef 改进了结构。\n协作证据:\n- handoff artifacts: 12a27bef: init\n- negative signals: 12a27bef: init',
      undefined,
      [
        {
          type: 'commit',
          label: '12a27bef',
          sha: '12a27befd11e81bbb73c914c00c73e6a93bac765',
          url: 'https://github.com/ZGCA-HMI-Lab/SceneParser/commit/12a27befd11e81bbb73c914c00c73e6a93bac765',
        },
      ]
    );

    const matches = formatted.match(
      /\[12a27bef\]\(https:\/\/github\.com\/ZGCA-HMI-Lab\/SceneParser\/commit\/12a27befd11e81bbb73c914c00c73e6a93bac765\)/g
    );
    assert.equal(matches?.length, 3);
  });

  it('uses structured evidence links for files and directories without inferred repoUrl', () => {
    const formatted = formatReasoningMarkdown(
      '引入了模块化目录结构（evaluation/、finetuning/），并添加 evaluation/inference_sceneparser.py。',
      undefined,
      [
        {
          type: 'dir',
          label: 'evaluation/',
          path: 'evaluation/',
          commit_sha: '12a27befd11e81bbb73c914c00c73e6a93bac765',
          url: 'https://github.com/ZGCA-HMI-Lab/SceneParser/tree/12a27befd11e81bbb73c914c00c73e6a93bac765/evaluation',
        },
        {
          type: 'dir',
          label: 'finetuning/',
          path: 'finetuning/',
          commit_sha: '12a27befd11e81bbb73c914c00c73e6a93bac765',
          url: 'https://github.com/ZGCA-HMI-Lab/SceneParser/tree/12a27befd11e81bbb73c914c00c73e6a93bac765/finetuning',
        },
        {
          type: 'file',
          label: 'evaluation/inference_sceneparser.py',
          path: 'evaluation/inference_sceneparser.py',
          commit_sha: '12a27befd11e81bbb73c914c00c73e6a93bac765',
          url: 'https://github.com/ZGCA-HMI-Lab/SceneParser/blob/12a27befd11e81bbb73c914c00c73e6a93bac765/evaluation/inference_sceneparser.py',
        },
      ]
    );

    assert.match(
      formatted,
      /\[evaluation\/\]\(https:\/\/github\.com\/ZGCA-HMI-Lab\/SceneParser\/tree\/12a27befd11e81bbb73c914c00c73e6a93bac765\/evaluation\)/
    );
    assert.match(
      formatted,
      /\[finetuning\/\]\(https:\/\/github\.com\/ZGCA-HMI-Lab\/SceneParser\/tree\/12a27befd11e81bbb73c914c00c73e6a93bac765\/finetuning\)/
    );
    assert.match(
      formatted,
      /\[evaluation\/inference_sceneparser\.py\]\(https:\/\/github\.com\/ZGCA-HMI-Lab\/SceneParser\/blob\/12a27befd11e81bbb73c914c00c73e6a93bac765\/evaluation\/inference_sceneparser\.py\)/
    );
  });

  it('does not apply structured evidence links inside existing markdown links or code spans', () => {
    const formatted = formatReasoningMarkdown(
      '已有 [12a27bef](https://example.com/custom)，代码 `evaluation/`，正文 evaluation/。',
      undefined,
      [
        {
          type: 'commit',
          label: '12a27bef',
          sha: '12a27befd11e81bbb73c914c00c73e6a93bac765',
          url: 'https://github.com/ZGCA-HMI-Lab/SceneParser/commit/12a27befd11e81bbb73c914c00c73e6a93bac765',
        },
        {
          type: 'dir',
          label: 'evaluation/',
          path: 'evaluation/',
          url: 'https://github.com/ZGCA-HMI-Lab/SceneParser/tree/HEAD/evaluation',
        },
      ]
    );

    assert.match(formatted, /\[12a27bef\]\(https:\/\/example\.com\/custom\)/);
    assert.match(formatted, /`evaluation\/`/);
    assert.match(formatted, /正文 \[evaluation\/\]\(https:\/\/github\.com\/ZGCA-HMI-Lab\/SceneParser\/tree\/HEAD\/evaluation\)/);
  });
});
