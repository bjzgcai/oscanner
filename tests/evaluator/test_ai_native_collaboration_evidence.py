import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_ai_native_plugin():
    scan_path = PROJECT_ROOT / "plugins" / "zgc_ai_native_2026" / "scan" / "__init__.py"
    spec = importlib.util.spec_from_file_location("test_zgc_ai_native_2026_collaboration", scan_path)
    plugin = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(plugin)
    return plugin


def test_ai_native_adds_collaboration_evidence_block_into_mastery_professionalism(monkeypatch):
    plugin = _load_ai_native_plugin()
    evaluator = plugin.create_commit_evaluator(
        data_dir="",
        api_key="test-key",
        model="deepseek/deepseek-v4-pro",
        language="en-US",
    )
    monkeypatch.setattr(evaluator, "_get_checker_list", lambda: [])

    commits = [
        {
            "sha": "abc123456789",
            "commit": {
                "author": {"name": "Ada"},
                "message": "docs: document migration plan and review checklist (#42)",
            },
            "files": [
                {"filename": "docs/adr/api-migration.md", "patch": "+review checklist"},
                {"filename": "CHANGELOG.md", "patch": "+migration notes"},
            ],
        },
        {
            "sha": "def987654321",
            "commit": {
                "author": {"name": "Ada"},
                "message": "test: add contract coverage for shared API",
            },
            "files": [
                {"filename": "tests/api/test_contracts.py", "patch": "+def test_contract()"},
                {"filename": "backend/api/schema.py", "patch": "+class SharedSchema"},
            ],
        },
        {
            "sha": "fed555555555",
            "commit": {
                "author": {"name": "Ada"},
                "message": "ci: add lint workflow and contributing guide",
            },
            "files": [
                {"filename": ".github/workflows/ci.yml", "patch": "+name: ci"},
                {"filename": "CONTRIBUTING.md", "patch": "+How to contribute"},
            ],
        },
    ]

    parts, _checker_raw_analysis = evaluator._build_context_parts(
        commits,
        "Ada",
        file_contents={},
        repo_structure={"files": ["backend/api/schema.py", "docs/adr/api-migration.md"]},
    )

    commits_context = parts["commits"]
    assert "COLLABORATION EVIDENCE (mastery_professionalism subscore)" in commits_context
    assert "Subscore:" in commits_context
    assert "reviewable commits" in commits_context
    assert "handoff artifacts" in commits_context
    assert "team hygiene" in commits_context

    merged = evaluator._merge_partial_evaluations(
        [
            {
                "_part_name": "commits",
                "spec_quality": 70,
                "cloud_architecture": 60,
                "ai_engineering": 50,
                "mastery_professionalism": 75,
                "reasoning": "Engineering Mastery & Professionalism: good team practice.",
            }
        ],
        "Ada",
    )

    assert "mastery_professionalism_collaboration" not in merged
    assert merged["mastery_professionalism"] == 72
    reasoning = merged["reasoning"]
    mastery_section = reasoning.split("## Engineering Mastery & Professionalism", 1)[1]
    assert "Collaboration Evidence:" in mastery_section
    assert "Subscore:" in mastery_section
