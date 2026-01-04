#!/usr/bin/env python3
"""
Standalone dry-run tester for daily picture generation.

Usage:
  python backend/tests/picture_dry_run.py --token TOKEN [--base-url http://127.0.0.1:8765] [--date YYYY-MM-DD] [--notes "smoke"]

Does not write to DB (uses dry_run=true). Exits non-zero on failure.
"""

import argparse
import json
import sys
import urllib.request
import urllib.error


def main():
    parser = argparse.ArgumentParser(description="Dry-run picture generation (no DB write).")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765", help="Backend base URL")
    parser.add_argument("--token", required=True, help="Bearer token for auth")
    parser.add_argument("--date", dest="target_date", help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument("--notes", dest="notes_override", default="smoke test", help="Override notes text for generation")
    parser.add_argument("--timeout", type=int, default=90, help="Request timeout seconds")
    args = parser.parse_args()

    url = f"{args.base_url.rstrip('/')}/api/pictures/generate"
    payload = {
        "target_date": args.target_date,
        "notes_override": args.notes_override,
        "dry_run": True,
        "skip_if_exists": False,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {args.token}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=args.timeout) as resp:
            body = resp.read().decode("utf-8")
            result = json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        sys.stderr.write(f"HTTP error: {e.code} {e.reason}\n")
        if body:
            sys.stderr.write(f"Body: {body}\n")
        sys.exit(1)
    except Exception as e:
        sys.stderr.write(f"Request failed: {e}\n")
        sys.exit(1)

    image_b64 = result.get("image_base64")
    if not image_b64:
        sys.stderr.write(f"No image_base64 in response: {result}\n")
        sys.exit(1)

    thumb_len = len(result.get("thumbnail_base64") or image_b64)
    prompt = (result.get("prompt") or "").strip()
    print(f"✅ Dry-run generated image (base64 length: {len(image_b64)}, thumb length: {thumb_len})")
    if prompt:
        print(f"Prompt: {prompt[:120]}{'...' if len(prompt) > 120 else ''}")


if __name__ == "__main__":
    main()
