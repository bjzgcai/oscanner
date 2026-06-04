import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_ai_native_plugin():
    scan_path = PROJECT_ROOT / "plugins" / "zgc_ai_native_2026" / "scan" / "__init__.py"
    spec = importlib.util.spec_from_file_location("test_zgc_ai_native_repo_snapshot", scan_path)
    plugin = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(plugin)
    return plugin


def _write_repo_file(data_dir: Path, rel_path: str, content: str):
    path = data_dir / "repo_files" / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_ai_native_plugin_loads_context_cone_from_repo_snapshot(tmp_path):
    plugin = _load_ai_native_plugin()
    data_dir = tmp_path / "data"
    _write_repo_file(data_dir, "web/App.tsx", "import { api } from './api'\napi()\n")
    _write_repo_file(data_dir, "web/api.ts", "export const api = () => null\n")
    _write_repo_file(data_dir, "web/unrelated.ts", "export const unused = true\n")
    _write_repo_file(data_dir, "package.json", '{"scripts":{"test":"vitest"}}\n')
    (data_dir / "repo_files_manifest.json").write_text("{}", encoding="utf-8")

    evaluator = plugin.create_commit_evaluator(
        data_dir=str(data_dir),
        api_key="test-key",
        model="deepseek/deepseek-v4-pro",
    )
    commits = [{"files": [{"filename": "web/App.tsx", "patch": "+api()"}]}]

    assert evaluator._load_context_files(commits) == {
        "package.json": '{"scripts":{"test":"vitest"}}\n',
        "web/App.tsx": "import { api } from './api'\napi()\n",
        "web/api.ts": "export const api = () => null\n",
    }


def test_ai_native_plugin_loads_java_context_cone_from_repo_snapshot(tmp_path):
    plugin = _load_ai_native_plugin()
    data_dir = tmp_path / "data"
    _write_repo_file(
        data_dir,
        "src/main/java/com/example/App.java",
        "package com.example;\nimport com.example.service.UserService;\nclass App {}\n",
    )
    _write_repo_file(
        data_dir,
        "src/main/java/com/example/service/UserService.java",
        "package com.example.service;\nclass UserService {}\n",
    )
    _write_repo_file(data_dir, "src/main/java/com/example/Unused.java", "class Unused {}\n")
    _write_repo_file(data_dir, "pom.xml", "<project />\n")
    (data_dir / "repo_files_manifest.json").write_text("{}", encoding="utf-8")

    evaluator = plugin.create_commit_evaluator(
        data_dir=str(data_dir),
        api_key="test-key",
        model="deepseek/deepseek-v4-pro",
    )
    commits = [{"files": [{"filename": "src/main/java/com/example/App.java", "patch": "+new UserService()"}]}]

    assert evaluator._load_context_files(commits) == {
        "pom.xml": "<project />\n",
        "src/main/java/com/example/App.java": (
            "package com.example;\nimport com.example.service.UserService;\nclass App {}\n"
        ),
        "src/main/java/com/example/service/UserService.java": (
            "package com.example.service;\nclass UserService {}\n"
        ),
    }

def test_ai_native_context_parts_keep_repo_files_inside_commit_background():
    plugin = _load_ai_native_plugin()
    evaluator = plugin.create_commit_evaluator(
        data_dir="",
        api_key="test-key",
        model="deepseek/deepseek-v4-pro",
    )
    commits = [
        {
            "sha": "def456",
            "commit": {"author": {"name": "Ada"}, "message": "improve deployment workflow"},
            "files": [{"filename": ".github/workflows/ci.yml", "patch": "+name: ci"}],
        }
    ]

    parts, _checker_raw_analysis = evaluator._build_context_parts(
        commits,
        "Ada",
        file_contents={"src/app.py": "print('background only')\n"},
        repo_structure={"files": ["src/app.py"]},
    )

    assert "file_contents" not in parts
    assert "repo_structure" not in parts
    assert "commits" in parts
    assert "BACKGROUND REPOSITORY FILES" in parts["commits"]
    assert "BACKGROUND REPO STRUCTURE" in parts["commits"]
    assert "COMMITS:" in parts["commits"]


def test_ai_native_merge_ignores_background_only_partial_scores():
    plugin = _load_ai_native_plugin()
    evaluator = plugin.create_commit_evaluator(
        data_dir="",
        api_key="test-key",
        model="deepseek/deepseek-v4-pro",
    )

    result = evaluator._merge_partial_evaluations(
        [
            {
                "_part_name": "commits",
                "spec_quality": 50,
                "cloud_architecture": 50,
                "ai_engineering": 50,
                "mastery_professionalism": 50,
                "reasoning": "commit evidence",
            },
            {
                "_part_name": "file_contents",
                "spec_quality": 100,
                "cloud_architecture": 100,
                "ai_engineering": 100,
                "mastery_professionalism": 100,
                "reasoning": "background-only repo snapshot",
            },
        ],
        "Ada",
    )

    assert result["spec_quality"] == 50
    assert result["cloud_architecture"] == 50
    assert result["ai_engineering"] == 50
    assert result["mastery_professionalism"] == 50
    assert "background-only repo snapshot" not in result["reasoning"]

def test_ai_native_forced_checker_skips_unscoped_whole_repo_scan(tmp_path, monkeypatch):
    plugin = _load_ai_native_plugin()
    data_dir = tmp_path / "data" / "github" / "owner" / "repo"
    data_dir.mkdir(parents=True)
    evaluator = plugin.create_commit_evaluator(
        data_dir=str(data_dir),
        api_key="test-key",
        model="deepseek/deepseek-v4-pro",
        forced_checker_id="ccn",
    )

    monkeypatch.setattr(evaluator, "_get_checker_list", lambda: [])

    def fail_run_checker(*_args, **_kwargs):
        raise AssertionError("forced checker must not scan the whole repo without changed Python files")

    monkeypatch.setattr(evaluator, "_run_checker", fail_run_checker)

    parts, _checker_raw_analysis = evaluator._build_context_parts(
        [
            {
                "sha": "abc123",
                "commit": {"message": "update docs"},
                "files": [{"filename": "README.md", "patch": "+docs"}],
            }
        ],
        "Ada",
        file_contents={},
        repo_structure=None,
    )

    assert "checker_results" not in parts
