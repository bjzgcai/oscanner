# Benchmark Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a root `benchmark/` directory that can start inside Oscanner for easy testing and later move to a standalone benchmark repository.

**Architecture:** The benchmark stores metadata only: public repo URLs, pinned refs, target language, developer identity, L1-L5 stage, evaluator fields, runner feature-test fields, and fairness notes. Oscanner can consume this manifest locally now, while the same directory can become an external dataset later without carrying cloned third-party source.

**Tech Stack:** Markdown documentation, YAML manifests, existing Oscanner evaluator and repos_runner APIs.

---

### Task 1: Benchmark Directory Structure

**Files:**
- Create: `benchmark/README.md`
- Create: `benchmark/schema.md`
- Create: `benchmark/repos.yaml`
- Create: `benchmark/feature_requirements/python.yaml`
- Create: `benchmark/feature_requirements/javascript-typescript.yaml`
- Create: `benchmark/feature_requirements/go.yaml`
- Create: `benchmark/feature_requirements/rust.yaml`
- Create: `benchmark/feature_requirements/java.yaml`
- Create: `benchmark/feature_requirements/cpp.yaml`
- Create: `benchmark/notes/fairness-methodology.md`

- [ ] **Step 1: Create documentation and manifest files**

Use `apply_patch` to add the files listed above. Keep all benchmark files metadata-only; do not clone or commit third-party source repositories.

- [ ] **Step 2: Verify YAML files parse**

Run:

```bash
python - <<'PY'
from pathlib import Path
import yaml

for path in sorted(Path("benchmark").rglob("*.yaml")):
    with path.open("r", encoding="utf-8") as fh:
        yaml.safe_load(fh)
    print(f"parsed {path}")
PY
```

Expected: every YAML file prints with no exception.

- [ ] **Step 3: Verify scaffold files exist**

Run:

```bash
find benchmark -maxdepth 3 -type f | sort
```

Expected: all files listed in this plan appear.

