"""Runtime environment profiles for untrusted repository execution."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from dotenv import dotenv_values

from .paths import get_home_dir


SAFE_TEST_DEFAULTS: dict[str, str] = {
    "JWT_SECRET": "oscanner-test-jwt-secret",
    "SESSION_SECRET": "oscanner-test-session-secret",
    "NODE_ENV": "test",
    "CI": "1",
    "DATABASE_URL": "sqlite:///./.oscanner-test.sqlite3",
    "REDIS_URL": "redis://127.0.0.1:6379/0",
}

PAID_OR_REAL_SECRET_KEYS = {
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "STRIPE_SECRET_KEY",
    "AWS_SECRET_ACCESS_KEY",
}

BLOCKED_SECRET_ENV_KEYS = {
    *PAID_OR_REAL_SECRET_KEYS,
    "OSCANNER_LLM_API_KEY",
    "OPEN_ROUTER_KEY",
    "OPENROUTER_API_KEY",
    "GITHUB_TOKEN",
    "GITEE_TOKEN",
    "GITEE_ENTERPRISE_TOKEN",
    "AWS_ACCESS_KEY_ID",
    "AWS_SESSION_TOKEN",
}

VALID_REQUIRED_POLICIES = {"strict", "warn", "best_effort"}

_ENV_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,}$")
_DOTENV_ASSIGNMENT_RE = re.compile(
    r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=",
    re.MULTILINE,
)
_ENV_USAGE_PATTERNS = (
    re.compile(r"\bprocess\.env\.([A-Z][A-Z0-9_]{2,})\b"),
    re.compile(r"\bos\.getenv\(\s*[\"']([A-Z][A-Z0-9_]{2,})[\"']"),
    re.compile(r"\bos\.environ(?:\.get)?\(\s*[\"']([A-Z][A-Z0-9_]{2,})[\"']"),
    re.compile(r"\bos\.environ\[\s*[\"']([A-Z][A-Z0-9_]{2,})[\"']\s*\]"),
    re.compile(r"\benv\(\s*[\"']([A-Z][A-Z0-9_]{2,})[\"']\s*\)"),
    re.compile(r"\$\{([A-Z][A-Z0-9_]{2,})\}"),
)
_PROFILE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")

_ENV_TEMPLATE_NAMES = (
    ".env.example",
    ".env.sample",
    ".env.template",
    ".env.local.example",
    ".env.test.example",
    ".env.development.example",
)
_CONFIG_SAMPLE_NAMES = (
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    "package.json",
    "pyproject.toml",
    "alembic.ini",
    "prisma/schema.prisma",
    "README.md",
    "README.en.md",
    "README.txt",
)
_SOURCE_ENV_SUFFIXES = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
    ".go",
    ".rb",
    ".php",
    ".java",
    ".kt",
    ".cs",
}
_SOURCE_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "coverage",
    ".next",
    ".nuxt",
    ".turbo",
    "target",
    "__pycache__",
}
_IGNORED_ENV_WORDS = {
    "API",
    "ASCII",
    "CLI",
    "CSS",
    "CSV",
    "DOM",
    "GET",
    "HTML",
    "HTTP",
    "HTTPS",
    "JSON",
    "JWT",
    "LLM",
    "PDF",
    "POST",
    "PUT",
    "README",
    "REST",
    "SQL",
    "TODO",
    "URL",
    "UUID",
    "VALUE",
    "XML",
    "YAML",
}


@dataclass(frozen=True)
class RuntimeEnvContext:
    """Resolved runtime environment without exposing values in reports."""

    profile: Optional[str]
    profile_path: Optional[str]
    required_policy: str
    env: dict[str, str]
    profile_keys: list[str]
    safe_default_keys: list[str]
    detected_required_keys: list[str]
    missing_required_keys: list[str]
    blocked_secret_keys: list[str]
    warnings: list[str]

    def command_env(self) -> dict[str, str]:
        """Return the env passed to repo setup/test commands."""
        base: dict[str, str] = {}
        for key in ["PATH", "HOME", "LANG", "LC_ALL", "TMPDIR"]:
            value = os.environ.get(key)
            if value:
                base[key] = value
        base["PYTHONUNBUFFERED"] = "1"
        base.update(self.env)
        return base

    def as_report(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "profile_path": self.profile_path,
            "required_policy": self.required_policy,
            "supplied_keys": sorted(self.env),
            "profile_keys": self.profile_keys,
            "safe_default_keys": self.safe_default_keys,
            "detected_required_keys": self.detected_required_keys,
            "missing_required_keys": self.missing_required_keys,
            "blocked_secret_keys": self.blocked_secret_keys,
            "warnings": self.warnings,
        }

    def should_fail_on_missing(self) -> bool:
        return self.required_policy == "strict" and bool(self.missing_required_keys)


def runtime_env_dir() -> Path:
    value = os.getenv("REPOS_RUNNER_RUNTIME_ENV_DIR")
    if value:
        return Path(value).expanduser()
    return get_home_dir() / "runtime-envs"


def _is_valid_env_key(value: str) -> bool:
    key = str(value or "").strip().upper()
    if key in _IGNORED_ENV_WORDS:
        return False
    return bool(_ENV_KEY_RE.fullmatch(key))


def _normalize_required_policy(value: Optional[str]) -> str:
    policy = str(value or "warn").strip().lower()
    if policy not in VALID_REQUIRED_POLICIES:
        raise ValueError(
            "runtime env required_policy must be one of: best_effort, strict, warn"
        )
    return policy


def _profile_candidates(profile: str) -> list[Path]:
    name = str(profile or "").strip()
    if not name or not _PROFILE_NAME_RE.fullmatch(name) or name in {".", ".."}:
        raise ValueError("runtime env profile must be a simple file/profile name")
    base = runtime_env_dir().resolve()
    candidates = [base / name]
    if not name.endswith(".env"):
        candidates.append(base / f"{name}.env")
    return candidates


def _resolve_profile_path(profile: str) -> Path:
    base = runtime_env_dir().resolve()
    for candidate in _profile_candidates(profile):
        resolved = candidate.expanduser().resolve()
        try:
            resolved.relative_to(base)
        except ValueError as exc:
            raise ValueError("runtime env profile path escapes profile directory") from exc
        if resolved.is_file():
            return resolved
    raise FileNotFoundError(f"Runtime env profile not found: {profile}")


def load_runtime_env_profile(profile: Optional[str]) -> tuple[dict[str, str], list[str], Optional[str]]:
    if not profile:
        return {}, [], None

    path = _resolve_profile_path(profile)
    raw_values = dotenv_values(path)
    env: dict[str, str] = {}
    blocked: list[str] = []
    for raw_key, raw_value in raw_values.items():
        key = str(raw_key or "").strip().upper()
        if not _is_valid_env_key(key):
            continue
        if key in BLOCKED_SECRET_ENV_KEYS:
            blocked.append(key)
            continue
        if raw_value is None or str(raw_value).strip() == "":
            continue
        env[key] = str(raw_value)
    return env, sorted(set(blocked)), str(path)


def _safe_read(path: Path, max_bytes: int = 20000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:max_bytes]
    except OSError:
        return ""


def _extract_env_keys_from_text(text: str) -> set[str]:
    keys: set[str] = set()
    for match in _DOTENV_ASSIGNMENT_RE.finditer(text):
        key = match.group(1).strip().upper()
        if _is_valid_env_key(key):
            keys.add(key)
    for pattern in _ENV_USAGE_PATTERNS:
        for match in pattern.finditer(text):
            key = match.group(1).strip().upper()
            if _is_valid_env_key(key):
                keys.add(key)
    return keys


def _iter_env_hint_files(repo_dir: Path) -> list[Path]:
    files: list[Path] = []
    for name in (*_ENV_TEMPLATE_NAMES, *_CONFIG_SAMPLE_NAMES):
        path = repo_dir / name
        if path.is_file():
            files.append(path)

    docs_dir = repo_dir / "docs"
    if docs_dir.is_dir():
        files.extend(sorted(docs_dir.rglob("*.md"))[:20])
    return files


def _iter_source_env_files(repo_dir: Path, limit: int = 300) -> list[Path]:
    files: list[Path] = []
    for path in sorted(repo_dir.rglob("*")):
        if len(files) >= limit:
            break
        try:
            rel = path.relative_to(repo_dir)
        except ValueError:
            continue
        if any(part in _SOURCE_SKIP_DIRS for part in rel.parts):
            continue
        if path.is_file() and path.suffix.lower() in _SOURCE_ENV_SUFFIXES:
            files.append(path)
    return files


def detect_required_env_keys(repo_dir: Path | str) -> list[str]:
    """Best-effort env-name discovery from examples, docs, and config files."""
    root = Path(repo_dir)
    detected: set[str] = set()
    if not root.is_dir():
        return []

    for path in _iter_env_hint_files(root):
        detected.update(_extract_env_keys_from_text(_safe_read(path)))
    for path in _iter_source_env_files(root):
        detected.update(_extract_env_keys_from_text(_safe_read(path, max_bytes=12000)))

    return sorted(detected)


def build_runtime_env_context(
    repo_dir: Path | str,
    *,
    profile: Optional[str] = None,
    required_policy: Optional[str] = "warn",
    include_safe_defaults: bool = True,
) -> RuntimeEnvContext:
    policy = _normalize_required_policy(required_policy)
    profile_env, blocked_from_profile, profile_path = load_runtime_env_profile(profile)

    env: dict[str, str] = {}
    safe_default_keys: list[str] = []
    if include_safe_defaults:
        env.update(SAFE_TEST_DEFAULTS)
        safe_default_keys = sorted(SAFE_TEST_DEFAULTS)
    env.update(profile_env)

    detected_required = detect_required_env_keys(repo_dir)
    missing_required = sorted(key for key in detected_required if key not in env)
    blocked = sorted(set(blocked_from_profile))
    warnings: list[str] = []
    if missing_required and policy == "warn":
        warnings.append(
            "Missing detected runtime env keys: " + ", ".join(missing_required)
        )
    if blocked:
        warnings.append(
            "Ignored paid/real secret env keys from profile: " + ", ".join(blocked)
        )

    return RuntimeEnvContext(
        profile=str(profile).strip() if profile else None,
        profile_path=profile_path,
        required_policy=policy,
        env=env,
        profile_keys=sorted(profile_env),
        safe_default_keys=safe_default_keys,
        detected_required_keys=detected_required,
        missing_required_keys=missing_required,
        blocked_secret_keys=blocked,
        warnings=warnings,
    )
