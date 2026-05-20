"""SQLite persistence for trajectory polling jobs."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from evaluator.paths import get_data_dir


DEFAULT_POLL_JOB_TTL_SECONDS = 60 * 60


def get_default_poll_db_path() -> Path:
    configured = os.getenv("OSCANNER_TRAJECTORY_POLL_DB", "").strip()
    if configured:
        return Path(configured).expanduser()
    return get_data_dir() / "trajectory_poll_jobs.sqlite3"


class SQLiteTrajectoryPollStore:
    """Small SQLite-backed store for one-off trajectory poll jobs."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        ttl_seconds: int = DEFAULT_POLL_JOB_TTL_SECONDS,
    ) -> None:
        self.db_path = Path(db_path) if db_path is not None else get_default_poll_db_path()
        self.ttl_seconds = ttl_seconds
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trajectory_poll_jobs (
                    job_id TEXT PRIMARY KEY,
                    created_at REAL NOT NULL,
                    done INTEGER NOT NULL DEFAULT 0,
                    error TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trajectory_poll_events (
                    job_id TEXT NOT NULL,
                    event_id INTEGER NOT NULL,
                    event TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    PRIMARY KEY (job_id, event_id),
                    FOREIGN KEY (job_id)
                        REFERENCES trajectory_poll_jobs(job_id)
                        ON DELETE CASCADE
                )
                """
            )

    def create_job(self, job_id: str, created_at: float | None = None) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO trajectory_poll_jobs (job_id, created_at, done, error)
                VALUES (?, ?, 0, NULL)
                """,
                (job_id, time.time() if created_at is None else created_at),
            )

    def append_event(self, job_id: str, event: str, data: Any) -> int:
        data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(MAX(event_id) + 1, 0) AS next_id
                FROM trajectory_poll_events
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()
            event_id = int(row["next_id"])
            conn.execute(
                """
                INSERT INTO trajectory_poll_events (job_id, event_id, event, data_json)
                VALUES (?, ?, ?, ?)
                """,
                (job_id, event_id, event, data_json),
            )
            return event_id

    def finish_job(self, job_id: str, error: str | None = None) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE trajectory_poll_jobs
                SET done = 1, error = COALESCE(?, error)
                WHERE job_id = ?
                """,
                (error, job_id),
            )

    def get_job(self, job_id: str, cursor: int = 0) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            job = conn.execute(
                """
                SELECT job_id, done, error
                FROM trajectory_poll_jobs
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()
            if job is None:
                return None

            rows = conn.execute(
                """
                SELECT event_id, event, data_json
                FROM trajectory_poll_events
                WHERE job_id = ? AND event_id >= ?
                ORDER BY event_id ASC
                """,
                (job_id, cursor),
            ).fetchall()

        events = [
            {
                "id": int(row["event_id"]),
                "event": row["event"],
                "data": json.loads(row["data_json"]),
            }
            for row in rows
        ]
        next_cursor = events[-1]["id"] + 1 if events else cursor
        return {
            "job_id": job_id,
            "events": events,
            "next_cursor": next_cursor,
            "done": bool(job["done"]),
            "error": job["error"],
        }

    def cleanup(self, now: float | None = None) -> None:
        threshold = (time.time() if now is None else now) - self.ttl_seconds
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                DELETE FROM trajectory_poll_jobs
                WHERE done = 1 AND created_at < ?
                """,
                (threshold,),
            )

    def mark_interrupted_jobs(self, before_created_at: float, message: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE trajectory_poll_jobs
                SET done = 1, error = ?
                WHERE done = 0 AND created_at < ?
                """,
                (message, before_created_at),
            )
