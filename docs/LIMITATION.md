# Oscanner Limitations and Roadmap

Last reviewed: 2026-06-04

This document records known constraints in the current Oscanner implementation
and turns the earlier limitation notes into a future development roadmap. The
goal is to keep product decisions explicit: what the evaluator already guards
against, what it intentionally excludes, and what should be improved next.

## Current Technical Limits

| Area | Current limit or behavior | Impact |
| --- | --- | --- |
| GitHub authenticated rate limit | About 5,000 requests/hour per token | Large batch extraction and trajectory jobs can exhaust a token quickly. |
| GitHub unauthenticated rate limit | Much lower than authenticated access | Users should configure `GITHUB_TOKEN` for reliable extraction. |
| Gitee rate limits | Token-dependent and less predictable than GitHub | Gitee batch work needs retry, caching, and user-visible token checks. |
| Contents API file size | GitHub Contents API is not suitable for large file payloads; previous note tracked `< 1MB` base64 responses | Prefer tree/blob APIs, filtered snapshots, and size guards over reading arbitrary files through contents endpoints. |
| Tree recursion | Previous note tracked `100,000` tree entries as the practical recursion ceiling | Very large monorepos can produce incomplete snapshots or costly extraction. |
| Repository evaluation size | 10M-token evaluator guardrail | Evaluation stops before LLM work when a repository exceeds the guardrail. |
| Long-running work | SSE can be interrupted by browsers, proxies, or deployment platforms | Polling alternatives exist for selected runner and trajectory flows, but coverage should be expanded. |
| External repository execution | Runner executes untrusted code in host or Docker modes | Docker/auto mode and safe command allowlists reduce risk but do not remove all risk. |

## Repository Size Guardrail

The evaluator has a 10M-token guardrail. The check lives in
`backend/evaluator/services/evaluation_service.py` and stops evaluation with
HTTP 413 and this exact detail:

```text
the repo is too big exceeding 10M tokens!
```

The guardrail currently runs before evaluator/LLM work in these paths:

- Main incremental evaluator path.
- Gitee contributor evaluation route.
- Trajectory and group evaluation paths.

Future changes that add new evaluator entry points must apply the same guardrail
before constructing prompts or calling an LLM.

## Current Product Limitations

### Provider Parity Is Still Active Work

GitHub and Gitee are both first-class providers, but their APIs differ in commit
metadata, contributor discovery, review/comment availability, tree traversal,
tags, refs, and rate limits. Every provider-facing feature should either support
both providers or document an intentional limitation.

Known pressure points:

- Branch, tag, and boundary-SHA behavior must remain equivalent for GitHub and
  Gitee trajectory/group workflows.
- Review-comment evidence is easier to collect on GitHub than on Gitee.
- Enterprise Gitee behavior may differ from public Gitee endpoints.

### PR, Issue, and Collaboration Evidence Is Incomplete

The current evaluation relies heavily on commits, diffs, repository structure,
tests, CI, documentation, and selected collaboration evidence. It does not yet
fully model a contributor's PR review quality, issue triage, design discussion,
or cross-repository maintenance footprint.

This matters because senior engineering work often appears in:

- Review comments and requested changes.
- Issue analysis and reproduction quality.
- Design docs, ADRs, and roadmap discussions.
- Release management and maintainer decisions.
- Cross-team collaboration outside direct commits.

### Forks and Stars Are Intentionally Excluded

Fork and star counts are not considered in scoring. They are easy to manipulate,
are weak evidence for contribution quality, and can reward popularity rather than
engineering behavior. If they are ever shown in the UI, they should be labeled as
context only, not score inputs.

### Email-Based Identity Expansion Needs Privacy Controls

Using a user's email address to find all public footprints could discover repos
they contributed to, pull requests they opened, issues they filed, and aliases
they used. That may improve author matching, but it introduces privacy and terms
of service concerns.

Any email-first expansion must be:

- Opt-in and transparent.
- Limited to data sources allowed by provider terms.
- Scoped to public or user-authorized data.
- Auditable in the UI, so users can see which identities and repositories were
  included.
- Easy to disable or edit before evaluation.

Raw emails and tokens must not be logged or returned. When a secret must be
displayed for debugging, mask it as the first 4 and last 4 characters.

### LLM Scoring Is Evidence-Guided, Not Ground Truth

The plugin rubric asks the model to map repository evidence to behavior levels,
but the score is still model-mediated. Risks include:

- Prompt sensitivity across providers and model versions.
- False confidence when evidence is sparse.
- Inconsistent scoring for multilingual repositories.
- Overweighting visible artifacts and underweighting hidden team work.
- Parse failures when the model returns unexpected structure.

Benchmarks, deterministic prechecks, parser hardening, and score calibration are
needed to make results more reliable.

### Deployment Notes Are Not Productized

The earlier notes mention Vercel setup, but the implemented dashboard
supports local split-origin development and packaged same-origin behavior. A
future deployment guide should cover:

- Static Next.js export and backend same-origin packaging.
- Environment variables for local, server, and hosted deployments.
- Reverse-proxy behavior for API and static dashboard routes.
- Long-running SSE or polling behavior behind common proxies.
- Vercel-specific limitations if the frontend is hosted separately from the
  FastAPI backend.

## Future Development Roadmap

### Phase 1: Reliability and Guardrails

- Keep the 10M-token guardrail applied to every evaluator entry point.
- Add user-visible explanations when extraction is partial because of rate
  limits, tree limits, file-size limits, or token-size limits.
- Expand poll-mode equivalents for every long-running SSE workflow.
- Add retry/backoff policies with clear failure states for GitHub and Gitee rate
  limits.
- Surface provider token status in the dashboard before a large job starts.
- Add tests for corrupted cache files, missing commit windows, oversized
  repositories, and interrupted streaming jobs.

### Phase 2: Provider Parity

- Maintain one provider parity checklist for extraction, authors, commits, tags,
  branches, review evidence, issues, trajectories, group analysis, and runner
  URL validation.
- Extend Gitee tree and review/comment collection where public APIs allow it.
- Add enterprise Gitee compatibility tests for URL parsing and API response
  shapes.
- Make provider limitations explicit in API responses and dashboard result
  panels.
- Keep GitHub and Gitee behavior covered in route-level tests whenever one
  provider path changes.

### Phase 3: Collaboration Evidence

- Add structured PR evidence where provider APIs allow it:
  - Pull/merge request authorship.
  - Review comments.
  - Requested changes.
  - Review approvals.
  - Linked commits.
- Add issue evidence:
  - Opened issues.
  - Reproduction quality.
  - Bug triage and labels.
  - Resolution links to commits or PRs.
- Separate contribution signals into "direct code", "review", "issue/design",
  and "maintenance" evidence so the model can reason over each explicitly.
- Keep forks and stars excluded from scoring unless a future rubric explicitly
  treats them as non-scoring context.

### Phase 4: Identity and Consent

- Build an opt-in identity resolution workflow for usernames, emails, and commit
  aliases.
- Show users the proposed identity set before evaluation.
- Allow users to remove aliases and repositories from the candidate footprint.
- Store only the minimum identity data needed for repeatable evaluation.
- Add provider-specific terms and privacy warnings near email-based discovery.

### Phase 5: Evaluation Quality

- Expand benchmark datasets with pinned repos, fixed commits, expected evidence,
  and human-reviewed score bands.
- Add regression tests for plugin parser edge cases and multilingual headings.
- Add deterministic precheck features for tests, lockfiles, CI, Docker, docs,
  IaC, agent/tooling traces, and security posture.
- Calibrate plugin scoring with benchmark results before changing prompts.
- Track model, provider, prompt version, token usage, and parse fallback details
  in each persisted evaluation.

### Phase 6: Runner Safety and Coverage

- Prefer Docker executor mode for public or unknown repositories.
- Document and test the safe startup command allowlist.
- Add stronger artifact path validation and retention policies.
- Expand language-specific test detection where coverage is currently shallow.
- Make runtime screenshot and service/API evidence deterministic enough for
  automated consumers.
- Treat LLM-suggested compatibility commands as hints only, with validation and
  audit logs.

### Phase 7: Deployment and Operations

- Write a deployment guide for:
  - Local development.
  - Packaged same-origin dashboard.
  - Reverse-proxy production.
  - Separate hosted frontend and backend.
  - Vercel frontend deployment, if still desired.
- Add health checks for evaluator, runner, dashboard static assets, configured
  tokens, and LLM provider access.
- Add operational dashboards or logs for batch jobs, token usage, rate-limit
  failures, and queue depth.
- Define backup and cleanup policy for extracted data, runner clones, and test
  reports.

## Acceptance Criteria for Future Work

Future roadmap items should be considered complete only when they include:

- API behavior documented in `specs/`.
- Targeted backend tests for success and failure paths.
- Provider parity tests or an explicit limitation note.
- Frontend handling for loading, success, failure, and partial-data states when
  the feature is user-facing.
- Security review for repository URLs, author identities, file paths, tokens,
  and untrusted code execution.
