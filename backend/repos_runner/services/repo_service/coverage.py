"""
Tag-based feature analysis and test coverage checking.
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, List

from .llm import _messages_create_with_fallback


async def _extract_features_from_tag_message(message: str) -> List[str]:
    """Use LLM to extract a list of distinct testable features from a tag annotation message."""
    try:
        prompt = f"""Extract the list of specific testable features from this tag annotation message.

Tag message: "{message}"

Return ONLY a JSON array of feature names (strings), e.g.:
["Create", "Read", "Update", "Delete"]

Rules:
- Each feature should be a distinct, testable capability mentioned in the message.
- If the message mentions "CRUD", expand it to ["Create", "Read", "Update", "Delete"].
- Keep feature names concise (1-4 words).
- Only include features explicitly mentioned or clearly implied by the message.
"""
        result = _messages_create_with_fallback(
            model="anthropic/claude-sonnet-4.6",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = result.content[0].text.strip()
        json_match = re.search(r'\[.*\]', text, re.DOTALL)
        if json_match:
            features = json.loads(json_match.group())
            if isinstance(features, list) and features:
                return [str(f) for f in features]
    except Exception:
        pass
    return []


async def _check_feature_coverage(clone_dir: Path, features: List[str]) -> Dict[str, Any]:
    """
    Analyze test files in the repo to determine which required features are covered.

    Returns:
        {
            "covered": [...],          # features with tests
            "not_covered": [...],      # features missing tests
            "coverage_ratio": float,   # covered / total
            "test_files_found": [...], # relative paths of test files scanned
        }
    """
    # Collect test files — skip venvs, caches, and hidden/generated dirs
    _SKIP_DIRS = {
        ".venv", "venv", "env", "__pycache__", ".git", ".tox", ".eggs",
        "node_modules", "dist", "build", "coverage", ".next", ".nuxt",
        "target", "vendor", ".bundle", ".gradle", "out", "_build", "deps",
        "site-packages", "dist-packages",
    }

    def _is_skipped(path: Path) -> bool:
        for part in path.relative_to(clone_dir).parts:
            if (
                part in _SKIP_DIRS
                or part.startswith(".venv")
                or part.startswith("venv")
                or "site-packages" in part
                or (part.startswith(".") and part != ".")
            ):
                return True
        return False

    test_patterns = [
        "test_*.py", "*_test.py",
        "*.test.js", "*.spec.js",
        "*.test.ts", "*.spec.ts",
        "*.test.jsx", "*.spec.jsx",
        "*.test.tsx", "*.spec.tsx",
        "*_test.go", "test_*.go",
        "*_test.rs",
        "*Test.java", "*Tests.java",
        "*_spec.rb", "*_test.rb",
        "*Test.php",
    ]
    seen: set = set()
    test_files: List[Path] = []
    for pattern in test_patterns:
        for p in clone_dir.rglob(pattern):
            if p not in seen and not _is_skipped(p):
                seen.add(p)
                test_files.append(p)

    # Prioritize files in standard project test directories so they appear
    # first and are not displaced by stray matches from dependencies.
    _PROJECT_TEST_DIRS = {"tests", "test", "__tests__", "spec"}

    def _is_project_test(p: Path) -> bool:
        parts = p.relative_to(clone_dir).parts
        return bool(parts) and parts[0] in _PROJECT_TEST_DIRS

    test_files.sort(key=lambda p: (0 if _is_project_test(p) else 1))

    if not test_files:
        for test_dir_name in ["tests", "test", "__tests__", "spec"]:
            test_dir = clone_dir / test_dir_name
            if test_dir.exists():
                for f in test_dir.rglob("*"):
                    if f.is_file() and f.suffix in {".py", ".js", ".ts", ".go", ".rs", ".java", ".rb", ".php"} and not _is_skipped(f):
                        test_files.append(f)

    if not test_files:
        return {
            "covered": [],
            "not_covered": list(features),
            "coverage_ratio": 0.0,
            "test_files_found": [],
        }

    # Extract test class and method names from test files (compact, avoids truncation)
    test_content_parts = []
    for f in test_files[:30]:
        try:
            content = f.read_text(errors="ignore")
            names = re.findall(r'(?:class|def)\s+(test\w*|Test\w*)', content, re.IGNORECASE)
            if names:
                test_content_parts.append(f"--- {f.name} ---\n" + "\n".join(names))
            else:
                # Fallback: include raw content for small files
                test_content_parts.append(f"--- {f.name} ---\n{content[:3000]}")
        except Exception:
            pass
    test_content = "\n\n".join(test_content_parts)[:20000]

    prompt = f"""You are analyzing test names to check which features are actually tested.

Required features: {json.dumps(features)}

Test class and method names found in the repository:
{test_content}

Determine which of the required features have dedicated test cases based on the test names above.
A feature is "covered" if there are test classes or methods whose names clearly relate to that feature.

Return ONLY a JSON object:
{{
  "covered": ["feature1", "feature2"],
  "not_covered": ["feature3"]
}}

Use only feature names from the required features list.
"""
    try:
        result = _messages_create_with_fallback(
            model="anthropic/claude-sonnet-4.6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        text = result.content[0].text.strip()
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            coverage = json.loads(json_match.group())
            covered = coverage.get("covered", [])
            not_covered = coverage.get("not_covered", [])
            coverage_ratio = len(covered) / len(features) if features else 1.0
            return {
                "covered": covered,
                "not_covered": not_covered,
                "coverage_ratio": coverage_ratio,
                "test_files_found": [str(f.relative_to(clone_dir)) for f in test_files],
            }
    except Exception:
        pass

    # LLM failed — assume all covered to avoid false penalty
    return {
        "covered": list(features),
        "not_covered": [],
        "coverage_ratio": 1.0,
        "test_files_found": [str(f.relative_to(clone_dir)) for f in test_files],
    }
