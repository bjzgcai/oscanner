const ALLOWED_HOSTS = new Map([
  ['github.com', 'github'],
  ['www.github.com', 'github'],
  ['gitee.com', 'gitee'],
  ['www.gitee.com', 'gitee'],
]);

const SSH_REPO_URL_RE = /^git@(?<host>github\.com|gitee\.com):(?<owner>[^/\s]+)\/(?<repo>[^/\s]+?)(?:\.git)?$/i;
const REPO_SEGMENT_RE = /^[A-Za-z0-9._-]+$/;
const SHA_RE = /^[0-9a-f]{7,40}$/i;
const INLINE_NUMBERED_LIST_START_RE = /([:：])\s*(?=(?:[1-9]|[1-9][0-9])\.\s*[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaffA-Za-z])/g;
const INLINE_NUMBERED_ITEM_RE = /(?<!^)(?<!\n)\s+(?=(?:[1-9]|[1-9][0-9])\.\s*[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaffA-Za-z])/g;
const PROTECTED_MARKDOWN_RE = /(\[[^\]]+\]\([^)]+\)|`[^`]+`)/g;
const COMMIT_URL_RE = /https?:\/\/(?:www\.)?(?:github\.com|gitee\.com)\/[A-Za-z0-9._-]+\/[A-Za-z0-9._-]+\/commit\/[0-9a-f]{7,40}/gi;
const MARKDOWN_COMMIT_LINK_RE = /\[`?([0-9a-f]{7,40})`?\]\((https?:\/\/(?:www\.)?(?:github\.com|gitee\.com)\/[A-Za-z0-9._-]+\/[A-Za-z0-9._-]+\/commit\/[0-9a-f]{7,40})\)/gi;
const NESTED_MARKDOWN_COMMIT_LINK_RE = /\[\[([0-9a-f]{7,40})\]\((https?:\/\/(?:www\.)?(?:github\.com|gitee\.com)\/[A-Za-z0-9._-]+\/[A-Za-z0-9._-]+\/commit\/[0-9a-f]{7,40})\)\]\((https?:\/\/(?:www\.)?(?:github\.com|gitee\.com)\/[A-Za-z0-9._-]+\/[A-Za-z0-9._-]+\/commit\/[0-9a-f]{7,40})\)/gi;
const LINKABLE_PATH_RE = /(?<![A-Za-z0-9@:/])((?:[A-Za-z0-9._-]+\/)+(?:[A-Za-z0-9._-]+(?:\.[A-Za-z0-9._-]+)?|)|\.[A-Za-z0-9._-]+|README(?:\.[A-Za-z0-9]+)?|LICENSE|Makefile|Dockerfile|CMakeLists\.txt|package\.xml|package\.json|pyproject\.toml)(?![A-Za-z0-9_./-])/g;

function normalizeOwnerRepo(owner, repo) {
  const normalizedOwner = String(owner || '').trim();
  let normalizedRepo = String(repo || '').trim();
  if (normalizedRepo.endsWith('.git')) {
    normalizedRepo = normalizedRepo.slice(0, -4);
  }
  if (!REPO_SEGMENT_RE.test(normalizedOwner) || !REPO_SEGMENT_RE.test(normalizedRepo)) {
    return null;
  }
  return { owner: normalizedOwner, repo: normalizedRepo };
}

function decodePathSegment(segment) {
  try {
    return decodeURIComponent(segment);
  } catch {
    return null;
  }
}

function encodePath(value) {
  return String(value || '')
    .split('/')
    .filter(Boolean)
    .map((part) => encodeURIComponent(part))
    .join('/');
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function parseRepoRoot(input) {
  let candidate = String(input || '').trim();
  if (!candidate) return null;

  const sshMatch = candidate.match(SSH_REPO_URL_RE);
  if (sshMatch?.groups) {
    const platform = ALLOWED_HOSTS.get(sshMatch.groups.host.toLowerCase());
    const normalized = normalizeOwnerRepo(sshMatch.groups.owner, sshMatch.groups.repo);
    return platform && normalized ? { platform, ...normalized, ref: null } : null;
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

  const pathParts = parsed.pathname.split('/').filter(Boolean);
  if (pathParts.length < 2) return null;
  const owner = decodePathSegment(pathParts[0]);
  const repo = decodePathSegment(pathParts[1]);
  if (!owner || !repo) return null;
  const normalized = normalizeOwnerRepo(owner, repo);
  const ref = pathParts[2] === 'tree' && pathParts.length > 3
    ? pathParts.slice(3).map(decodePathSegment).filter(Boolean).join('/')
    : null;
  return normalized ? { platform, ...normalized, ref } : null;
}

function parseCommitUrl(input) {
  let parsed;
  try {
    parsed = new URL(String(input || '').trim());
  } catch {
    return null;
  }

  const platform = ALLOWED_HOSTS.get(parsed.hostname.toLowerCase());
  if (!platform) return null;

  const pathParts = parsed.pathname.split('/').filter(Boolean).map(decodePathSegment);
  if (pathParts.some((part) => part === null) || pathParts.length < 4 || pathParts[2] !== 'commit') {
    return null;
  }

  const normalized = normalizeOwnerRepo(pathParts[0], pathParts[1]);
  const sha = pathParts[3];
  if (!normalized || !SHA_RE.test(sha)) return null;

  const host = platform === 'gitee' ? 'gitee.com' : 'github.com';
  const owner = encodeURIComponent(normalized.owner);
  const repo = encodeURIComponent(normalized.repo);
  return {
    platform,
    owner: normalized.owner,
    repo: normalized.repo,
    sha,
    repoUrl: `https://${host}/${owner}/${repo}`,
    url: `https://${host}/${owner}/${repo}/commit/${sha}`,
  };
}

function recordCommitRef(commitRefs, displaySha, url) {
  const info = parseCommitUrl(url);
  if (!info) return null;

  const display = String(displaySha || info.sha.slice(0, 8)).trim();
  const normalizedDisplay = SHA_RE.test(display) ? display : info.sha.slice(0, 8);
  const ref = {
    displaySha: normalizedDisplay,
    sha: info.sha,
    url: info.url,
    repoUrl: info.repoUrl,
  };
  commitRefs.push(ref);
  return ref;
}

function commitLinkMarkdown(ref) {
  return `[${ref.displaySha}](${ref.url})`;
}

function protectMarkdownSegments(markdown, tokenStart = '\uE000', tokenEnd = '\uE001') {
  const protectedSegments = [];
  const text = String(markdown || '').replace(PROTECTED_MARKDOWN_RE, (segment) => {
    const token = `${tokenStart}${protectedSegments.length}${tokenEnd}`;
    protectedSegments.push(segment);
    return token;
  });
  const restore = (value) => String(value || '').replace(
    new RegExp(`${escapeRegExp(tokenStart)}(\\d+)${escapeRegExp(tokenEnd)}`, 'g'),
    (_, index) => protectedSegments[Number(index)] || ''
  );
  return { text, restore };
}

function normalizeExistingCommitLinks(markdown, commitRefs) {
  const protectedSegments = [];
  const protect = (segment) => {
    const token = `\uE100${protectedSegments.length}\uE101`;
    protectedSegments.push(segment);
    return token;
  };

  let text = String(markdown || '').replace(NESTED_MARKDOWN_COMMIT_LINK_RE, (_match, displaySha, _innerUrl, outerUrl) => {
    const ref = recordCommitRef(commitRefs, displaySha, outerUrl);
    return ref ? protect(commitLinkMarkdown(ref)) : _match;
  });

  text = text.replace(MARKDOWN_COMMIT_LINK_RE, (_match, displaySha, url) => {
    const ref = recordCommitRef(commitRefs, displaySha, url);
    return ref ? protect(commitLinkMarkdown(ref)) : _match;
  });

  text = text.replace(COMMIT_URL_RE, (url) => {
    const ref = recordCommitRef(commitRefs, '', url);
    return ref ? commitLinkMarkdown(ref) : url;
  });

  return text.replace(/\uE100(\d+)\uE101/g, (_, index) => protectedSegments[Number(index)] || '');
}

function cleanEvidenceLinkUrl(url) {
  const value = String(url || '').trim();
  if (!value) return null;
  try {
    const parsed = new URL(value);
    if (!['https:', 'http:'].includes(parsed.protocol)) return null;
    const platform = ALLOWED_HOSTS.get(parsed.hostname.toLowerCase());
    return platform ? parsed.toString() : null;
  } catch {
    return null;
  }
}

function addEvidenceTerm(terms, term, url, kind) {
  const text = String(term || '').trim();
  if (!text || text.length < 2 || !url) return;
  const key = `${kind}:${text.toLowerCase()}`;
  if (terms.has(key)) return;
  terms.set(key, { text, url, kind });
}

function evidenceTerms(evidenceLinks) {
  const terms = new Map();
  for (const link of Array.isArray(evidenceLinks) ? evidenceLinks : []) {
    if (!link || typeof link !== 'object') continue;
    const url = cleanEvidenceLinkUrl(link.url);
    if (!url) continue;
    const type = String(link.type || '').toLowerCase();
    const aliases = Array.isArray(link.aliases) ? link.aliases : [];
    if (type === 'commit') {
      const sha = String(link.sha || '').trim();
      const label = String(link.label || link.text || '').trim();
      if (SHA_RE.test(sha)) {
        addEvidenceTerm(terms, sha, url, 'sha');
        addEvidenceTerm(terms, sha.slice(0, 8), url, 'sha');
      }
      if (SHA_RE.test(label)) {
        addEvidenceTerm(terms, label, url, 'sha');
      }
      for (const alias of aliases) {
        if (SHA_RE.test(String(alias || '').trim())) {
          addEvidenceTerm(terms, alias, url, 'sha');
        }
      }
      continue;
    }

    if (type === 'file' || type === 'dir') {
      const path = String(link.path || link.label || link.text || '').replace(/\\/g, '/').trim();
      const label = String(link.label || link.text || '').replace(/\\/g, '/').trim();
      const kind = 'path';
      addEvidenceTerm(terms, path, url, kind);
      addEvidenceTerm(terms, label, url, kind);
      if (type === 'dir') {
        const normalizedPath = path.replace(/^\/+|\/+$/g, '');
        const normalizedLabel = label.replace(/^\/+|\/+$/g, '');
        addEvidenceTerm(terms, normalizedPath ? `${normalizedPath}/` : '', url, kind);
        addEvidenceTerm(terms, normalizedLabel ? `${normalizedLabel}/` : '', url, kind);
      }
      for (const alias of aliases) {
        addEvidenceTerm(terms, alias, url, kind);
      }
    }
  }

  return Array.from(terms.values()).sort((a, b) => b.text.length - a.text.length);
}

function termPattern(term) {
  const escaped = escapeRegExp(term.text);
  if (term.kind === 'sha') {
    return `(?<![A-Za-z0-9/])${escaped}(?![A-Za-z0-9])`;
  }
  return `(?<![A-Za-z0-9@:/])${escaped}(?![A-Za-z0-9_./-])`;
}

function applyEvidenceLinks(markdown, evidenceLinks) {
  const terms = evidenceTerms(evidenceLinks);
  if (!terms.length) return markdown;

  const { text, restore } = protectMarkdownSegments(markdown, '\uE300', '\uE301');
  const patterns = terms.map((term) => `(${termPattern(term)})`);
  const matcher = new RegExp(patterns.join('|'), 'gi');
  const linked = text.replace(matcher, (match, ...groups) => {
    const index = groups.findIndex((group) => typeof group === 'string' && group !== undefined);
    const term = index >= 0 ? terms[index] : null;
    return term ? `[${match}](${term.url})` : match;
  });

  return restore(linked);
}

export function buildCommitUrl(repoUrl, sha) {
  const cleanedSha = String(sha || '').trim();
  if (!SHA_RE.test(cleanedSha)) return null;
  const parsed = parseRepoRoot(repoUrl);
  if (!parsed) return null;

  const host = parsed.platform === 'gitee' ? 'gitee.com' : 'github.com';
  const owner = encodeURIComponent(parsed.owner);
  const repo = encodeURIComponent(parsed.repo);
  return `https://${host}/${owner}/${repo}/commit/${cleanedSha}`;
}

export function buildRepositoryPathUrl(repoUrl, path, options = {}) {
  const cleanedPath = String(path || '').trim().replace(/^\/+|\/+$/g, '');
  if (!cleanedPath || cleanedPath === '.' || cleanedPath === '..') return null;

  const parsed = parseRepoRoot(repoUrl);
  if (!parsed) return null;

  const commitSha = String(options.commitSha || '').trim();
  const ref = SHA_RE.test(commitSha) ? commitSha : (parsed.ref || 'HEAD');
  const isDirectory = String(path || '').trim().endsWith('/');
  const kind = isDirectory ? 'tree' : 'blob';
  const host = parsed.platform === 'gitee' ? 'gitee.com' : 'github.com';
  const owner = encodeURIComponent(parsed.owner);
  const repo = encodeURIComponent(parsed.repo);
  const encodedRef = encodePath(ref);
  const encodedPath = encodePath(cleanedPath);
  return encodedRef && encodedPath ? `https://${host}/${owner}/${repo}/${kind}/${encodedRef}/${encodedPath}` : null;
}

export function normalizeReasoningListBreaks(reasoning) {
  return String(reasoning || '')
    .replace(/\\n\\n/g, '\n\n')
    .replace(/\\n/g, '\n')
    .replace(INLINE_NUMBERED_LIST_START_RE, '$1\n')
    .replace(INLINE_NUMBERED_ITEM_RE, '\n')
    .trim();
}

export function formatReasoningMarkdown(reasoning, repoUrl, evidenceLinks = []) {
  const commitRefs = [];
  let normalized = normalizeExistingCommitLinks(normalizeReasoningListBreaks(reasoning), commitRefs);
  normalized = applyEvidenceLinks(normalized, evidenceLinks);
  const inferredRepoUrl = repoUrl || commitRefs[0]?.repoUrl || null;
  const inferredCommitSha = commitRefs[0]?.sha || null;
  if (!inferredRepoUrl) return normalized;

  const commitUrlBySha = new Map();
  for (const ref of commitRefs) {
    commitUrlBySha.set(ref.sha.toLowerCase(), ref.url);
    commitUrlBySha.set(ref.sha.slice(0, 8).toLowerCase(), ref.url);
    commitUrlBySha.set(ref.displaySha.toLowerCase(), ref.url);
  }

  const protectedInitial = protectMarkdownSegments(normalized, '\uE000', '\uE001');
  const protectedText = protectedInitial.text;

  const withCommitLinks = protectedText.replace(/(?<![A-Za-z0-9/])([0-9a-f]{7,40})(?![A-Za-z0-9])/gi, (match) => {
    const url = commitUrlBySha.get(match.toLowerCase()) || buildCommitUrl(inferredRepoUrl, match);
    return url ? `[${match}](${url})` : match;
  });

  const commitLinkSegments = [];
  const commitLinksProtected = withCommitLinks.replace(PROTECTED_MARKDOWN_RE, (segment) => {
    const token = `\uE200${commitLinkSegments.length}\uE201`;
    commitLinkSegments.push(segment);
    return token;
  });

  const withPathLinks = commitLinksProtected.replace(LINKABLE_PATH_RE, (match) => {
    const url = buildRepositoryPathUrl(inferredRepoUrl, match, { commitSha: inferredCommitSha });
    return url ? `[${match}](${url})` : match;
  });

  const restoredCommitLinks = withPathLinks.replace(
    /\uE200(\d+)\uE201/g,
    (_, index) => commitLinkSegments[Number(index)] || ''
  );
  return protectedInitial.restore(restoredCommitLinks);
}
