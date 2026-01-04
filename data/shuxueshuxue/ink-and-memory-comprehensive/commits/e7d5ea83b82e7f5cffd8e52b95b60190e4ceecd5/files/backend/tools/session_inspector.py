#!/usr/bin/env python3
"""
Inspect and rebuild sessions for a specific user/day.

This utility lists every session that lands within the requested local day,
prints their metadata, deletes each row, and recreates it using the same
`database.save_session()` helper so we can verify our understanding of the schema.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect and rebuild sessions for a given day.")
    parser.add_argument("--email", help="User email (alternative to --user-id)")
    parser.add_argument("--user-id", type=int, help="User ID (alternative to --email)")
    parser.add_argument("--date", required=True, help="Local date in YYYY-MM-DD")
    parser.add_argument("--timezone", default="UTC", help="IANA timezone name (default: UTC)")
    return parser.parse_args()


def resolve_user_id(email: str | None, user_id: int | None) -> int:
    if user_id:
        user = database.get_user_by_id(user_id)
        if not user:
            raise SystemExit(f"User ID {user_id} not found")
        return user["id"]

    if email:
        user = database.get_user_by_email(email)
        if not user:
            raise SystemExit(f"User with email {email} not found")
        return user["id"]

    raise SystemExit("Either --email or --user-id is required.")


def local_day_bounds(day: str, tz_name: str) -> tuple[str, str]:
    tz = ZoneInfo(tz_name)
    local_start = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=tz)
    local_end = local_start + timedelta(days=1)
    utc_start = local_start.astimezone(timezone.utc)
    utc_end = local_end.astimezone(timezone.utc)
    return (
        utc_start.strftime("%Y-%m-%d %H:%M:%S"),
        utc_end.strftime("%Y-%m-%d %H:%M:%S"),
    )


def fetch_sessions(user_id: int, utc_start: str, utc_end: str) -> list[dict]:
    db = database.get_db()
    try:
        rows = db.execute(
            """
            SELECT id, name, editor_state_json, created_at, updated_at
            FROM user_sessions
            WHERE user_id = ?
              AND created_at >= ?
              AND created_at < ?
            ORDER BY created_at ASC
            """,
            (user_id, utc_start, utc_end),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        db.close()


def rebuild_sessions(user_id: int, sessions: list[dict]) -> None:
    if not sessions:
        print("⚠️  No sessions found for the requested window.")
        return

    for session in sessions:
        session_id = session["id"]
        created_at = session["created_at"]
        updated_at = session["updated_at"]
        name = session.get("name")
        editor_state = json.loads(session["editor_state_json"])
        first_line = editor_state.get("cells", [{}])[0].get("content", "").split("\n")[0]

        print("------------------------------------------------------------")
        print(f"🗂  Session ID:   {session_id}")
        print(f"📅  Created At:   {created_at}")
        print(f"🕒  Updated At:   {updated_at}")
        print(f"🏷️   Name:         {name or '(none)'}")
        print(f"📝  First Line:   {first_line or '(empty)'}")
        print("🔁 Rebuilding row through database.save_session()...")

        database.delete_session(user_id, session_id)
        database.save_session(
            user_id,
            session_id,
            editor_state,
            name=name,
            created_at=created_at,
        )
        print("✅ Recreated successfully.")


def main() -> None:
    args = parse_args()
    user_id = resolve_user_id(args.email, args.user_id)
    utc_start, utc_end = local_day_bounds(args.date, args.timezone)
    sessions = fetch_sessions(user_id, utc_start, utc_end)
    print(f"Found {len(sessions)} session(s) for user {user_id} between {utc_start} and {utc_end} UTC.")
    rebuild_sessions(user_id, sessions)


if __name__ == "__main__":
    main()
