import json
import os
import subprocess
import sys
from pathlib import Path


def test_server_loads_explicit_runner_env_before_queue_initializes(tmp_path):
    env_file = tmp_path / ".env.prod"
    env_file.write_text(
        "REPOS_RUNNER_MAX_CONCURRENT_JOBS=3\n"
        "REPOS_RUNNER_MAX_PENDING_JOBS=7\n",
        encoding="utf-8",
    )

    project_root = Path(__file__).resolve().parents[2]
    backend_dir = project_root / "backend"
    env = os.environ.copy()
    env["REPOS_RUNNER_ENV_FILE"] = str(env_file)
    env["PYTHONPATH"] = f"{project_root}:{backend_dir}:{env.get('PYTHONPATH', '')}"

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json; "
                "import repos_runner.server; "
                "from repos_runner.routes import runner; "
                "print(json.dumps(runner.runner_queue.snapshot()))"
            ),
        ],
        check=True,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )

    assert json.loads(result.stdout.strip().splitlines()[-1]) == {
        "max_concurrent": 3,
        "running": 0,
        "pending": 0,
        "max_pending": 7,
    }
