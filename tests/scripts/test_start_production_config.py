import os
import subprocess
from pathlib import Path


def test_repos_runner_port_does_not_inherit_evaluator_port(tmp_path):
    project_root = Path(__file__).resolve().parents[2]
    test_root = tmp_path / "oscanner"
    scripts_dir = test_root / "scripts"
    evaluator_dir = test_root / "backend" / "evaluator"
    runner_dir = test_root / "backend" / "repos_runner"
    webapp_dir = test_root / "frontend" / "webapp"
    scripts_dir.mkdir(parents=True)
    evaluator_dir.mkdir(parents=True)
    runner_dir.mkdir(parents=True)
    webapp_dir.mkdir(parents=True)

    script_path = scripts_dir / "start_production.sh"
    script_path.write_text(
        (project_root / "scripts" / "start_production.sh").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    script_path.chmod(0o755)

    (evaluator_dir / ".env.local").write_text("PORT=8000\n", encoding="utf-8")
    (runner_dir / ".env.prod").write_text(
        "REPOS_RUNNER_MAX_CONCURRENT_JOBS=1\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["OSCANNER_START_PRODUCTION_PRINT_CONFIG"] = "1"
    result = subprocess.run(
        [str(script_path), "--daemon"],
        check=True,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )

    assert "EVALUATOR_PORT=8000" in result.stdout
    assert "REPOS_RUNNER_PORT=8001" in result.stdout
    assert "WEBAPP_PORT=3000" in result.stdout


def test_start_production_exposes_oscanner_home_from_env(tmp_path):
    project_root = Path(__file__).resolve().parents[2]
    test_root = tmp_path / "oscanner"
    scripts_dir = test_root / "scripts"
    evaluator_dir = test_root / "backend" / "evaluator"
    runner_dir = test_root / "backend" / "repos_runner"
    webapp_dir = test_root / "frontend" / "webapp"
    scripts_dir.mkdir(parents=True)
    evaluator_dir.mkdir(parents=True)
    runner_dir.mkdir(parents=True)
    webapp_dir.mkdir(parents=True)

    script_path = scripts_dir / "start_production.sh"
    script_path.write_text(
        (project_root / "scripts" / "start_production.sh").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    script_path.chmod(0o755)

    oscanner_home = tmp_path / "oscanner-home"
    (evaluator_dir / ".env.local").write_text(
        f"PORT=8000\nOSCANNER_HOME={oscanner_home}\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["OSCANNER_START_PRODUCTION_PRINT_CONFIG"] = "1"
    result = subprocess.run(
        [str(script_path), "--daemon"],
        check=True,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )

    assert f"OSCANNER_HOME={oscanner_home}" in result.stdout
