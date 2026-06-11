# GitHub API Notes

> Legal/privacy note: use these collection workflows only within the constraints
> in [Legal And Privacy Use Constraints](legal_privacy.md).

## Global Commit Search By Email

GitHub commit search can find commits across visible repositories by matching
the email stored in Git commit metadata.

Use `author-email:<email>` to match the commit author email:

```bash
gh search commits --author-email "person@example.com" \
  --json sha,url,repository,authorDate
```

Equivalent REST search:

```bash
curl -H "Accept: application/vnd.github+json" \
  "https://api.github.com/search/commits?q=author-email:person@example.com&per_page=100"
```

This corresponds to the email in the commit object:

```json
{
  "commit": {
    "author": {
      "email": "person@example.com"
    }
  }
}
```

Use `committer-email:<email>` to match the commit committer email:

```bash
gh search commits "committer-email:person@example.com" \
  --json sha,url,repository,committerDate
```

Equivalent REST search:

```bash
curl -H "Accept: application/vnd.github+json" \
  "https://api.github.com/search/commits?q=committer-email:person@example.com&per_page=100"
```

This corresponds to the email in the commit object:

```json
{
  "commit": {
    "committer": {
      "email": "person@example.com"
    }
  }
}
```

Notes:

- The GitHub search qualifier is `committer-email`, not `commit-email`.
- Search is global across repositories visible to the authenticated caller, unless
  narrowed with qualifiers such as `repo:OWNER/REPO`, `org:ORG`, or `user:USER`.
- GitHub search is limited to the repository default branch.
- The search API returns at most 1,000 results for a query, with up to 100
  results per page.
- Private repositories require authentication and repository access.
- The matched email is the raw Git commit metadata email. It may be a GitHub
  no-reply address and does not necessarily equal the user's account email.

## Pull Request Evidence From Email

GitHub does not provide a reliable global pull request search by email. Global
pull request search is based on issue/PR qualifiers such as `type:pr` and
`author:USERNAME`, where `author` is a GitHub login or app account, not an
email address.

If only an email address is known, use commits as the discovery path:

1. Search global commits by `author-email:<email>`.
2. Extract `repository.full_name` and `sha` from each commit result.
3. Call the repository-scoped associated PR endpoint for each commit:

```bash
curl -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/OWNER/REPO/commits/COMMIT_SHA/pulls"
```

GitHub describes this endpoint as returning the merged pull request that
introduced the commit to the repository. If the commit is not present in the
default branch, it can return merged and open pull requests associated with the
commit.

When a GitHub login is known, pull requests can also be searched directly:

```bash
curl -H "Accept: application/vnd.github+json" \
  "https://api.github.com/search/issues?q=type:pr+author:USERNAME&per_page=100"
```

Use the PR result as relationship evidence, not as the primary identity match,
unless the GitHub login is known or can be confidently linked.

Attribution guidance:

- Prefer `commit.author.email` / `author-email:<email>` for code authorship
  evidence. This is the person recorded as writing the commit.
- Treat `commit.committer.email` / `committer-email:<email>` as separate and
  weaker evidence. The committer is the person or system that created/applied
  the Git object; it may be a maintainer, GitHub's web UI, a bot, or a merge
  process.
- Do not use `committer-email` as the main way to attribute a pull request to a
  user. Use it only for "applied/committed by" evidence.
- Relate pull requests to the user through commits whose `commit.author.email`
  matches the target email, then enrich those commits with associated PRs,
  changed files, reviews, comments, merge state, and timestamps.
- If the associated PR's `user.login` matches a GitHub account already linked
  to the email-derived commits, that is stronger PR authorship evidence.
- Squash merges, rebases, cherry-picks, bot-authored commits, and GitHub
  no-reply addresses can weaken or obscure the relationship. Keep raw evidence
  fields so downstream scoring can distinguish strong and weak matches.

## Pull Request Fields Worth Collecting

Pull request data is important for evaluating engineering capability. Commits
show code contribution, but PRs show how the contribution moved through a real
engineering workflow: scope, review quality, collaboration, responsiveness,
merge outcome, and maintainability signals.

For each PR associated with a matched commit, collect at least:

- PR metadata: `id`, `number`, `html_url`, `state`, `draft`, `locked`, `title`,
  `body`, `user.login`, `author_association`, `created_at`, `updated_at`,
  `closed_at`, `merged_at`, `merge_commit_sha`, `base`, `head`, labels,
  assignees, requested reviewers, and requested teams.
- PR size and code shape: commits, changed files, additions, deletions,
  changed file paths, statuses, and patch/diff URLs when available.
- PR commits: all commits on the PR, preserving each commit's `author.email`,
  `committer.email`, GitHub `author.login`, GitHub `committer.login`, SHA, and
  dates.
- Reviews: reviewer login, review state (`APPROVED`, `CHANGES_REQUESTED`,
  `COMMENTED`, etc.), submitted time, body, author association, and commit ID.
- Review comments: line-level discussion on code, including commenter login,
  body, path, diff hunk, line/original line, side, commit ID, timestamps, and
  whether the comment is outdated or resolved when available.
- Issue comments on the PR: general conversation comments, including commenter
  login, body, author association, timestamps, and reactions when available.

Useful REST endpoints after discovering a PR:

```bash
# PR metadata
GET /repos/{owner}/{repo}/pulls/{pull_number}

# Commits included in the PR
GET /repos/{owner}/{repo}/pulls/{pull_number}/commits

# Files changed by the PR
GET /repos/{owner}/{repo}/pulls/{pull_number}/files

# Submitted reviews
GET /repos/{owner}/{repo}/pulls/{pull_number}/reviews

# Line-level review comments across the PR
GET /repos/{owner}/{repo}/pulls/{pull_number}/comments

# General conversation comments, because pull requests are also issues
GET /repos/{owner}/{repo}/issues/{issue_number}/comments
```

Evaluation value:

- Code authorship: matched commits and changed files show what the user likely
  wrote.
- Technical complexity: file types, code churn, test changes, dependency
  changes, and patch shape help estimate difficulty.
- Collaboration: review threads and issue comments show how the user explains
  decisions, responds to feedback, and negotiates tradeoffs.
- Quality signal: review outcomes, requested changes, follow-up commits, CI
  status, and merge result show whether the work was accepted and how much
  iteration it needed.
- Review capability: if the target user is the reviewer/commenter rather than
  the PR author, their review comments and review state are direct evidence of
  code review ability.

Identity and attribution rules:

- If only email is known, start from commits matched by `author-email:<email>`.
  This is the strongest email-only code authorship signal.
- Connect PRs to the user through those matched commits, not through PR author
  alone.
- If the PR `user.login` can be linked to the same person, then PR metadata,
  PR body, and PR comments by that login become stronger first-party evidence.
- If comments or reviews are by another login that cannot be linked to the
  target identity, treat them as context around the target's work, not as the
  target user's own communication.
- Use `committer-email` only as secondary evidence for who applied or committed
  the Git object. It is useful for bot/maintainer/merge-process detection, but
  should not drive primary capability attribution.

## Deriving GitHub Login From Email

There is no reliable public GitHub API that maps an arbitrary email address to
exactly one GitHub login. GitHub account email visibility is privacy-controlled,
and many users use no-reply commit emails.

However, commit search results can often provide a GitHub login indirectly. A
commit API response includes both:

- Raw Git metadata: `commit.author.name`, `commit.author.email`,
  `commit.committer.name`, and `commit.committer.email`.
- GitHub account mapping when GitHub can associate the raw commit identity with
  an account: top-level `author.login` and `committer.login`.

Recommended email-to-login inference flow:

1. Search commits by `author-email:<email>`.
2. For each result, inspect top-level `author.login`.
3. Count distinct `author.login` values across matching commits.
4. Accept a login as strongly linked only when the matched commits consistently
   map to the same top-level `author.login`.
5. If multiple logins appear, or `author` is `null`, keep the evidence at the
   email/commit level and avoid using login-only APIs as primary evidence.

Example fields to preserve:

```json
{
  "sha": "COMMIT_SHA",
  "commit": {
    "author": {
      "name": "Raw Git Author Name",
      "email": "person@example.com"
    }
  },
  "author": {
    "login": "github-login"
  }
}
```

Once a login is confidently linked, it can unlock GitHub APIs and search
qualifiers that do not support email directly:

```bash
# Pull requests authored by the linked GitHub login
GET /search/issues?q=type:pr+author:USERNAME

# Issues authored by the linked GitHub login
GET /search/issues?q=type:issue+author:USERNAME

# Issues or PRs commented on by the linked GitHub login
GET /search/issues?q=commenter:USERNAME

# Issues or PRs reviewed by the linked GitHub login
GET /search/issues?q=reviewed-by:USERNAME
```

Confidence guidance:

- Strong: `author-email:<email>` commits repeatedly map to the same top-level
  `author.login`.
- Medium: the email is a GitHub no-reply address containing a username, and the
  same username also appears as top-level `author.login` on matched commits.
- Weak: Git commit author name resembles a GitHub profile name, but no
  top-level `author.login` is present.
- Do not infer identity from `committer.login` unless the target evidence is
  specifically about who committed/applied the Git object.
- Do not assume the public `email` field on `GET /users/{username}` will be
  present. It only returns a publicly visible profile email when the user has
  chosen to expose one.

## Login-Based Evidence To Collect

After deriving a GitHub login with enough confidence, collect login-based
evidence that cannot be collected from email alone.

High-value searches:

```bash
# Issues created by the user
gh search issues "type:issue author:USERNAME" \
  --json repository,number,title,url,state,createdAt,updatedAt,closedAt,labels,author

# Pull requests created by the user
gh search prs "author:USERNAME" \
  --json repository,number,title,url,state,createdAt,updatedAt,closedAt,mergedAt,labels,author

# Issues or pull requests commented on by the user
gh search issues "commenter:USERNAME" \
  --json repository,number,title,url,state,createdAt,updatedAt,closedAt,author

# Pull requests reviewed by the user
gh search prs "reviewed-by:USERNAME" \
  --json repository,number,title,url,state,createdAt,updatedAt,closedAt,mergedAt,author

# Pull requests where review was requested from the user
gh search prs "review-requested:USERNAME" \
  --json repository,number,title,url,state,createdAt,updatedAt,closedAt,mergedAt,author

# Issues or pull requests assigned to the user
gh search issues "assignee:USERNAME" \
  --json repository,number,title,url,state,createdAt,updatedAt,closedAt,labels,author,assignees
```

REST equivalents use the search API:

```bash
GET /search/issues?q=type:issue+author:USERNAME
GET /search/issues?q=type:pr+author:USERNAME
GET /search/issues?q=commenter:USERNAME
GET /search/issues?q=type:pr+reviewed-by:USERNAME
GET /search/issues?q=type:pr+review-requested:USERNAME
GET /search/issues?q=assignee:USERNAME
```

For each issue created by the user, collect:

- Issue metadata: `id`, `number`, `html_url`, `state`, `state_reason`,
  `title`, `body`, `user.login`, `author_association`, labels, assignees,
  milestone, `created_at`, `updated_at`, and `closed_at`.
- Issue comments: commenter login, body, timestamps, author association, and
  reactions when available.
- Linked PRs or closing references when available, because these connect
  problem reports to implementation work.

Useful issue endpoints:

```bash
# Issue metadata
GET /repos/{owner}/{repo}/issues/{issue_number}

# Issue comments
GET /repos/{owner}/{repo}/issues/{issue_number}/comments

# Timeline events, useful for labels, assignments, cross-references, closes,
# reopens, and links between issues and PRs.
GET /repos/{owner}/{repo}/issues/{issue_number}/timeline
```

Other useful GitHub evidence:

- Authored PRs: primary evidence for implementation ownership, design
  explanation, and delivery quality.
- PR reviews by the user: direct evidence of code review skill, architectural
  judgment, risk detection, and communication quality.
- Review comments by the user: useful when line-level and tied to concrete code;
  preserve `path`, `diff_hunk`, `line`, and `commit_id`.
- Issue comments by the user: useful for debugging, triage, product thinking,
  clarification quality, and collaboration.
- Assigned issues/PRs: useful as responsibility/context evidence, but weaker
  than authored work because assignment does not prove execution.
- Closed issues: useful only with context. Closing an issue may mean fixing,
  triaging duplicate/invalid work, or administrative cleanup.
- Labels and milestones: useful for project area, severity, priority, and
  release context.
- Reactions: weak signal, but can help identify community impact or agreement.
- Repository metadata for each evidence item: stars, forks, archived/forked
  status, primary language, topics, license, and default branch. This helps
  weight evidence by project relevance and avoid over-scoring toy/fork repos.
- User profile metadata: `login`, `name`, public email if exposed, company,
  blog, location, bio, account creation date, followers, following, and public
  repository count. Use profile data as context, not capability proof.
- Public repositories owned by the user: useful for breadth, project ownership,
  languages, README quality, releases, tests, CI configuration, and maintenance
  activity.
- Releases and tags authored/published by the user when available: useful for
  delivery and maintenance evidence.

## CI And Quality Signal Evidence

CI evidence is useful context for delivery quality. It shows whether a commit or
pull request passed automated checks, what failed, how long checks took, and
whether failures were tied to tests, lint, security scans, builds, deployment,
or external services. Treat CI as supporting evidence: passing checks strengthen
an implementation story, but failing or missing checks need context from PR
discussion, follow-up commits, repository maturity, and project norms.

For each matched commit SHA, PR head SHA, PR merge commit SHA, or default-branch
commit that matters to the evaluation, collect these endpoint families:

```bash
# Checks API: modern check runs for a commit, branch, or tag ref
GET /repos/{owner}/{repo}/commits/{ref}/check-runs

# Check-run annotations, useful for concrete file/path/line quality findings
GET /repos/{owner}/{repo}/check-runs/{check_run_id}/annotations

# Legacy commit status contexts, still used by many external CI systems
GET /repos/{owner}/{repo}/commits/{ref}/statuses

# Combined legacy commit status
GET /repos/{owner}/{repo}/commits/{ref}/status

# GitHub Actions workflow runs for a repository, filterable by head SHA, actor,
# branch, event, status, and created date
GET /repos/{owner}/{repo}/actions/runs?head_sha={sha}

# Jobs inside a workflow run
GET /repos/{owner}/{repo}/actions/runs/{run_id}/jobs

# Workflow metadata when a run references a workflow ID or path
GET /repos/{owner}/{repo}/actions/workflows/{workflow_id}
```

Useful `curl` examples:

```bash
# Check runs for a matched commit SHA
curl -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/OWNER/REPO/commits/COMMIT_SHA/check-runs?per_page=100"

# Legacy statuses for the same SHA
curl -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/OWNER/REPO/commits/COMMIT_SHA/statuses?per_page=100"

# Combined legacy status
curl -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/OWNER/REPO/commits/COMMIT_SHA/status"

# GitHub Actions runs attached to the same SHA
curl -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/OWNER/REPO/actions/runs?head_sha=COMMIT_SHA&per_page=100"
```

For pull request evidence, collect CI for multiple refs when available:

- Each matched commit SHA in the PR.
- The PR `head.sha`, which is usually the most direct pre-merge CI signal.
- The PR `merge_commit_sha`, which is useful after merge.
- The default-branch commit that contains the change, when the associated PR or
  merge commit can be identified.

Preserve at least these fields:

- Check runs: `id`, `name`, `status`, `conclusion`, `started_at`,
  `completed_at`, `details_url`, `html_url`, `app`, `pull_requests`,
  `head_sha`, `check_suite`, and `output.title`, `output.summary`,
  `output.text` when present.
- Check annotations: `path`, `start_line`, `end_line`, `annotation_level`,
  `message`, `title`, `raw_details`, and blob coordinates when present.
- Legacy statuses: `context`, `state`, `description`, `target_url`,
  `created_at`, `updated_at`, and `creator.login`.
- Combined status: top-level `state`, `sha`, `total_count`, and nested
  `statuses`.
- Workflow runs: `id`, `name`, `display_title`, `event`, `status`,
  `conclusion`, `workflow_id`, `run_number`, `run_attempt`, `head_branch`,
  `head_sha`, `path`, `html_url`, `created_at`, `updated_at`,
  `run_started_at`, `actor.login`, `triggering_actor.login`, and PR links.
- Workflow jobs: `id`, `name`, `status`, `conclusion`, `started_at`,
  `completed_at`, `runner_name`, `runner_group_name`, `html_url`, and step
  names/statuses/conclusions when present.

Implementation guidance for `backend/evaluator/collectors/github.py`:

```python
collector = GitHubCollector(token=github_token)

signals = collector.fetch_ci_quality_signals(
    owner="OWNER",
    repo="REPO",
    ref="COMMIT_SHA",
    include_annotations=True,
    include_workflow_jobs=True,
)

# Store signals next to the matched commit or PR evidence.
```

The collector methods map directly to the endpoint families:

- `fetch_check_runs_for_ref(owner, repo, ref)` ->
  `GET /repos/{owner}/{repo}/commits/{ref}/check-runs`
- `fetch_check_run_annotations(owner, repo, check_run_id)` ->
  `GET /repos/{owner}/{repo}/check-runs/{check_run_id}/annotations`
- `fetch_commit_statuses(owner, repo, ref)` ->
  `GET /repos/{owner}/{repo}/commits/{ref}/statuses`
- `fetch_combined_status(owner, repo, ref)` ->
  `GET /repos/{owner}/{repo}/commits/{ref}/status`
- `fetch_workflow_runs(owner, repo, head_sha=ref)` ->
  `GET /repos/{owner}/{repo}/actions/runs?head_sha={ref}`
- `fetch_workflow_run_jobs(owner, repo, run_id)` ->
  `GET /repos/{owner}/{repo}/actions/runs/{run_id}/jobs`
- `fetch_workflow(owner, repo, workflow_id)` ->
  `GET /repos/{owner}/{repo}/actions/workflows/{workflow_id}`
- `fetch_ci_quality_signals(...)` combines the above into one repository-local
  evidence object and records endpoint errors as warnings.

Attribution guidance:

- CI status belongs to the commit, PR, or branch being evaluated. It does not
  by itself prove who wrote the passing or failing code.
- Prefer CI attached to commits matched by `author-email:<email>` or PRs
  strongly linked to the target login.
- Failed checks can be useful evidence when the user fixes them in follow-up
  commits or explains failures in PR comments.
- Missing CI is not automatically negative; older, small, toy, or documentation
  repositories may have no automated checks.
- Annotations are high-value because they tie automated quality findings to
  concrete files and lines.

Evidence quality ranking:

1. Strongest: matched `author-email` commits, associated PRs, authored PRs from
   a confidently linked login, and concrete reviews/comments by that login.
2. Medium: created issues, issue comments, assigned work, linked issues closed
   by PRs, and repository ownership.
3. Weak/contextual: stars, followers, reactions, profile text, memberships, and
   repository popularity.

Avoid these attribution mistakes:

- Do not score all activity in a repository just because the user has one commit
  there.
- Do not treat issue creation as implementation skill unless linked to code,
  debugging, design, or accepted project decisions.
- Do not treat comments from other users on the user's PR as the target user's
  communication evidence. They are context unless the target replied.
- Do not combine multiple GitHub logins into one profile unless the commit/email
  evidence supports that merge.
