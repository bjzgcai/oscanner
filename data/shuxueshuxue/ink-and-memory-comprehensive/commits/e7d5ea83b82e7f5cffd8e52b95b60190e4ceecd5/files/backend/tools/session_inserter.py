#!/usr/bin/env python3
"""
Create synthetic sessions for a specific user/day.

Useful for timezone sanity checks and regression testing.
"""

from __future__ import annotations

import argparse
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Insert a session for a specific user/day.")
    parser.add_argument("--email", help="User email (alternative to --user-id)")
    parser.add_argument("--user-id", type=int, help="User ID (alternative to --email)")
    parser.add_argument("--date", required=True, help="Local date in YYYY-MM-DD")
    parser.add_argument("--time", default="09:00", help="Local time in HH:MM (default 09:00)")
    parser.add_argument("--timezone", default="UTC", help="IANA timezone name (default UTC)")
    parser.add_argument("--title", help="Optional session title")
    parser.add_argument("--text", default="", help="Optional text content for the first text cell")
    parser.add_argument("--session-id", help="Optional explicit session id (default random UUID)")
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


def local_timestamp(date: str, time_str: str, tz_name: str) -> tuple[str, str]:
    tz = ZoneInfo(tz_name)
    local_dt = datetime.strptime(f"{date} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
    utc_dt = local_dt.astimezone(timezone.utc)
    created_at_db = utc_dt.strftime("%Y-%m-%d %H:%M:%S")
    created_at_state = utc_dt.isoformat().replace("+00:00", "Z")
    return created_at_db, created_at_state


def build_editor_state(session_id: str, text: str, created_at_iso: str) -> dict:
    text_cell_id = uuid.uuid4().hex[:12]
    return {
        "cells": [
            {"id": text_cell_id, "type": "text", "content": text}
        ],
        "commentors": [],
        "tasks": [],
        "weightPath": [],
        "overlappedPhrases": [],
        "sessionId": session_id,
        "currentEntryId": session_id,
        "selectedState": None,
        "createdAt": created_at_iso
    }


def main() -> None:
    args = parse_args()
    user_id = resolve_user_id(args.email, args.user_id)
    created_at_db, created_at_state = local_timestamp(args.date, args.time, args.timezone)
    session_id = args.session_id or str(uuid.uuid4())
    text_content = args.text.strip()
    title = args.title or (text_content.splitlines()[0][:60] if text_content else f"Session {args.date}")

    editor_state = build_editor_state(session_id, text_content, created_at_state)
    database.save_session(
        user_id,
        session_id,
        editor_state,
        name=title,
        created_at=created_at_db,
    )
    print(f"✅ Inserted session {session_id} for user {user_id} at {created_at_db} UTC.")


if __name__ == "__main__":
    main()
