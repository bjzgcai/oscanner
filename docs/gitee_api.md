# Gitee API Notes

## Repository-Scoped Commit Search By Email Or Username

Gitee does not expose a GitHub-style global commit search endpoint such as
`/search/commits?q=author-email:person@example.com`.

The public Gitee v5 OpenAPI provides these search endpoints:

- `/api/v5/search/issues`
- `/api/v5/search/repositories`
- `/api/v5/search/users`

It does not provide `/api/v5/search/commits`. Commit lookup is repository
scoped.

Use the repository commits endpoint with the `author` query parameter to match
commits by author email or Gitee username/login:

```bash
curl -G "https://gitee.com/api/v5/repos/OWNER/REPO/commits" \
  --data-urlencode "access_token=$GITEE_TOKEN" \
  --data-urlencode "author=person@example.com" \
  --data-urlencode "per_page=100"
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

Useful optional filters:

```bash
curl -G "https://gitee.com/api/v5/repos/OWNER/REPO/commits" \
  --data-urlencode "access_token=$GITEE_TOKEN" \
  --data-urlencode "author=person@example.com" \
  --data-urlencode "sha=main" \
  --data-urlencode "since=2026-01-01T00:00:00Z" \
  --data-urlencode "until=2026-06-01T00:00:00Z" \
  --data-urlencode "page=1" \
  --data-urlencode "per_page=100"
```

Notes:

- `author` is repository scoped. It is not global across Gitee.
- Gitee documents `author` as accepting either the commit author's email or a
  personal namespace address, such as username/login.
- There is no separate `author-email` or `committer-email` qualifier like
  GitHub commit search.
- The commits list endpoint filters by commit author. Gitee does not document a
  `committer` query parameter for this endpoint.
- If committer identity matters, fetch commit details or unfiltered commit pages
  and inspect committer fields locally, such as `commit.committer.email`,
  `commit.committer.name`, and any top-level linked `committer` user object.
- Private repositories require an access token with repository access.
- The matched email is the raw Git commit metadata email. It may not equal the
  user's Gitee account email.

## Discovery From A Gitee Profile URL

A profile URL such as `https://gitee.com/wu-yanbiao` gives you the Gitee
username/login `wu-yanbiao`. Gitee does not provide a public global endpoint for
"all commits by this profile across all Gitee". The practical workflow is:

1. Get the profile.
2. List repositories that belong to the user.
3. For each repository, collect commits with `author=<username>`.
4. Separately inspect unfiltered commit pages or commit details if committer
   matches are required.

Example:

```bash
username="wu-yanbiao"

# 1. Get profile
curl -G "https://gitee.com/api/v5/users/$username" \
  --data-urlencode "access_token=$GITEE_TOKEN"

# 2. List that user's public repositories
curl -G "https://gitee.com/api/v5/users/$username/repos" \
  --data-urlencode "access_token=$GITEE_TOKEN" \
  --data-urlencode "page=1" \
  --data-urlencode "per_page=100"

# 3. For each repository, collect author matches
curl -G "https://gitee.com/api/v5/repos/OWNER/REPO/commits" \
  --data-urlencode "access_token=$GITEE_TOKEN" \
  --data-urlencode "author=$username" \
  --data-urlencode "page=1" \
  --data-urlencode "per_page=100"
```

This finds commits where the Git commit author matches the Gitee username/login
according to Gitee's repository-scoped filter. It does not guarantee every
commit the user made across Gitee because:

- The user may have contributed to repositories owned by other users,
  organizations, or enterprises.
- The user may have committed with a different Git author name or email.
- Private repositories require token access.
- Repository listing and commit listing are paginated.

## Committer Matching

Gitee commits contain both author and committer metadata when available. Author
and committer are different Git identities:

- `commit.author` is the person recorded as writing the change.
- `commit.committer` is the person or process recorded as applying the commit.

The Gitee commits endpoint documents `author`, but not `committer`, as a query
filter. To collect committer matches, fetch commits and filter locally:

```bash
username="wu-yanbiao"

curl -sG "https://gitee.com/api/v5/repos/OWNER/REPO/commits" \
  --data-urlencode "access_token=$GITEE_TOKEN" \
  --data-urlencode "page=1" \
  --data-urlencode "per_page=100" |
  jq --arg username "$username" '
    .[]
    | select(
        (.commit.committer.name // "" | ascii_downcase) == ($username | ascii_downcase)
        or (.committer.login // "" | ascii_downcase) == ($username | ascii_downcase)
        or (.committer.name // "" | ascii_downcase) == ($username | ascii_downcase)
      )
    | {
        sha,
        html_url,
        author: .commit.author,
        committer: .commit.committer,
        linked_committer: .committer,
        message: .commit.message
      }
  '
```

For email-based committer matching, compare against
`commit.committer.email` locally. If the repository is cloned, Git can perform
repository-local author and committer matching directly:

```bash
git log --author="person@example.com" --all
git log --committer="person@example.com" --all
git log --author="wu-yanbiao" --all
git log --committer="wu-yanbiao" --all
```

Treat committer matches as separate evidence from author matches. A committer
can be a maintainer, merge account, automation account, or the hosting platform
rather than the person who wrote the original code.

## Engineering Capability Evidence From A Profile

For Gitee evaluation, prefer starting from a Gitee profile URL and username
rather than an email address:

```text
https://gitee.com/wu-yanbiao -> wu-yanbiao
```

Unlike GitHub, Gitee does not provide a global commit search surface. The best
available strategy is:

1. Build a repository inventory from the profile user's public repositories.
2. Fetch and store repository-scoped evidence locally.
3. Filter that evidence by Gitee username, Git author names, Git author emails,
   committer names, and committer emails.
4. Keep raw identity fields so downstream scoring can distinguish strong author
   evidence from weaker committer or context evidence.

### Repository Inventory

For the profile-based Gitee evaluation path, only use repositories returned by
the profile user's repository endpoint:

```bash
curl -G "https://gitee.com/api/v5/users/USERNAME/repos" \
  --data-urlencode "access_token=$GITEE_TOKEN" \
  --data-urlencode "type=all" \
  --data-urlencode "page=1" \
  --data-urlencode "per_page=100"
```

Do not expand this profile-based inventory with `/user/repos`, organization
repos, enterprise repos, or repository search unless the product explicitly adds
a separate "known organization/enterprise scope" mode. Keeping the inventory to
`/users/{username}/repos` makes attribution simpler and prevents accidentally
scoring unrelated repository activity that is merely visible to the token.

Store repository metadata for weighting and context: `full_name`, `html_url`,
description, language, default branch, fork/private flags, stars, forks,
watchers, open issue count, owner, namespace, and timestamps when present.

### Commits And Code Evidence

For each candidate repository, collect author-filtered commits first:

```bash
curl -G "https://gitee.com/api/v5/repos/OWNER/REPO/commits" \
  --data-urlencode "access_token=$GITEE_TOKEN" \
  --data-urlencode "author=USERNAME" \
  --data-urlencode "page=1" \
  --data-urlencode "per_page=100"
```

Then fetch unfiltered commit pages when feasible and locally match:

- `commit.author.name`
- `commit.author.email`
- top-level linked `author.login`, `author.name`, or `author.username`
- `commit.committer.name`
- `commit.committer.email`
- top-level linked `committer.login`, `committer.name`, or
  `committer.username`

For every matched SHA, fetch commit details:

```bash
curl -G "https://gitee.com/api/v5/repos/OWNER/REPO/commits/COMMIT_SHA" \
  --data-urlencode "access_token=$GITEE_TOKEN"
```

Preserve changed file paths, additions, deletions, patch/diff content or URLs,
commit message, author date, committer date, parent SHAs, and raw identity
objects. These fields are the strongest evidence for implementation skill,
technical scope, test changes, review iteration, and maintenance work.

If local cloning is allowed, also run Git-level matching because it can be more
complete for a single repository:

```bash
git log --author="USERNAME" --all --numstat --format=fuller
git log --committer="USERNAME" --all --numstat --format=fuller
```

### Pull Request Evidence

Pull requests show ownership, design explanation, collaboration, delivery
quality, and review outcomes. Collect PRs authored by the user:

```bash
curl -G "https://gitee.com/api/v5/repos/OWNER/REPO/pulls" \
  --data-urlencode "access_token=$GITEE_TOKEN" \
  --data-urlencode "author=USERNAME" \
  --data-urlencode "state=all" \
  --data-urlencode "page=1" \
  --data-urlencode "per_page=100"
```

Also collect PRs where the user was assigned for review or testing:

```bash
curl -G "https://gitee.com/api/v5/repos/OWNER/REPO/pulls" \
  --data-urlencode "access_token=$GITEE_TOKEN" \
  --data-urlencode "assignee=USERNAME" \
  --data-urlencode "state=all" \
  --data-urlencode "page=1" \
  --data-urlencode "per_page=100"

curl -G "https://gitee.com/api/v5/repos/OWNER/REPO/pulls" \
  --data-urlencode "access_token=$GITEE_TOKEN" \
  --data-urlencode "tester=USERNAME" \
  --data-urlencode "state=all" \
  --data-urlencode "page=1" \
  --data-urlencode "per_page=100"
```

For each relevant PR, collect:

```bash
# PR metadata
GET /api/v5/repos/{owner}/{repo}/pulls/{number}

# Commits in the PR, up to Gitee's documented endpoint limit
GET /api/v5/repos/{owner}/{repo}/pulls/{number}/commits

# Files changed by the PR, up to Gitee's documented endpoint limit
GET /api/v5/repos/{owner}/{repo}/pulls/{number}/files

# PR comments and line-level code comments when available
GET /api/v5/repos/{owner}/{repo}/pulls/{number}/comments

# Review/test/assignment/merge operation history
GET /api/v5/repos/{owner}/{repo}/pulls/{number}/operate_logs

# Issues linked to the PR
GET /api/v5/repos/{owner}/{repo}/pulls/{number}/issues

# PR labels
GET /api/v5/repos/{owner}/{repo}/pulls/{number}/labels

# Merge status
GET /api/v5/repos/{owner}/{repo}/pulls/{number}/merge
```

Preserve PR title, body, state, draft/security fields when present, labels,
assignees, testers, source and target branches, timestamps, merge status,
merge method, commits, changed files, comments, and operation logs.

### Issues, Triage, And Product/Debugging Evidence

Issues are useful for debugging, triage, problem framing, requirement
discussion, maintenance, and collaboration evidence. Collect issues created by
the user:

```bash
curl -G "https://gitee.com/api/v5/repos/OWNER/REPO/issues" \
  --data-urlencode "access_token=$GITEE_TOKEN" \
  --data-urlencode "creator=USERNAME" \
  --data-urlencode "state=all" \
  --data-urlencode "page=1" \
  --data-urlencode "per_page=100"
```

Also collect issues assigned to the user:

```bash
curl -G "https://gitee.com/api/v5/repos/OWNER/REPO/issues" \
  --data-urlencode "access_token=$GITEE_TOKEN" \
  --data-urlencode "assignee=USERNAME" \
  --data-urlencode "state=all" \
  --data-urlencode "page=1" \
  --data-urlencode "per_page=100"
```

The issue search endpoint can help find public issues by keyword, author, or
assignee, but it is not equivalent to GitHub's full issue search qualifiers:

```bash
curl -G "https://gitee.com/api/v5/search/issues" \
  --data-urlencode "access_token=$GITEE_TOKEN" \
  --data-urlencode "q=keyword" \
  --data-urlencode "author=USERNAME" \
  --data-urlencode "page=1" \
  --data-urlencode "per_page=100"
```

For each relevant issue, collect:

```bash
# Issue metadata
GET /api/v5/repos/{owner}/{repo}/issues/{number}

# Issue comments
GET /api/v5/repos/{owner}/{repo}/issues/{number}/comments

# Pull requests linked to the issue
GET /api/v5/repos/{owner}/issues/{number}/pull_requests?repo={repo}

# Operation logs for labels, assignment, state changes, and workflow events
GET /api/v5/repos/{owner}/issues/{number}/operate_logs?repo={repo}

# Issue labels
GET /api/v5/repos/{owner}/{repo}/issues/{number}/labels
```

Preserve issue title, body, state, labels, assignees, collaborators, milestone,
program fields, security flags, timestamps, comments, operation logs, and
linked pull requests.

### Comments And Review-Like Evidence

Gitee does not expose a GitHub-style global `commenter:USERNAME` search. Collect
comments at the repository, PR, issue, and commit level, then filter locally by
comment author login/name.

Useful endpoints:

```bash
# Repository-level issue comments
GET /api/v5/repos/{owner}/{repo}/issues/comments

# Comments for one issue
GET /api/v5/repos/{owner}/{repo}/issues/{number}/comments

# Comments for one pull request
GET /api/v5/repos/{owner}/{repo}/pulls/{number}/comments

# Repository-level commit comments
GET /api/v5/repos/{owner}/{repo}/comments

# Comments for one commit/ref
GET /api/v5/repos/{owner}/{repo}/commits/{ref}/comments
```

Comments by the target user are direct evidence of communication, debugging,
review quality, and design reasoning. Comments by other users are context
around the user's work, not the user's own communication evidence.

### Repository Structure, Quality, And CI Signals

Repository content helps evaluate engineering breadth and quality beyond raw
activity counts. For repositories with matched evidence, collect:

```bash
# Root or path contents
GET /api/v5/repos/{owner}/{repo}/contents/{path}

# Recursive tree when available
GET /api/v5/repos/{owner}/{repo}/git/trees/{sha}?recursive=1

# Branches and tags
GET /api/v5/repos/{owner}/{repo}/branches
GET /api/v5/repos/{owner}/{repo}/tags

# Contributors and collaborators when visible to the token
GET /api/v5/repos/{owner}/{repo}/contributors
GET /api/v5/repos/{owner}/{repo}/collaborators
GET /api/v5/repos/{owner}/{repo}/collaborators/{username}/permission
```

Look for README quality, tests, CI files, Docker/Kubernetes/IaC files,
dependency manifests, docs, examples, release tags, and ownership/maintainer
signals.

Gitee also exposes check-run evidence for CI or automated quality checks:

```bash
# Check runs for a commit
GET /api/v5/repos/{owner}/{repo}/commits/{ref}/check-runs

# Check-run details and annotations
GET /api/v5/repos/{owner}/{repo}/check-runs/{check_run_id}
GET /api/v5/repos/{owner}/{repo}/check-runs/{check_run_id}/annotations
```

Preserve check status, conclusion, timestamps, output summaries, annotations,
affected paths, and links to external CI systems.

### Evidence Quality Ranking

Use evidence strength to avoid over-attribution:

1. Strong: matched `commit.author` evidence, PRs authored by the username, PR
   commits/files, accepted or merged PRs, and comments by the username on code
   or design discussions.
2. Strong for review capability: PR comments by the username, review/test
   operation logs, assignment/tester activity followed by concrete comments or
   status changes.
3. Medium: issues created by the username, issue comments by the username,
   assigned issues, linked issues closed by PRs, commit comments, and
   maintainer operation logs.
4. Context: repository ownership, collaborator status, stars, forks, watchers,
   profile metadata, followers, and repository popularity.

Avoid these attribution mistakes:

- Do not score all activity in a repository just because the user owns it or
  has one commit there.
- Do not treat `commit.committer` as code authorship unless the evaluation is
  explicitly about who applied the commit.
- Do not treat comments from other users on the user's PR as the user's own
  communication evidence.
- Do not infer all user activity from profile-owned repositories; users can
  contribute to organization, enterprise, and third-party repositories.
- Do not merge multiple usernames, emails, or Git author names unless the raw
  commit and profile evidence supports that merge.

## Cross-Repository Discovery From Email

Because Gitee has no global commit search, email-only cross-repository
discovery requires a repository inventory first:

1. Build a list of candidate repositories visible to the token.
2. Call `/api/v5/repos/{owner}/{repo}/commits?author=<email>` for each repo.
3. Fetch commit details for matched SHAs when file diffs or richer metadata are
   needed.
4. Deduplicate by `repo_full_name` and `sha`.

Example using a local repository list:

```bash
email="person@example.com"

while read full_name; do
  owner="${full_name%/*}"
  repo="${full_name#*/}"

  curl -sG "https://gitee.com/api/v5/repos/$owner/$repo/commits" \
    --data-urlencode "access_token=$GITEE_TOKEN" \
    --data-urlencode "author=$email" \
    --data-urlencode "per_page=100" |
    jq --arg repo "$full_name" '.[] | {
      repo: $repo,
      sha,
      html_url,
      author: .commit.author,
      committer: .commit.committer,
      message: .commit.message
    }'
done < gitee_repos.txt
```

For the current profile-based product flow, use only the known Gitee user's
repositories as the repository inventory:

```bash
# Repositories for a known Gitee user
curl -G "https://gitee.com/api/v5/users/USERNAME/repos" \
  --data-urlencode "access_token=$GITEE_TOKEN" \
  --data-urlencode "type=all" \
  --data-urlencode "per_page=100"
```

Do not include `/api/v5/user/repos`, `/api/v5/orgs/{org}/repos`,
`/api/v5/enterprises/{enterprise}/repos`, or
`/api/v5/search/repositories` in this default flow. Those endpoints can expose
repositories outside the user's profile-owned repository set and should only be
used in a separate, explicitly scoped mode.

## Fetching Matched Commit Details

After finding a matched commit SHA, fetch the repository-scoped commit detail:

```bash
curl -G "https://gitee.com/api/v5/repos/OWNER/REPO/commits/COMMIT_SHA" \
  --data-urlencode "access_token=$GITEE_TOKEN"
```

Preserve at least these fields:

- Repository: `owner`, `repo`, `full_name`, repository URL.
- Commit identity: `commit.author.name`, `commit.author.email`,
  `commit.committer.name`, `commit.committer.email`.
- Commit metadata: `sha`, `html_url`, `commit.message`, author date, committer
  date.
- File evidence from commit details when available: file paths, additions,
  deletions, patch/diff URLs or patch text.

## Pull Request Evidence From Email

Gitee pull request search is not a reliable email-only identity path. Use
matched commits as the discovery path:

1. Find commits in candidate repositories with `author=<email>`.
2. Preserve each matched `repo` and `sha`.
3. Use repository pull request APIs, local extracted PR data, or commit-linked
   metadata when available to connect the commit to a pull request.

Attribution guidance:

- Prefer `commit.author.email` for code authorship evidence. This is the person
  recorded as writing the commit.
- Treat `commit.committer.email` as separate and weaker evidence. It may be a
  maintainer, Gitee system account, bot, or merge process.
- Do not use committer email as the main way to attribute a pull request to a
  user.
- Keep raw commit identity fields so downstream scoring can distinguish strong
  author-email matches from weaker committer or username-only matches.

## Oscanner Behavior

Oscanner currently handles Gitee email matching through locally cached
repositories, not global Gitee discovery.

The `/api/github/analyze` endpoint combines:

- Global GitHub commit search with `author-email` and `committer-email`.
- Cached Gitee repositories already extracted under the Oscanner data
  directory.

For Gitee, the endpoint iterates cached repositories, loads local commit files,
and matches the supplied email against visible author/committer metadata. The
response limitation says:

```text
Gitee remains limited to repositories already present in the local Oscanner data cache.
```

To evaluate Gitee commits by email across more repositories, first extract or
sync the target Gitee repositories, then run the email-based analysis against
the local cache.
