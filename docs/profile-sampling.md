# Profile sampling v1

GitHub and Gitee evaluations select bounded evidence across repositories,
years and file categories. Commit titles do not determine categories.
Files retain patches for evaluation; `sampled_evidence` is a compact display
projection with paths and provenance. Old request limits remain supported.

The sampler reserves 5% recent activity (at least one when the budget is five
or more), covers repositories, and targets source 45%, tests 20%, engineering
configuration/ADR 20%, ordinary documentation 10%. These are targets, not
guarantees: repository coverage and actual supply take precedence. Missing
categories redistribute to engineering first. A repository normally gets at
most max(30%, 1 / repository count) of the budget, rounded up. Exhausted supply
relaxes this cap explicitly in `selection_reason`.

Within each category, repository and calendar-year counts balance selection.
Diff size is capped as a tie-breaker, never interpreted as engineering quality.
Identical SHA objects across mirrors count once. Complete identical patches
within one repository and attributed identity also count once. Distinct
reverts and incremental commits remain evidence; title matching cannot safely
establish that they cancel or represent the same work.

GitHub detail hydration examines at most min(500, max(50, 5 * request limit))
candidates, round-robin across repositories and evenly spread through history.
Cached file details are reused. Detail failures and truncated pages lower
confidence, while inventory completeness stays separate. Gitee uses the
existing synchronized local commit files. Neither path promises complete
lifetime file coverage; unknown file types stay unknown rather than being
invented architecture evidence.

`summary` adds sampling_version, sampled_commit_count, engineering_commit_count,
documentation_only_commit_count, repository_coverage (sampled repository count),
available_repository_count, detail_complete_count and evidence_confidence.
The evaluation also includes sampling_summary, sampled_evidence and
assessment_status. Low confidence means insufficient_evidence: numeric scores
remain backward compatible observations, not a definitive personal L1 grade.
Fewer than three engineering samples, missing details, broad ownership-only
attribution or collection warnings cause low confidence. High confidence needs
ten engineering samples, full selected details, verified attribution and two
repositories. Repository context is never proof of individual authorship.

Reevaluate to obtain the new fields. Existing saved evaluations remain unchanged.
