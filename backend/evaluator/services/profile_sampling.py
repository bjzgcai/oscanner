"""Deterministic profile evidence sampling; missing data is never negative evidence."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from math import ceil
from pathlib import PurePosixPath
from typing import Any, Iterable

ENGINEERING = {"source_implementation", "test_quality", "engineering_config", "architecture_documentation"}
SOURCE = {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".cpp", ".c", ".h", ".cs", ".rb", ".php", ".swift", ".kt", ".sh", ".sql", ".ipynb", ".cu"}
QUOTAS = {"source_implementation": .45, "test_quality": .20, "engineering_config": .20, "documentation": .10}


def file_category(path: str) -> str:
    path = path.lower().removeprefix("./")
    name = PurePosixPath(path).name
    parts = PurePosixPath(path).parts
    if any(p in {"vendor", "node_modules", "dist", "build", "__pycache__"} for p in parts) or name.endswith((".min.js", ".map", ".png", ".jpg", ".gif", ".svg")):
        return "generated_or_low_signal"
    if any(p in {"test", "tests", "__tests__"} for p in parts) or name.startswith("test_") or any(p in name for p in (".spec.", ".test.", "_test.")):
        return "test_quality"
    if path.startswith((".github/workflows/", ".circleci/")) or any(p in {"k8s", "kubernetes", "terraform", "helm"} for p in parts) or name.startswith(("dockerfile", "docker-compose", ".eslintrc", ".pre-commit-config")) or name in {"makefile", "justfile", "pyproject.toml", "package.json", "package-lock.json", "poetry.lock", "uv.lock", "tsconfig.json", "cargo.toml", "go.mod"} or name.endswith(".tf"):
        return "engineering_config"
    if any(p in {"adr", "adrs", "architecture"} for p in parts):
        return "architecture_documentation"
    if PurePosixPath(name).suffix in SOURCE:
        return "source_implementation"
    if name.endswith((".md", ".rst", ".adoc", ".txt")) or path.startswith(("docs/", "doc/")):
        return "documentation"
    return "unknown"


def normalize_commit(commit: dict[str, Any]) -> dict[str, Any]:
    item = dict(commit)
    files = []
    for raw in commit.get("files") or commit.get("changed_files") or []:
        entry = dict(raw) if isinstance(raw, dict) else {"filename": raw}
        path = entry.get("filename") or entry.get("path")
        if isinstance(path, str) and path.strip():
            entry["filename"] = path.strip()
            files.append(entry)
    categories = {file_category(f["filename"]) for f in files}
    order = ["test_quality", "engineering_config", "source_implementation", "architecture_documentation", "unknown", "documentation", "generated_or_low_signal"]
    item["category"] = next((c for c in order if c in categories), "unknown")
    item["files"] = files
    item["repository"] = commit.get("repo_url") or commit.get("repo_full_name") or "unknown"
    item["committed_at"] = commit.get("date") or commit.get("committed_at") or ""
    item["author_match_method"] = commit.get("author_match_method") or ("email" if commit.get("matched_email") else "login" if commit.get("matched_roles") else "broad_attribution")
    stats = commit.get("stats") or {}
    for key in ("additions", "deletions"):
        item[key] = int(stats.get(key) or commit.get(key) or sum(int(f.get(key) or 0) for f in files))
    item["detail_complete"] = bool(files) and not commit.get("detail_incomplete")
    return item


def _repo(item):
    return (item.get("platform", ""), item["repository"])


def _rank(item):
    # Changed-line volume is deliberately bounded; a code dump is not quality.
    return (item["category"] in ENGINEERING, item["detail_complete"], min(item["additions"] + item["deletions"], 200), str(item["committed_at"]), str(item.get("sha", "")))


def candidate_window(commits: Iterable[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Bound detail requests, cycling repositories and evenly spaced history."""
    groups = defaultdict(list)
    for commit in commits:
        groups[(commit.get("platform"), commit.get("repo_full_name"))].append(commit)
    queues = []
    for key in sorted(groups, key=str):
        items = sorted(groups[key], key=lambda c: str(c.get("date") or ""), reverse=True)
        # Breadth-first bisection covers recent, old, and middle history early.
        indices, ranges = [], [(0, len(items) - 1)]
        if items:
            indices.append(0)
        while ranges:
            lo, hi = ranges.pop(0)
            if hi <= lo:
                continue
            indices.append(hi)
            mid = (lo + hi) // 2
            ranges.extend([(lo, mid), (mid + 1, hi - 1)])
        queues.append([items[i] for i in dict.fromkeys(indices)])
    result = []
    while any(queues) and len(result) < limit:
        for queue in queues:
            if queue and len(result) < limit:
                result.append(queue.pop(0))
    return result


def sample_profile_commits(commits: Iterable[dict[str, Any]], limit: int):
    unique = {}
    patches = set()
    for raw in commits:
        if not isinstance(raw, dict) or not raw.get("sha"):
            continue
        item = normalize_commit(raw)
        files = item["files"]
        if files and all(f.get("patch") for f in files) and not raw.get("detail_incomplete"):
            fingerprint = hashlib.sha256(json.dumps(
                sorted((f["filename"], f["patch"]) for f in files), ensure_ascii=True,
            ).encode()).hexdigest()
            patch_key = (_repo(item), raw.get("matched_email") or raw.get("matched_identity"), fingerprint)
            if patch_key in patches:
                continue
            patches.add(patch_key)
        # Identical Git objects mirrored across forks count once. A revert has
        # its own diff and SHA and must not be discarded by its title alone.
        key = (item.get("platform"), item["sha"])
        if key not in unique or _rank(item) > _rank(unique[key]):
            unique[key] = item
    candidates = sorted(unique.values(), key=_rank, reverse=True)
    budget = min(max(1, int(limit)), len(candidates))
    repos = {_repo(c) for c in candidates}
    repo_cap = max(ceil(budget * .30), ceil(budget / max(1, len(repos))))
    selected, counts, periods = [], Counter(), Counter()

    def choose(pool, reason, relax=False):
        eligible = [c for c in pool if c not in selected and (relax or counts[_repo(c)] < repo_cap)]
        if not eligible or len(selected) >= budget:
            return False
        eligible.sort(key=lambda c: (counts[_repo(c)], periods[(_repo(c), str(c["committed_at"])[:4])]))
        item = eligible[0]
        item["selection_reason"] = reason
        selected.append(item)
        counts[_repo(item)] += 1
        periods[(_repo(item), str(item["committed_at"])[:4])] += 1
        return True

    # Reserve 5% for recent activity, then ensure repository coverage where
    # budget permits. Quotas are targets; coverage and actual supply win.
    recent = sorted(candidates, key=lambda c: str(c["committed_at"]), reverse=True)
    for _ in range(max(1, int(budget * .05)) if budget >= 5 else 0):
        choose(recent, "recent_activity")
    for repo in sorted(repos, key=str):
        if not counts[repo]:
            choose([c for c in candidates if _repo(c) == repo], "repository_coverage")
    for category, fraction in QUOTAS.items():
        bucket = {category, "architecture_documentation"} if category == "engineering_config" else {category}
        target = round(budget * fraction)
        while sum(c["category"] in bucket for c in selected) < target:
            if not choose([c for c in candidates if c["category"] in bucket], "category_and_history_coverage"):
                break
    for pool in ([c for c in candidates if c["category"] in ENGINEERING], candidates):
        while choose(pool, "redistributed_quota"):
            pass
    while choose(candidates, "supply_limited_cap_relaxation", relax=True):
        pass
    engineering = sum(c["category"] in ENGINEERING for c in selected)
    complete = sum(c["detail_complete"] for c in selected)
    uncertain = any(c["author_match_method"] == "broad_attribution" for c in selected)
    confidence = "low" if engineering < 3 or complete < len(selected) or uncertain else "medium"
    if engineering >= 10 and complete == len(selected) and not uncertain and len(counts) >= 2:
        confidence = "high"
    summary = {"sampling_version": "profile-v1", "available_commit_count": len(candidates), "sampled_commit_count": len(selected), "engineering_commit_count": engineering, "documentation_only_commit_count": sum(c["category"] == "documentation" for c in selected), "repository_coverage": len(counts), "available_repository_count": len(repos), "detail_complete_count": complete, "evidence_confidence": confidence}
    return selected, summary


def annotate_evaluation(evaluation, summary, commits=()):
    evaluation["sampling_summary"] = dict(summary)
    evaluation["evidence_confidence"] = summary["evidence_confidence"]
    evaluation["assessment_status"] = "insufficient_evidence" if summary["evidence_confidence"] == "low" else "evidence_based"
    evaluation["sampled_evidence"] = [
        {**{key: c.get(key) for key in ("repository", "sha", "url", "committed_at", "category", "selection_reason", "author_match_method", "additions", "deletions")},
         "files": [f["filename"] for f in c.get("files", [])]}
        for c in commits
    ]
    if evaluation["assessment_status"] == "insufficient_evidence":
        evaluation["evidence_notice"] = "证据不足：分数仅描述已采集样本，不能据此认定个人缺少工程能力或确定为 L1。"
    return evaluation
