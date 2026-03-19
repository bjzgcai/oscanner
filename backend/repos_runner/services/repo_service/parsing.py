"""
Structured test-output parsing (JSON reports, regex, LLM fallback).
"""

import json
import re
from pathlib import Path
from typing import Optional, Dict, Any

from .llm import _default_requested_model, _message_text_content, _messages_create_with_fallback


def _parse_json_report(clone_dir: Path) -> Optional[Dict[str, Any]]:
    """
    Parse .test_report.json written by pytest-json-report or jest --json.
    Returns a dict with 'passed', 'failed', 'total', 'test_cases' or None.
    """
    report_path = clone_dir / ".test_report.json"
    if not report_path.exists():
        return None

    try:
        data = json.loads(report_path.read_text())
    except Exception:
        return None

    # pytest-json-report format
    if "summary" in data and "tests" in data:
        summary = data["summary"]
        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0) + summary.get("error", 0)
        total = summary.get("total", passed + failed)

        test_cases = []
        for t in data.get("tests", []):
            outcome = t.get("outcome", "unknown")
            test_cases.append({
                "name": t.get("nodeid", t.get("name", "unknown")),
                "status": "passed" if outcome == "passed" else "failed",
                "duration": t.get("duration", 0),
                "output": t.get("call", {}).get("longrepr", "") if outcome != "passed" else "",
            })
        return {"passed": passed, "failed": failed, "total": total, "test_cases": test_cases}

    # jest --json format
    if "numPassedTests" in data:
        passed = data.get("numPassedTests", 0)
        failed = data.get("numFailedTests", 0)
        total = data.get("numTotalTests", passed + failed)

        test_cases = []
        for suite in data.get("testResults", []):
            for t in suite.get("testResults", []):
                status_raw = t.get("status", "unknown")
                test_cases.append({
                    "name": " > ".join(t.get("ancestorTitles", [])) + " > " + t.get("title", ""),
                    "status": "passed" if status_raw == "passed" else "failed",
                    "duration": t.get("duration", 0) / 1000.0,  # ms → s
                    "output": "\n".join(t.get("failureMessages", [])),
                })
        return {"passed": passed, "failed": failed, "total": total, "test_cases": test_cases}

    # Go test JSON format (one JSON object per line)
    if "Action" in data:
        # Single line parsed as object; re-read the file line by line
        return _parse_go_json_report(report_path)

    return None


def _parse_go_json_report(report_path: Path) -> Optional[Dict[str, Any]]:
    """Parse Go test JSON output (one JSON object per line)."""
    try:
        lines = report_path.read_text().splitlines()
        passed = 0
        failed = 0
        test_cases = []

        for line in lines:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            action = obj.get("Action", "")
            test = obj.get("Test", "")
            if not test:
                continue
            if action == "pass":
                passed += 1
                test_cases.append({
                    "name": test,
                    "status": "passed",
                    "duration": obj.get("Elapsed", 0),
                    "output": "",
                })
            elif action == "fail":
                failed += 1
                test_cases.append({
                    "name": test,
                    "status": "failed",
                    "duration": obj.get("Elapsed", 0),
                    "output": "",
                })

        total = passed + failed
        if total == 0:
            return None
        return {"passed": passed, "failed": failed, "total": total, "test_cases": test_cases}
    except Exception:
        return None


def _parse_test_output_with_regex(output: str) -> Optional[Dict[str, int]]:
    """Fast-path regex parsing for common test framework stdout."""

    # pytest: "9 failed, 9 passed"
    m = re.search(r"=+\s*(\d+)\s+failed,\s+(\d+)\s+passed", output)
    if m:
        failed, passed = int(m.group(1)), int(m.group(2))
        return {"passed": passed, "failed": failed, "total": passed + failed}

    # pytest: "9 passed"
    m = re.search(r"=+\s*(\d+)\s+passed", output)
    if m:
        passed = int(m.group(1))
        return {"passed": passed, "failed": 0, "total": passed}

    # Jest: "Tests:  9 failed, 9 passed, 18 total"
    m = re.search(r"Tests:\s+(\d+)\s+failed,\s+(\d+)\s+passed,\s+(\d+)\s+total", output)
    if m:
        return {"failed": int(m.group(1)), "passed": int(m.group(2)), "total": int(m.group(3))}

    # Jest all-passed: "Tests:  9 passed, 9 total"
    m = re.search(r"Tests:\s+(\d+)\s+passed,\s+(\d+)\s+total", output)
    if m:
        passed, total = int(m.group(1)), int(m.group(2))
        return {"passed": passed, "failed": total - passed, "total": total}

    # Go: "ok" / "FAIL" summary lines
    ok_count = len(re.findall(r"^ok\s+", output, re.MULTILINE))
    fail_count = len(re.findall(r"^FAIL\s+", output, re.MULTILINE))
    if ok_count + fail_count > 0:
        return {"passed": ok_count, "failed": fail_count, "total": ok_count + fail_count}

    # cargo test: "test result: ok. N passed; N failed"
    m = re.search(r"test result:.*?(\d+)\s+passed;\s+(\d+)\s+failed", output)
    if m:
        passed, failed = int(m.group(1)), int(m.group(2))
        return {"passed": passed, "failed": failed, "total": passed + failed}

    # Maven surefire: "Tests run: N, Failures: N, Errors: N"
    m = re.search(r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+)", output)
    if m:
        total, failures, errors = int(m.group(1)), int(m.group(2)), int(m.group(3))
        failed = failures + errors
        return {"passed": total - failed, "failed": failed, "total": total}

    # RSpec: "N examples, N failures"
    m = re.search(r"(\d+)\s+examples?,\s*(\d+)\s+failures?", output)
    if m:
        total, failed = int(m.group(1)), int(m.group(2))
        return {"passed": total - failed, "failed": failed, "total": total}

    return None


async def _parse_test_output_with_llm(output: str) -> Optional[Dict[str, int]]:
    """LLM fallback for unknown test frameworks."""
    try:
        truncated = output[-2000:] if len(output) > 2000 else output

        prompt = f"""Parse this test output and extract the test results.

Test output:
```
{truncated}
```

Return ONLY a JSON object (no other text):
{{
  "passed": <number>,
  "failed": <number>,
  "total": <number>
}}

If you cannot determine the counts, return: {{"passed": 0, "failed": 0, "total": 0}}
"""
        message = _messages_create_with_fallback(
            model=_default_requested_model(),
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = _message_text_content(message)
        json_match = re.search(r"\{[^}]+\}", response_text)
        if json_match:
            result = json.loads(json_match.group())
            if all(k in result for k in ["passed", "failed", "total"]):
                if result["total"] > 0 and result["passed"] + result["failed"] == result["total"]:
                    return result
    except Exception:
        pass
    return None


async def _parse_test_output(output: str) -> Optional[Dict[str, int]]:
    result = _parse_test_output_with_regex(output)
    if result:
        return result
    return await _parse_test_output_with_llm(output)
