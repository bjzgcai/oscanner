"""Deterministic profile evidence sampling; missing data is never negative evidence."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from math import ceil
from pathlib import PurePosixPath
from typing import Any, Iterable

ENGINEERING = {"source_implementation", "test_quality", "engineering_config", "architecture_documentation"}
SOURCE = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".cpp", ".c", ".h",
    ".cs", ".rb", ".php", ".swift", ".kt", ".sh", ".sql", ".ipynb", ".cu", ".vue",
    ".svelte", ".css", ".scss", ".sass", ".less", ".html", ".htm", ".dart", ".scala",
    ".r", ".jl", ".m", ".mm", ".pl", ".lua", ".ex", ".exs", ".erl", ".hs", ".clj",
}
LOCKFILES = {
    "package-lock.json", "poetry.lock", "uv.lock", "yarn.lock", "pnpm-lock.yaml",
    "cargo.lock", "composer.lock", "gemfile.lock", "pipfile.lock",
}
QUOTAS = {"source_implementation": .45, "test_quality": .20, "engineering_config": .20, "documentation": .10}
PERSONAL_ATTRIBUTIONS = {"verified_email", "verified_login", "profile_owned_non_fork"}


def file_category(path: str) -> str:
    path = path.lower().removeprefix("./")
    name = PurePosixPath(path).name
    parts = PurePosixPath(path).parts
    if (
        any(p in {"vendor", "node_modules", "dist", "build", "__pycache__"} for p in parts)
        or name in LOCKFILES
        or name.endswith((".min.js", ".map", ".png", ".jpg", ".gif", ".svg"))
    ):
        return "generated_or_low_signal"
    if any(p in {"test", "tests", "__tests__"} for p in parts) or name.startswith("test_") or any(p in name for p in (".spec.", ".test.", "_test.")):
        return "test_quality"
    if path.startswith((".github/workflows/", ".circleci/")) or any(p in {"k8s", "kubernetes", "terraform", "helm"} for p in parts) or name.startswith(("dockerfile", "docker-compose", ".eslintrc", ".pre-commit-config")) or name in {"makefile", "justfile", "pyproject.toml", "package.json", "tsconfig.json", "cargo.toml", "go.mod"} or name.endswith(".tf"):
        return "engineering_config"
    if any(p in {"adr", "adrs", "architecture"} for p in parts):
        return "architecture_documentation"
    if PurePosixPath(name).suffix in SOURCE:
        return "source_implementation"
    if name.endswith((".md", ".rst", ".adoc", ".txt")) or path.startswith(("docs/", "doc/")):
        return "documentation"
    return "unknown"


def attribution_category(commit: dict[str, Any]) -> str:
    """Classify how strongly a collected artifact is attributed to the user."""
    explicit = str(commit.get("attribution_category") or commit.get("attribution") or "").strip()
    aliases = {
        "email": "verified_email",
        "github_login": "verified_login",
        "commit_association": "organization_or_team_context",
        "broad_attribution": "repo_fallback",
    }
    if explicit in PERSONAL_ATTRIBUTIONS | {"repo_fallback", "organization_or_team_context"}:
        return explicit
    if explicit in aliases:
        return aliases[explicit]
    if commit.get("matched_email"):
        return "verified_email"
    roles = commit.get("matched_roles") or []
    if commit.get("matched_login") or any(
        isinstance(role, dict) and role.get("github_login") for role in roles
    ):
        return "verified_login"
    if commit.get("organization_context"):
        return "organization_or_team_context"
    source = str(commit.get("source") or "")
    if "profile" in source and "fork" not in source:
        return "profile_owned_non_fork"
    return "repo_fallback"


def _commit_actor_identity(commit: dict[str, Any]) -> str:
    nested = commit.get("commit") if isinstance(commit.get("commit"), dict) else {}
    author = nested.get("author") if isinstance(nested.get("author"), dict) else {}
    login = str(author.get("login") or author.get("github_login") or "").strip()
    if login:
        return login.lower()
    return str(commit.get("matched_email") or commit.get("author") or "").strip().lower()


def annotate_repository_fallback(commits: Iterable[dict[str, Any]], *, dominant_threshold: float = 0.8) -> bool:
    """Mark repo-only evidence personal only when one contributor dominates."""
    items = [commit for commit in commits if isinstance(commit, dict)]
    identities = Counter(_commit_actor_identity(commit) for commit in items if _commit_actor_identity(commit))
    dominant = identities.most_common(1)[0][1] / max(1, sum(identities.values())) if identities else 0
    personal = bool(identities) and dominant >= dominant_threshold
    for commit in items:
        if not commit.get("matched_email") and not commit.get("matched_login"):
            commit["personal_evidence"] = personal
    return personal


def normalize_collaboration_item(item: dict[str, Any], identities: Iterable[str] = ()) -> dict[str, Any]:
    """Normalize a PR/issue/review row and its actor attribution."""
    normalized = dict(item)
    actor = str(
        normalized.get("actor")
        or normalized.get("github_login")
        or normalized.get("login")
        or normalized.get("user")
        or ""
    ).strip()
    identity_set = {str(value or "").strip().lower() for value in identities if str(value or "").strip()}
    category = "verified_login" if actor and actor.lower() in identity_set else "organization_or_team_context"
    normalized.update({
        "actor": actor,
        "action_type": str(normalized.get("action_type") or normalized.get("source") or "collaboration"),
        "attribution_category": category,
        "personal_evidence": category == "verified_login",
    })
    return normalized


def summarize_attribution(items: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = [item for item in items if isinstance(item, dict)]
    counts = Counter(attribution_category(item) for item in rows)
    personal = sum(bool(item.get("personal_evidence")) or attribution_category(item) in PERSONAL_ATTRIBUTIONS for item in rows)
    return {
        "total": len(rows),
        "personal_evidence": personal,
        "context_only": len(rows) - personal,
        "counts": dict(sorted(counts.items())),
    }


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
    item["author_match_method"] = commit.get("author_match_method") or (
        "email" if commit.get("matched_email")
        else "login" if commit.get("matched_login") or commit.get("matched_roles")
        else "broad_attribution"
    )
    item["attribution_category"] = attribution_category(commit)
    item["personal_evidence"] = bool(
        commit.get("personal_evidence")
        or item["attribution_category"] in PERSONAL_ATTRIBUTIONS
    )
    stats = commit.get("stats") or {}
    for key in ("additions", "deletions"):
        item[key] = int(stats.get(key) or commit.get(key) or sum(int(f.get(key) or 0) for f in files))
    stats = commit.get("stats") if isinstance(commit.get("stats"), dict) else {}
    legitimate_empty_diff = (
        not files
        and not commit.get("detail_incomplete")
        and (
            commit.get("empty_diff")
            or len(commit.get("parents") or []) > 1
            or str(commit.get("message") or "").startswith("Merge ")
            or int(stats.get("total") or 0) == 0
        )
    )
    item["detail_complete"] = (bool(files) or legitimate_empty_diff) and not commit.get("detail_incomplete")
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
            patch_key = (item["repository"], raw.get("matched_email") or raw.get("matched_identity"), fingerprint)
            if patch_key in patches:
                continue
            patches.add(patch_key)
        # Identical Git objects mirrored across forks count once. A revert has
        # its own diff and SHA and must not be discarded by its title alone.
        key = str(item["sha"]).lower()
        if key not in unique or _rank(item) > _rank(unique[key]):
            unique[key] = item
        else:
            mirrors = unique[key].setdefault("mirror_repositories", [])
            mirror = {"platform": item.get("platform"), "repository": item.get("repo_full_name"), "url": item.get("url")}
            if mirror not in mirrors:
                mirrors.append(mirror)
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
    uncertain = any(not c["personal_evidence"] for c in selected)
    confidence = "low" if engineering < 3 or complete < len(selected) or uncertain else "medium"
    if engineering >= 10 and complete == len(selected) and not uncertain and len(counts) >= 2:
        confidence = "high"
    attribution_summary = summarize_attribution(selected)
    summary = {
        "sampling_version": "profile-v2",
        "available_commit_count": len(candidates),
        "sampled_commit_count": len(selected),
        "engineering_commit_count": engineering,
        "documentation_only_commit_count": sum(c["category"] == "documentation" for c in selected),
        "repository_coverage": len(counts),
        "available_repository_count": len(repos),
        "detail_complete_count": complete,
        "attribution_summary": attribution_summary,
        "evidence_coverage": {
            "sampled_commit_count": len(selected),
            "engineering_commit_count": engineering,
            "detail_complete_count": complete,
            "repository_coverage": len(counts),
            "personal_evidence_count": attribution_summary["personal_evidence"],
            "context_only_count": attribution_summary["context_only"],
        },
        "evidence_confidence": confidence,
    }
    return selected, summary


def annotate_evaluation(evaluation, summary, commits=()):
    evaluation["sampling_summary"] = dict(summary)
    evaluation["evidence_confidence"] = summary["evidence_confidence"]
    evaluation["assessment_status"] = "insufficient_evidence" if summary["evidence_confidence"] == "low" else "scored"
    evaluation["sampled_evidence"] = [
        {**{key: c.get(key) for key in ("repository", "sha", "url", "committed_at", "category", "selection_reason", "author_match_method", "additions", "deletions")},
         "files": [f["filename"] for f in c.get("files", [])]}
        for c in commits
    ]
    evaluation["ranking_eligible"] = (
        evaluation["assessment_status"] == "scored"
        and summary.get("engineering_commit_count", 0) >= 3
        and summary.get("attribution_summary", {}).get("context_only", 0) == 0
    )
    evaluation["evidence_limitations"] = []
    if summary.get("attribution_summary", {}).get("context_only"):
        evaluation["evidence_limitations"].append(
            f"{summary['attribution_summary']['context_only']} items use repository or team context rather than verified personal attribution"
        )
    if summary.get("engineering_commit_count", 0) < 3:
        evaluation["evidence_limitations"].append("Fewer than three engineering commits with analyzable evidence were sampled")
    if not evaluation["ranking_eligible"]:
        evaluation["evidence_notice"] = "证据不足或归属待确认：结果不能用于认定个人缺少工程能力，也不能直接参与排名。"
    return evaluation
