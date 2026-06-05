import React from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';

import type { EvidenceLink } from '../../_shared/view/types';
import { buildCommitUrl, formatReasoningMarkdown } from './reasoningFormat.mjs';

type ReasoningMarkdownProps = {
  reasoning: string;
  repoUrl?: string | null;
  evidenceLinks?: EvidenceLink[] | null;
};

export default function ReasoningMarkdown({ reasoning, repoUrl, evidenceLinks }: ReasoningMarkdownProps) {
  const markdown = formatReasoningMarkdown(reasoning, repoUrl, evidenceLinks ?? undefined);

  const components: Components = {
    a({ href, children }) {
      return (
        <a href={href} target="_blank" rel="noreferrer">
          {children}
        </a>
      );
    },
    code({ children, className }) {
      const text = String(children ?? '').trim();
      const commitUrl = repoUrl ? buildCommitUrl(repoUrl, text) : null;
      const code = <code className={className}>{children}</code>;
      if (!commitUrl) {
        return code;
      }
      return (
        <a href={commitUrl} target="_blank" rel="noreferrer">
          {code}
        </a>
      );
    },
  };

  return (
    <div style={{ whiteSpace: 'pre-wrap' }}>
      <ReactMarkdown components={components}>{markdown}</ReactMarkdown>
    </div>
  );
}
