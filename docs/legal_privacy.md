# Legal And Privacy Use Constraints

Oscanner collects repository and contribution evidence from GitHub, Gitee, and
local Git metadata. These sources can include personal data such as names,
emails, usernames, profile fields, commit history, pull/merge request activity,
reviews, comments, and timestamps. Public availability does not automatically
make every downstream use appropriate or permitted.

This document is engineering guidance, not legal advice. Confirm requirements
with legal/compliance counsel before using Oscanner for hiring, ranking,
monitoring, enterprise analytics, or any other high-impact people-evaluation
workflow.

## Allowed Collection Principles

Use provider data only through official GitHub/Gitee API surfaces or local Git
repositories that the operator is authorized to access. Do not scrape private
surfaces, bypass access controls, evade rate limits, or combine tokens to exceed
provider limits.

Collect only data that is public or that the token holder is authorized to use
for the specific evaluation purpose. Private repositories, enterprise data, and
organization-visible data should be treated as permission-scoped evidence, not as
general-purpose profile data.

For person-level evaluation, prefer one of these bases:

- The evaluated person explicitly submits the profile, repository, email, or
  alias set.
- The repository owner or organization has a documented legitimate internal use
  and permission to analyze the relevant repositories.
- The workflow is limited to public, repository-scoped evidence with clear user
  notice, minimization, and deletion controls.

Do not use Oscanner workflows to bulk harvest developers, spam users, sell or
resell personal profiles, bypass platform restrictions, or provide candidate
lead lists to recruiters, headhunters, job boards, or similar services without a
separate legal review and appropriate consent/notice.

## Identity And Attribution

Commit emails, Git author names, Git committer names, and platform usernames are
not always the same person. Squash merges, rebases, cherry-picks, bot accounts,
maintainer commits, web UI commits, and no-reply addresses can weaken identity
confidence.

Keep raw evidence fields and attribution confidence levels so downstream scoring
can distinguish strong authorship evidence from weaker committer, context, or
inferred-identity evidence.

Use email-to-login or alias inference only when necessary, and prefer an opt-in
identity resolution flow where users can confirm, remove, or correct proposed
emails, usernames, aliases, and repositories before evaluation.

## Data Minimization And Retention

Collect the minimum evidence needed for repeatable evaluation. Avoid storing raw
patches, comments, emails, profile details, or private repository metadata when
summary evidence is sufficient.

Store data locally by default. Protect tokens and secrets, mask them in logs and
responses, and never include raw secrets in persisted reports.

Provide a practical way to delete local cached data and generated reports. For
shared or hosted deployments, define retention limits, access controls, audit
logging, and deletion/export procedures before collecting user data.

## Provider-Specific Notes

### GitHub

Use official GitHub APIs within documented rate limits and secondary abuse
limits. Authenticated access does not grant permission to reuse all visible data
for every purpose.

GitHub commit search by `author-email` or `committer-email` should be treated as
identity evidence, not as a guaranteed account lookup. GitHub account email
visibility is privacy-controlled, and commit emails may be no-reply addresses or
unrelated to the account's private email.

Be especially cautious with workflows that infer developers from emails or build
people profiles from public GitHub data for recruiting, lead generation, or
resale.

### Gitee

Use official Gitee OpenAPI endpoints within documented limits and token scopes.
Prefer profile-submitted or repository-owner-authorized collection.

For Gitee profile-based evaluation, keep repository inventory limited to the
submitted profile's repositories unless the product explicitly enters a separate
organization or enterprise scope with appropriate permission.

Treat Gitee commit emails, usernames, profile fields, and contribution history as
personal information where applicable. For China-facing or enterprise use,
confirm compliance duties before using the data for scoring, ranking, or hiring.

## Implementation Checklist

- Validate repository URLs, author names, emails, and file paths before API calls
  or writes.
- Respect provider authentication, authorization, pagination, rate limits, and
  abuse-prevention responses.
- Do not expand from a submitted identity into all token-visible private,
  organization, or enterprise repositories unless that scope is explicit and
  authorized.
- Separate author, committer, reviewer, commenter, maintainer, and bot evidence
  in stored data and model prompts.
- Mask secrets and avoid logging raw tokens, private URLs, or unnecessary PII.
- Document attribution uncertainty in user-facing reports.
- Support deletion of local caches and generated evaluation artifacts.
