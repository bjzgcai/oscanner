const ALLOWED_HOSTS = new Map([
  ['github.com', 'github'],
  ['www.github.com', 'github'],
  ['gitee.com', 'gitee'],
  ['www.gitee.com', 'gitee'],
]);

const REPO_SEGMENT_RE = /^[A-Za-z0-9._-]+$/;
const SSH_REPO_URL_RE = /^git@(?<host>github\.com|gitee\.com):(?<owner>[^/\s]+)\/(?<repo>[^/\s]+?)(?:\.git)?$/i;

const decodePathSegment = (segment) => {
  try {
    return decodeURIComponent(segment);
  } catch {
    return null;
  }
};

const normalizeOwnerRepo = (owner, repo) => {
  const normalizedOwner = owner.trim();
  let normalizedRepo = repo.trim();
  if (normalizedRepo.endsWith('.git')) {
    normalizedRepo = normalizedRepo.slice(0, -4);
  }

  if (!normalizedOwner || !normalizedRepo) return null;
  if (normalizedOwner === '.' || normalizedOwner === '..' || normalizedRepo === '.' || normalizedRepo === '..') {
    return null;
  }
  if (!REPO_SEGMENT_RE.test(normalizedOwner) || !REPO_SEGMENT_RE.test(normalizedRepo)) {
    return null;
  }

  return { owner: normalizedOwner, repo: normalizedRepo };
};

/**
 * Parse GitHub/Gitee repository URLs accepted by the backend.
 *
 * Supports:
 * - https://github.com/owner/repo
 * - github.com/owner/repo
 * - git@github.com:owner/repo.git
 * - https://github.com/owner/repo/tree/branch-or-commit
 *
 * @param {string} input
 * @returns {{ platform: 'github' | 'gitee', owner: string, repo: string, ref?: string } | null}
 */
export const parseRepoUrl = (input) => {
  let candidate = String(input || '').trim();
  if (!candidate) return null;

  const sshMatch = candidate.match(SSH_REPO_URL_RE);
  if (sshMatch?.groups) {
    const platform = ALLOWED_HOSTS.get(sshMatch.groups.host.toLowerCase());
    const normalized = normalizeOwnerRepo(sshMatch.groups.owner, sshMatch.groups.repo);
    return platform && normalized ? { platform, ...normalized } : null;
  }

  if (!candidate.includes('://')) {
    candidate = `https://${candidate}`;
  }

  let parsed;
  try {
    parsed = new URL(candidate);
  } catch {
    return null;
  }

  if (parsed.username || parsed.password) return null;

  const platform = ALLOWED_HOSTS.get(parsed.hostname.toLowerCase());
  if (!platform) return null;

  const pathParts = parsed.pathname
    .split('/')
    .filter(Boolean)
    .map(decodePathSegment);

  if (pathParts.some((part) => part === null) || pathParts.length < 2) {
    return null;
  }
  if (pathParts.length > 2 && pathParts[2] !== 'tree') {
    return null;
  }

  const normalized = normalizeOwnerRepo(pathParts[0], pathParts[1]);
  if (!normalized) return null;

  if (pathParts.length <= 2) {
    return { platform, ...normalized };
  }
  if (pathParts.length === 3) {
    return null;
  }

  const ref = pathParts.slice(3).join('/').replace(/^\/+|\/+$/g, '');
  return ref ? { platform, ...normalized, ref } : null;
};

/**
 * @param {string} input
 * @returns {boolean}
 */
export const validateRepoUrl = (input) => parseRepoUrl(input) !== null;
