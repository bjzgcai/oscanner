# Fairness Methodology

This benchmark is meant to support a defensible claim that Oscanner evaluates
engineering work fairly across languages and career stages. The benchmark itself
does not prove fairness by existing; fairness comes from transparent selection,
reproducible runs, and honest limits.

## Selection Rules

Use one recognized public developer per language track, but avoid treating fame
as the same thing as evaluation ground truth. Prefer non-fork repositories under
the developer's personal account when the evidence is comparable. Use
organization-owned repositories when they provide stronger level evidence and
the target developer's authorship or maintainership is attributable enough for
the benchmark.

For each selected developer, record:

- Why this person is a reasonable representative for the language track.
- Which five repositories, tags, SHAs, or commit ranges represent L1-L5.
- Public evidence for each level assignment.
- Author aliases used for commit attribution.
- Known reasons the selected repo may be hard to evaluate automatically.

Chronology is a main factor for L1-L5 ordering: L1 should represent earlier,
less mature work, and L5 should represent later, more mature or architecturally
advanced work. Maturity and design complexity decide between nearby historical
candidates.

Prefer pinned tags, SHAs, or commit ranges over floating branches. Floating
branches make benchmark results drift over time.

## Level Assignment

Each L1-L5 label should be backed by evidence in the manifest:

- L1: small-scope early work, simple bug fixes, learning-stage contributions.
- L2: independent feature delivery and routine quality practices.
- L3: module ownership, meaningful design decisions, reliable test coverage.
- L4: architecture, maintainability, compatibility, review, or release judgment.
- L5: ecosystem-level impact, widely adopted systems, or field-shaping work.

If a famous developer's public history does not have a clean L1-L5 trail, record
the gap rather than forcing a weak example into the dataset.

## Evaluator Fairness

Evaluator runs should record:

- Oscanner commit SHA.
- Plugin ID and plugin version or commit SHA.
- Model name and provider mode.
- Repository URL and pinned ref or commit range.
- Target author and aliases.
- Raw score, dimension scores, and evaluator reasoning summary.

Compare scores within each language track first, then across languages. Cross
language comparisons are more fragile because repository conventions, test
culture, and historical tooling differ.

## Repos Runner Fairness

Runner results should record:

- Detected language and test commands.
- Setup, test, and pipeline timeouts.
- Executor mode, such as host or Docker.
- Feature requirements supplied to the runner.
- Passed, failed, total, score, and failure reason.

Do not punish a historical repository only because modern package tooling did
not exist yet. When a repo needs an older runtime, record that as a constraint
and decide whether to support it or exclude that entry.

## Exclusion Rules

Exclude or retire entries when:

- The selected ref cannot be fetched publicly.
- The target author's commits cannot be attributed with confidence.
- The project requires private credentials for normal setup.
- The project cannot be run safely in the repos_runner sandbox.
- The selected repo mainly reflects generated code or vendored dependencies.

## Review Status

Use `review_status` in `repos.yaml`:

- `unreviewed`: initial slot or candidate.
- `self_reviewed`: checked by the benchmark maintainer.
- `expert_reviewed`: checked by an external reviewer familiar with the language.
- `locked`: stable enough for repeated public benchmark reporting.
