# Oscanner Specs

This directory records implemented product behavior for the Oscanner Skill
Evaluator repository. It is intentionally rooted at the repository top level so
future work can start from current behavior before changing APIs, plugin
contracts, runner semantics, or dashboard flows.

## Implemented Feature Specs

- [Implemented Features](implemented-features.md): current backend, runner,
  dashboard, CLI, plugin, checker, storage, and test-support behavior.

## Related Docs

- [Architecture](../docs/01_architecture.md)
- [Evaluation Architecture](../docs/03_evaluation_architecture.md)
- [Trajectory Evaluation](../docs/06_trajectory_evaluation.md)
- [Limitations and Roadmap](../docs/LIMITATION.md)
- [Backend README](../backend/evaluator/README.md)
- [Repos Runner README](../backend/repos_runner/README.md)
- [Dashboard README](../frontend/webapp/README.md)

## Maintenance Rules

- Update these specs when implemented behavior changes, especially API payloads,
  persisted data shape, plugin scan output, runner report shape, or dashboard
  routes.
- Keep provider behavior explicit. GitHub and Gitee are both first-class
  providers unless a limitation is documented.
- Do not document generated cache data, local secrets, cloned repositories, or
  runtime reports as source-controlled product state.
