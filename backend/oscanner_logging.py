"""Persistent logging helpers for Oscanner backend services."""

from __future__ import annotations

import os
import re
import sys
import threading
from pathlib import Path
from typing import Optional, TextIO

_FALSE_VALUES = {"0", "false", "no", "off"}
_DEFAULT_MAX_BYTES = 10 * 1024 * 1024
_DEFAULT_BACKUP_COUNT = 5
_SECRET_NAME_RE = re.compile(r"(TOKEN|KEY|SECRET|PASSWORD|PASS|CREDENTIAL)", re.IGNORECASE)


def _safe_filename(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip(".-_")
    return name or "backend"


def _log_home_dir() -> Path:
    if os.getenv("OSCANNER_HOME"):
        return Path(os.environ["OSCANNER_HOME"]).expanduser()
    data_home = Path(os.getenv("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))).expanduser()
    return data_home / "oscanner"


def get_log_dir() -> Path:
    """Return the directory used for persisted backend logs."""
    if os.getenv("OSCANNER_LOG_DIR"):
        return Path(os.environ["OSCANNER_LOG_DIR"]).expanduser()
    return _log_home_dir() / "logs"


def get_service_log_path(service_name: str) -> Path:
    """Return the default log path for a backend service."""
    return get_log_dir() / f"{_safe_filename(service_name)}.log"


def _int_from_env(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _mask_secret_value(value: str) -> str:
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}...{value[-4:]}"


def _iter_sensitive_env_values() -> list[str]:
    values: list[str] = []
    for key, value in os.environ.items():
        if not value or len(value) < 8:
            continue
        if _SECRET_NAME_RE.search(key):
            values.append(value)
    # Replace longer values first so nested secrets are masked predictably.
    return sorted(set(values), key=len, reverse=True)


def mask_known_secrets(text: str) -> str:
    """Mask sensitive environment variable values before persisting logs."""
    masked = text
    for secret in _iter_sensitive_env_values():
        masked = masked.replace(secret, _mask_secret_value(secret))
    return masked


class _RotatingFileWriter:
    def __init__(self, path: Path, *, max_bytes: int, backup_count: int) -> None:
        self.path = path
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self._lock = threading.RLock()
        self._file: Optional[TextIO] = None

    def write(self, text: str) -> None:
        if not text:
            return
        safe_text = mask_known_secrets(text)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._rollover_if_needed(len(safe_text.encode("utf-8", errors="replace")))
            if self._file is None or self._file.closed:
                self._file = self.path.open("a", encoding="utf-8", errors="replace")
            self._file.write(safe_text)

    def flush(self) -> None:
        with self._lock:
            if self._file is not None and not self._file.closed:
                self._file.flush()

    def close(self) -> None:
        with self._lock:
            if self._file is not None and not self._file.closed:
                self._file.close()

    def _rollover_if_needed(self, incoming_bytes: int) -> None:
        if self.max_bytes <= 0:
            return
        try:
            current_size = self.path.stat().st_size if self.path.exists() else 0
        except OSError:
            current_size = 0
        if current_size + incoming_bytes <= self.max_bytes:
            return

        if self._file is not None and not self._file.closed:
            self._file.close()

        if self.backup_count <= 0:
            try:
                self.path.unlink(missing_ok=True)
            except OSError:
                pass
            return

        for idx in range(self.backup_count - 1, 0, -1):
            src = self.path.with_name(f"{self.path.name}.{idx}")
            dst = self.path.with_name(f"{self.path.name}.{idx + 1}")
            if src.exists():
                try:
                    src.replace(dst)
                except OSError:
                    pass
        if self.path.exists():
            try:
                self.path.replace(self.path.with_name(f"{self.path.name}.1"))
            except OSError:
                pass
        self._file = None


class _TeeStream:
    def __init__(self, original: TextIO, writer: _RotatingFileWriter, log_path: Path) -> None:
        self._original = original
        self._writer = writer
        self._oscanner_log_path = str(log_path)
        self.encoding = getattr(original, "encoding", "utf-8")
        self.errors = getattr(original, "errors", "replace")

    def write(self, text: str) -> int:
        if not isinstance(text, str):
            text = str(text)
        written = self._original.write(text)
        self._writer.write(text)
        return written if isinstance(written, int) else len(text)

    def flush(self) -> None:
        self._original.flush()
        self._writer.flush()

    def isatty(self) -> bool:
        return bool(getattr(self._original, "isatty", lambda: False)())

    def fileno(self) -> int:
        return self._original.fileno()

    def close(self) -> None:
        self.flush()

    def __getattr__(self, name: str):
        return getattr(self._original, name)


def configure_service_logging(service_name: str) -> Optional[Path]:
    """Persist stdout/stderr for a backend service while keeping console output."""
    persist_logs = os.getenv("OSCANNER_PERSIST_LOGS")
    if persist_logs is not None and persist_logs.strip().lower() in _FALSE_VALUES:
        return None
    if persist_logs is None and "pytest" in sys.modules:
        return None

    log_path = get_service_log_path(service_name)
    if getattr(sys.stdout, "_oscanner_log_path", None) == str(log_path):
        return log_path

    max_bytes = _int_from_env("OSCANNER_LOG_MAX_BYTES", _DEFAULT_MAX_BYTES)
    backup_count = _int_from_env("OSCANNER_LOG_BACKUP_COUNT", _DEFAULT_BACKUP_COUNT)
    writer = _RotatingFileWriter(log_path, max_bytes=max_bytes, backup_count=backup_count)
    sys.stdout = _TeeStream(sys.stdout, writer, log_path)  # type: ignore[assignment]
    sys.stderr = _TeeStream(sys.stderr, writer, log_path)  # type: ignore[assignment]
    print(f"[logs] Persisting {service_name} logs to {log_path}")
    return log_path
