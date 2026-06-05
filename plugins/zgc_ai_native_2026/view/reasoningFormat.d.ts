export function buildCommitUrl(repoUrl: string | undefined | null, sha: string): string | null;
export function buildRepositoryPathUrl(
  repoUrl: string | undefined | null,
  path: string,
  options?: { commitSha?: string | null }
): string | null;
export function normalizeReasoningListBreaks(reasoning: string | undefined | null): string;
export type EvidenceLink = {
  type?: 'commit' | 'file' | 'dir' | string;
  label?: string;
  text?: string;
  url?: string;
  sha?: string;
  commit_sha?: string;
  path?: string;
  aliases?: string[];
};
export function formatReasoningMarkdown(
  reasoning: string | undefined | null,
  repoUrl?: string | null,
  evidenceLinks?: EvidenceLink[] | null
): string;
