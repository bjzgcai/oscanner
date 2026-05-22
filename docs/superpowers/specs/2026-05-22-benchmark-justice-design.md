# Benchmark Justice Design

## Purpose

Oscanner's benchmark should demonstrate evaluation justice through separate,
auditable checks rather than one opaque overall score. The benchmark should make
failures visible: an evaluator can be stable but biased by fame, or good at
career-stage ordering but unfair across languages.

The benchmark will be treated as a suite of small, curated datasets. The current
30-entry language/career matrix remains the core public set, and additional
targeted sets test specific justice claims.

## Justice Claims

The suite should report these checks independently:

1. Ordering justice: L1-L5 ordering is reasonable within a language/developer
   track.
2. Cross-language justice: similar evidence receives similar treatment across
   Python, JavaScript/TypeScript, Go, Rust, Java, and C/C++.
3. Evidence justice: observable repository evidence drives scores more than
   fame, stars, organization reputation, or author identity.
4. Applicability justice: old, traditional, non-cloud, or non-AI repositories
   are not unfairly punished when a dimension is not applicable.
5. Stability justice: rerunning the same pinned case does not cause large score
   swings.
6. Calibration accuracy: human-reviewed expected score bands and dimension
   expectations are respected.

## Benchmark Suite Shape

### Core Set

Size: 30 entries.

Source: `benchmark/repos.yaml`.

Shape: six language tracks times five L1-L5 levels.

Purpose: ordering justice, broad cross-language sanity checks, and public
demonstration.

Selection rules:

- Prefer pinned tags, SHAs, or commit ranges.
- Keep public evidence for every level assignment.
- Record target author aliases.
- Mark review status as `unreviewed`, `self_reviewed`, `expert_reviewed`, or
  `locked`.

### Counterfactual Set

Size: 10-20 entries.

Purpose: evidence justice.

Cases:

- Same repository evidence with fame/stars/identity removed from the evaluator
  context.
- Same commit evidence presented with alternate neutral metadata.
- Similar repo evidence from famous and non-famous maintainers.

Expected behavior:

- Scores should remain close when code, commits, tests, docs, and architecture
  evidence are unchanged.
- Any meaningful score movement must be explainable by evidence differences, not
  by public reputation.

### Era And Applicability Set

Size: 10-15 entries.

Purpose: applicability justice.

Cases:

- Historical libraries created before modern CI, containers, or AI tooling were
  common.
- Modern traditional libraries where cloud or AI engineering is not central.
- Cloud-native applications where deployment evidence should matter.
- AI-native applications where prompt/tool/evaluation evidence should matter.

Expected behavior:

- Missing non-applicable dimensions should not dominate the final judgment.
- Dimension-level gaps should still be reported honestly.
- Overall scoring should distinguish "not applicable" from "applicable but
  absent".

### Calibration Set

Size: 10-20 entries.

Purpose: calibration accuracy.

Cases:

- Human-reviewed examples with expected overall score bands.
- Human-reviewed dimension expectations.
- Known weak and strong examples for each rubric dimension.

Expected behavior:

- Scores should land inside expected bands for most locked cases.
- Out-of-band results should produce reviewable failure records, not silent
  aggregate degradation.

### Regression Smoke Set

Size: 6-10 entries.

Purpose: fast evaluator drift detection.

Cases:

- One stable pinned example per major language or dimension.
- Small enough to run frequently.

Expected behavior:

- No major score movement without a deliberate rubric, prompt, model, or data
  extraction change.

## Reporting Model

The public report should lead with a justice profile, not a single justice
score.

Example:

```text
Oscanner Benchmark Justice Report

Overall Status: Needs Attention

Ordering Justice:        PASS   87/100
Cross-Language Justice:  WARN   72/100
Evidence Justice:        FAIL   54/100
Applicability Justice:   WARN   68/100
Stability Justice:       PASS   91/100
Calibration Accuracy:    WARN   74/100
```

Primary output:

- Per-check `PASS`, `WARN`, or `FAIL`.
- Per-check numeric score for trend tracking.
- Failed case list with expected value, actual value, and evidence summary.
- Label confidence for each failed case.

Secondary output:

- Optional aggregate badge such as `2 pass, 3 warn, 1 fail`.
- Optional weighted score for internal trend monitoring only.

The aggregate score must be labeled non-authoritative. A failing justice check
must stay visible even when the aggregate looks acceptable.

## Pass, Warn, Fail Semantics

Each justice check should define explicit thresholds.

Initial defaults:

- `PASS`: check score is at least 85 and no critical failure exists.
- `WARN`: check score is 70-84, or there are label-confidence concerns.
- `FAIL`: check score is below 70, or a critical fairness invariant is broken.

Critical failures:

- Same evidence receives materially different scores under different author
  identity metadata.
- L1-L5 ordering is inverted for locked cases without evidence-based reason.
- Historical or non-applicable dimensions dominate the overall score.
- Rerun variance exceeds the stability threshold on locked cases.

## Result Artifacts

Each benchmark run should store a compact JSON result with:

- Oscanner commit SHA.
- Plugin ID and plugin version or commit SHA.
- Model provider and model name.
- Benchmark manifest version.
- Dataset subset names.
- Repository URL and pinned ref or commit range.
- Target author and aliases.
- Raw overall score.
- Dimension scores.
- Applicability flags per dimension.
- Evaluator reasoning summary.
- Pass/warn/fail result per justice check.
- Failed case explanations.

Large cloned repositories, local caches, secrets, and full generated reports
should remain outside the committed benchmark artifacts unless intentionally
curated.

## Size Strategy

The benchmark should grow by label quality, not by volume.

Recommended initial size:

- 30 core entries.
- 10-20 counterfactual entries.
- 10-15 era/applicability entries.
- 10-20 calibration entries.
- 6-10 smoke entries.

Target total: roughly 70-95 curated cases.

The suite should not expand toward hundreds of repositories until the schema,
labels, review process, and failure reports are stable.

## Implementation Boundaries

This design does not require changing evaluator scoring immediately. The first
implementation should add benchmark metadata and reporting structure that make
justice failures observable. Rubric or scoring changes should follow only after
the benchmark reveals consistent failure patterns.

The benchmark route, validation runner, and frontend validation dashboard can
consume the suite incrementally:

1. Load suite subsets from benchmark metadata.
2. Run targeted checks independently.
3. Emit justice-profile results.
4. Render pass/warn/fail gates and failed cases.

## Open Policy

Human review remains part of the benchmark contract. Cases can be `unreviewed`,
`self_reviewed`, `expert_reviewed`, or `locked`. Public claims should rely only
on `expert_reviewed` or `locked` cases. Draft cases can be useful for local
development but must not be used as proof of evaluator justice.

