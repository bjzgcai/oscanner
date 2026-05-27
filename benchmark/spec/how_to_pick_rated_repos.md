# How To Pick Rated Repos

This note records the current thinking behind the benchmark selection process in
`benchmark/README.md`. The goal is to make the L1-L5 repository choices useful
for evaluating Oscanner, while staying honest about what the labels do and do
not prove.

## Short Answer

Manually picking the JavaScript/TypeScript examples first is a good bootstrap
step, but it should not become the only source of truth.

The manual JavaScript set should be treated as a calibration example: it shows
the intended shape of L1 through L5 selections. An LLM can then help find
candidate repositories for other languages, but the LLM should not be the final
judge. Final benchmark entries need explicit evidence, pinned refs, and human
review before they are used as rated examples.

In other words:

1. Use manual JavaScript picks to explain the selection style.
2. Use the LLM to discover and compare candidates.
3. Use human review to decide whether each candidate really fits the level.
4. Record the evidence and uncertainty in `repos.yaml`.

## Why Start With Manual JavaScript Picks

The JavaScript/TypeScript track is the first hand-calibrated track. It gives the
benchmark a concrete example of what the levels should feel like in practice:

- L1 should look like early, small-scope, learning-stage, or demo work.
- L2 should look like an independent utility or complete small feature.
- L3 should show reusable design, product intent, or module ownership.
- L4 should show stronger architecture, ecosystem awareness, compatibility, or
  maintainability judgment.
- L5 should show mature, influential, or unusually strong engineering work.

This is useful because the level definitions are abstract. Real repositories
make them easier to understand.

The risk is that JavaScript-specific signals can accidentally leak into other
languages. For example, package shape, test culture, release conventions,
frontend ecosystem influence, and repository size do not mean the same thing in
Go, Rust, Java, C/C++, and Python. The JS examples should guide the structure of
the decision, not force every language to look like JavaScript.

## What The Benchmark Is Actually Rating

This benchmark does not rate a developer's whole career. It rates a selected
public repository, tag, SHA, or commit window as a benchmark example for one
career-stage level.

That distinction matters. A famous developer may have a small toy repository,
and an early repository from a famous developer may still contain excellent
code. The label should describe the selected evidence, not the person's
reputation.

The intended benchmark shape is:

- six language tracks;
- one recognized public developer per language track;
- five public non-fork repositories, tags, SHAs, or commit windows per
  developer;
- L1-L5 ordering based mainly on chronology, with maturity and design complexity
  as tie-breakers;
- 30 total entries in `benchmark/repos.yaml`.

## Selection Principles

Prefer personal, non-fork repositories under the developer's own account when
the evidence is comparable. Organization repositories are allowed when they
provide stronger evidence for the intended level, but the selection must record
why the target developer's authorship or maintainership is attributable enough
for the benchmark.

Use chronology as the first ordering signal. Earlier work is usually a better
candidate for lower levels, and later mature work is usually a better candidate
for higher levels.

Use maturity and design complexity as the second ordering signal. Nearby
repositories in time should be separated by evidence such as API design,
testing, compatibility, performance work, system boundaries, maintenance
history, or ecosystem impact.

Pin every selected entry to a SHA, tag, or commit range before using it in
locked benchmark runs. Floating branches make the benchmark drift.

Do not force a perfect L1-L5 story. If a developer's public history does not
contain a credible example for a level, mark the gap instead of inventing
confidence.

## Role Of The LLM

The LLM is useful for candidate discovery, not final labeling.

Good uses:

- finding possible repositories for a developer and language;
- summarizing public evidence about scope, maturity, and impact;
- comparing several candidates against the L1-L5 definitions;
- identifying risks, such as sparse history, archived code, old tooling, or
  unclear author attribution;
- drafting `selection_evidence`, `expected_risks`, and `exclusion_notes`.

Bad uses:

- treating the LLM's chosen level as ground truth;
- asking the LLM to copy the JavaScript level examples directly into another
  ecosystem;
- letting popularity, stars, or reputation replace repository evidence;
- using an LLM-generated benchmark as proof that an LLM evaluator is correct.

The selection process should keep this separation clear: LLM suggestions are
candidates. Human-reviewed evidence creates benchmark labels.

## Recommended Workflow

1. Pick one recognized public developer for the language track.
2. List candidate public, non-fork repositories for that developer, including
   organization repositories where attribution is clear.
3. Remove repos that cannot be fetched publicly, cannot be attributed to the
   target author, require private credentials, or are unsafe to run.
4. Order candidates chronologically.
5. Compare nearby candidates by maturity, design complexity, tests, maintenance,
   and ecosystem impact.
6. Choose provisional L1-L5 entries.
7. Pin each entry to a SHA, tag, or commit range.
8. Write `selection_evidence` for each entry in `repos.yaml`.
9. Write `expected_risks` and `known_test_constraints` honestly.
10. Mark entries as `candidate` and `unreviewed`.
11. Run evaluator and repos_runner experiments.
12. Promote entries only after review: `self_reviewed`, then
    `expert_reviewed`, then `locked`.

## Evidence To Record

Each selected entry should have enough evidence that another maintainer can
understand why it was chosen without rerunning the whole search.

Useful evidence includes:

- why the developer represents the language track;
- why this repo is personal and attributable enough;
- why the selected ref or commit range is stable;
- why the repo belongs at this level;
- whether the project is early, mature, experimental, widely used, or
  ecosystem-shaping;
- whether tests, docs, releases, or compatibility constraints are meaningful for
  this language and time period;
- what was excluded and why.

## Level Heuristics

L1 means small scope, early work, simple fixes, demos, or learning-stage
contributions. It should not need to prove architecture ownership.

L2 means independent delivery. The repo should look like a complete small tool,
library, or feature area with some practical edge-case handling.

L3 means stronger ownership. The repo should show meaningful design decisions,
module structure, reusable APIs, tests, or maintainability work.

L4 means lead-level judgment. The repo should show architecture, compatibility,
performance, reliability, release discipline, or coordination concerns.

L5 means expert-level impact. The repo should show unusually strong technical
work, broad adoption, field influence, or a mature system that shapes how others
build.

These are heuristics, not mechanical rules. Repository size, stars, commit
count, and age are signals, but none of them is enough by itself.

## Review Policy

Use the review fields in `repos.yaml` conservatively:

- `unreviewed`: the entry is a first-pass candidate.
- `self_reviewed`: the benchmark maintainer checked the repo, ref, attribution,
  and evidence.
- `expert_reviewed`: someone familiar with the language or ecosystem reviewed
  the level assignment.
- `locked`: stable enough for repeated benchmark reporting.

Only `locked` entries should be used for public benchmark claims. Draft and
candidate entries are useful for developing Oscanner, but they should be
described as provisional.

## Main Caveat

This benchmark is a practical evaluation set, not a perfect measurement of
career progression. It is especially limited because the first version chooses
one public developer per language. That makes it easier to build and explain,
but it also means each language track can reflect the quirks of one person's
public repository history.

The benchmark becomes stronger as it records better evidence, receives external
review, and eventually adds more developers or more entries per level.
