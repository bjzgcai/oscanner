# Benchmark Manifest Schema

`repos.yaml` is the source of truth for the benchmark draft. It is intentionally
plain YAML so it can be consumed by Oscanner, scripts, or a future external
benchmark repository.

## Top-Level Fields

- `version`: integer schema version.
- `name`: stable benchmark identifier.
- `status`: lifecycle state, currently `draft`.
- `description`: short benchmark purpose.
- `languages`: the six benchmark language tracks.
- `levels`: L1-L5 definitions used across every language track.
- `entries`: exactly 30 benchmark slots, one for each language and level.

## Entry Fields

- `id`: stable kebab-case identifier, for example `python-l1`.
- `language`: one of `python`, `javascript-typescript`, `go`, `rust`, `java`,
  or `cpp`.
- `level`: one of `L1`, `L2`, `L3`, `L4`, or `L5`.
- `status`: `needs_selection`, `candidate`, `selected`, `retired`, or
  `rejected`.
- `developer_profile_id`: stable identifier for the selected developer in that
  language track.
- `developer`: display name for the selected developer.
- `author_aliases`: commit author names, emails, or usernames used by Oscanner
  to attribute work to the developer.
- `repo`: repository metadata.
- `selection_evidence`: why this entry belongs at this level.
- `evaluator`: fields used by Oscanner evaluator workflows.
- `repos_runner`: fields used by Oscanner repository test workflows.
- `fairness`: controls that keep the entry reproducible and defensible.

## Repository Fields

- `platform`: `github` or `gitee`.
- `owner`: repository owner.
- `name`: repository name.
- `url`: full public repository URL.
- `ref_type`: `branch`, `tag`, `sha`, or `commit_range`.
- `ref`: branch, tag, or SHA value. Use `null` for a commit range.
- `start_sha`: older commit when `ref_type` is `commit_range`.
- `end_sha`: newer commit when `ref_type` is `commit_range`.
- `license`: detected project license when known.

## Evaluator Fields

- `target_author`: primary author string to evaluate.
- `plugin_id`: recommended plugin for the benchmark run.
- `expected_score_band`: optional score band after expert calibration.
- `expected_strengths`: dimensions expected to be strong.
- `expected_risks`: known reasons the evaluator might under-score or over-score
  this entry.

## Repos Runner Fields

- `feature_requirements_file`: path to a language-level feature template.
- `feature_requirements_override`: entry-specific feature requirements when the
  language template is too broad.
- `test_command_policy`: `auto_detect`, `documented_command`, or
  `custom_command`.
- `known_test_constraints`: dependency, platform, or runtime limits that affect
  automated test execution.

## Fairness Fields

- `selection_rule`: the objective rule used to choose this repo or ref.
- `public_evidence_urls`: public pages supporting the level assignment.
- `exclusion_notes`: what was intentionally excluded and why.
- `review_status`: `unreviewed`, `self_reviewed`, `expert_reviewed`, or
  `locked`.

