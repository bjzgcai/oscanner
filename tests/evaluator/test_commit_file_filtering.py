import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from evaluator.utils.data_loader import load_commits_from_local  # noqa: E402


def test_load_commits_from_local_excludes_dependency_directories(tmp_path):
    data_dir = tmp_path / "data" / "gitee" / "owner" / "repo"
    commits_dir = data_dir / "commits"
    commits_dir.mkdir(parents=True)

    (data_dir / "commits_index.json").write_text(
        json.dumps([{"sha": "abc123"}]),
        encoding="utf-8",
    )
    (commits_dir / "abc123.json").write_text(
        json.dumps(
            {
                "sha": "abc123",
                "stats": {"additions": 1010, "deletions": 205, "total": 1215},
                "files": [
                    {
                        "filename": "src/app.py",
                        "additions": 10,
                        "deletions": 5,
                        "patch": "+print('real code')",
                    },
                    {
                        "filename": "frontend/node_modules/react/index.js",
                        "additions": 1000,
                        "deletions": 200,
                        "patch": "+dependency code",
                    },
                    {
                        "filename": "backend/venv/lib/python3.11/site-packages/pkg.py",
                        "additions": 50,
                        "deletions": 25,
                        "patch": "+installed package",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    commits = load_commits_from_local(data_dir)

    assert len(commits) == 1
    assert [f["filename"] for f in commits[0]["files"]] == ["src/app.py"]
    assert commits[0]["stats"] == {"additions": 10, "deletions": 5, "total": 15}


def test_load_commits_from_local_excludes_binary_generated_and_noise_files(tmp_path):
    data_dir = tmp_path / "data" / "gitee" / "owner" / "repo"
    commits_dir = data_dir / "commits"
    commits_dir.mkdir(parents=True)

    (data_dir / "commits_index.json").write_text(
        json.dumps([{"sha": "def456"}]),
        encoding="utf-8",
    )
    (commits_dir / "def456.json").write_text(
        json.dumps(
            {
                "sha": "def456",
                "stats": {"additions": 1293, "deletions": 276, "total": 1569},
                "files": [
                    {"filename": "src/app.py", "additions": 12, "deletions": 2},
                    {"filename": "README.md", "additions": 8, "deletions": 1},
                    {"filename": "Dockerfile", "additions": 6, "deletions": 0},
                    {"filename": "package-lock.json", "additions": 500, "deletions": 200},
                    {"filename": "docs/architecture.md", "additions": 20, "deletions": 3},
                    {"filename": "assets/logo.png", "additions": 200, "deletions": 0},
                    {"filename": "public/demo.mp4", "additions": 300, "deletions": 0},
                    {"filename": "frontend/dist/app.js", "additions": 150, "deletions": 50},
                    {"filename": "debug.log", "additions": 90, "deletions": 20},
                    {"filename": ".DS_Store", "additions": 7, "deletions": 0},
                ],
            }
        ),
        encoding="utf-8",
    )

    commits = load_commits_from_local(data_dir)

    assert [f["filename"] for f in commits[0]["files"]] == [
        "src/app.py",
        "README.md",
        "Dockerfile",
        "package-lock.json",
        "docs/architecture.md",
    ]
    assert commits[0]["stats"] == {"additions": 546, "deletions": 206, "total": 752}
