import os
import subprocess
from pathlib import Path


def _copy_script(project_root: Path, test_root: Path, script_name: str) -> Path:
    scripts_dir = test_root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    script_path = scripts_dir / script_name
    script_path.write_text(
        (project_root / "scripts" / script_name).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    script_path.chmod(0o755)
    return script_path


def test_start_dev_print_config_reads_dotenv_files(tmp_path):
    project_root = Path(__file__).resolve().parents[2]
    test_root = tmp_path / "oscanner"
    evaluator_dir = test_root / "backend" / "evaluator"
    runner_dir = test_root / "backend" / "repos_runner"
    webapp_dir = test_root / "frontend" / "webapp"
    evaluator_dir.mkdir(parents=True)
    runner_dir.mkdir(parents=True)
    webapp_dir.mkdir(parents=True)
    script_path = _copy_script(project_root, test_root, "start_dev.sh")

    (evaluator_dir / ".env").write_text("PORT=8100\n", encoding="utf-8")
    (runner_dir / ".env").write_text("RUNNER_PORT=8101\n", encoding="utf-8")
    (webapp_dir / ".env.local").write_text("PORT=3100\n", encoding="utf-8")

    env = os.environ.copy()
    env["OSCANNER_START_DEV_PRINT_CONFIG"] = "1"
    result = subprocess.run(
        [str(script_path)],
        check=True,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )

    assert "EVALUATOR_PORT=8100" in result.stdout
    assert "RUNNER_PORT=8101" in result.stdout
    assert "WEBAPP_PORT=3100" in result.stdout
    assert "NEXT_PUBLIC_API_SERVER_URL=http://localhost:8100" in result.stdout
    assert "NEXT_PUBLIC_RUNNER_SERVER_URL=http://localhost:8101" in result.stdout


def test_start_dev_waits_for_backend_health_checks():
    project_root = Path(__file__).resolve().parents[2]
    script = (project_root / "scripts" / "start_dev.sh").read_text(encoding="utf-8")

    assert "wait_for_health" in script
    assert "/health" in script
    assert "http://127.0.0.1:${RUNNER_PORT}/health" in script


def test_stop_dev_uses_repo_root_for_env_files():
    project_root = Path(__file__).resolve().parents[2]
    script = (project_root / "scripts" / "stop_dev.sh").read_text(encoding="utf-8")

    assert 'PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"' in script
