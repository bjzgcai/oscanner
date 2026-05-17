import importlib.util
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_simple_plugin():
    scan_path = PROJECT_ROOT / "plugins" / "zgc_simple" / "scan" / "__init__.py"
    spec = importlib.util.spec_from_file_location("test_zgc_simple_repo_snapshot", scan_path)
    plugin = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(plugin)
    return plugin


def test_evaluator_prefers_complete_repo_snapshot_over_changed_files(tmp_path):
    plugin = _load_simple_plugin()
    data_dir = tmp_path / "data"
    (data_dir / "repo_files" / "src").mkdir(parents=True)
    (data_dir / "files" / "src").mkdir(parents=True)
    (data_dir / "repo_files" / "src" / "app.py").write_text("print('snapshot')\n", encoding="utf-8")
    (data_dir / "files" / "src" / "changed.py").write_text("print('changed')\n", encoding="utf-8")
    (data_dir / "repo_files_manifest.json").write_text(
        json.dumps({"end_sha": "end123", "included_files": [{"path": "src/app.py"}]}),
        encoding="utf-8",
    )

    evaluator = plugin.create_commit_evaluator(
        data_dir=str(data_dir),
        api_key="test-key",
        model="deepseek/deepseek-v4-pro",
    )
    commits = [{"files": [{"filename": "src/changed.py"}]}]

    assert evaluator._load_context_files(commits) == {"src/app.py": "print('snapshot')\n"}
