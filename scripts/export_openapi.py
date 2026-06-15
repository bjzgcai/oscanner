#!/usr/bin/env python3
"""Export checked-in OpenAPI specs for Oscanner services."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
OUT_DIR = ROOT / "docs" / "openapi"

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _operation_ids(spec: dict[str, Any]) -> list[str]:
    operation_ids: list[str] = []
    for path_item in spec.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if isinstance(operation, dict) and "operationId" in operation:
                operation_ids.append(str(operation["operationId"]))
    return operation_ids


def _assert_unique_operation_ids(service: str, spec: dict[str, Any]) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for operation_id in _operation_ids(spec):
        if operation_id in seen:
            duplicates.add(operation_id)
        seen.add(operation_id)
    if duplicates:
        duplicate_list = ", ".join(sorted(duplicates))
        raise RuntimeError(f"{service} OpenAPI has duplicate operationId values: {duplicate_list}")


def main() -> int:
    from evaluator.server import app as evaluator_app
    from repos_runner.server import app as runner_app

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    services = [
        ("evaluator", "evaluator.openapi.json", evaluator_app),
        ("repos_runner", "repos_runner.openapi.json", runner_app),
    ]

    for service, filename, app in services:
        spec = app.openapi()
        _assert_unique_operation_ids(service, spec)
        output_path = OUT_DIR / filename
        output_path.write_text(
            json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {output_path.relative_to(ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
