# Oscanner Benchmark Draft

This directory is a metadata-only draft benchmark for testing Oscanner's
`evaluator` and `repos_runner` services.

The intended benchmark shape is:

- 6 programming language tracks: Python, JavaScript/TypeScript, Go, Rust, Java,
  and C/C++.
- 1 highly recognized public developer per language track.
- 5 public non-fork repositories, tags, or commit windows per developer,
  mapped to L1 through L5 career stages where possible.
- 30 benchmark entries total.

## Why This Starts Inside Oscanner

Keeping the draft here makes it easy to test against the local evaluator API,
runner API, plugins, and frontend workflow while the benchmark schema is still
changing. The directory is intentionally structured so it can later move into a
standalone repository such as `oscanner-benchmark` with minimal changes.

## What Belongs Here

- Public repository URLs; prefer personal repositories when evidence is
  comparable, but allow organization repositories when attribution is clear and
  the repo exposes stronger engineering evidence.
- Pinned tags, branches, SHAs, or commit ranges.
- Developer identity and author aliases.
- L1-L5 stage labels and evidence for each label.
- Feature requirements used by `repos_runner`.
- Fairness and reproducibility notes.
- Evaluation result exports, when they are small and anonymized enough to share.

## What Does Not Belong Here

- Cloned third-party repository source code.
- Local cache data from `~/.local/share/oscanner`.
- API keys, tokens, or private repository URLs.
- Large generated runner reports unless they are intentionally curated as
  benchmark artifacts.

## Files

- `repos.yaml`: the 30-slot benchmark manifest.
- `schema.md`: field definitions for benchmark entries.
- `feature_requirements/*.yaml`: language-level feature-test templates for
  `repos_runner`.
- `notes/fairness-methodology.md`: selection and interpretation rules for
  defending the benchmark as fair.

## First Workflow

1. Choose one public developer per language.
2. Fill the five L1-L5 entries for that developer with public non-fork repos,
   tags, SHAs, or commit windows.
3. Use chronology as a main factor and maturity/design complexity as the
   tie-breaker.
4. Pin each candidate to a tag or SHA before using it in locked benchmark runs.
5. Add evidence explaining why each entry represents that level.
6. Run evaluator scoring for the author and selected ref or range.
7. Run repos_runner tests with the matching feature requirement template.
8. Save a small result summary outside this manifest, then promote stable
   benchmark data into the future standalone benchmark repository.
