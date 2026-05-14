import subprocess
from pathlib import Path

from repos_runner.services import sandbox


class _DockerResult:
    def __init__(self, args, returncode=0, stdout="", stderr=""):
        self.args = args
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_docker_session_mounts_repo_and_execs_commands(monkeypatch, tmp_path):
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        if args[:2] == ["docker", "run"]:
            return _DockerResult(args, stdout="container-id\n")
        return _DockerResult(args, stdout="ok")

    monkeypatch.setenv("REPOS_RUNNER_EXECUTOR", "docker")
    monkeypatch.setattr(sandbox.shutil, "which", lambda name: "/usr/bin/docker" if name == "docker" else None)
    monkeypatch.setattr(sandbox.subprocess, "run", fake_run)

    with sandbox.create_execution_session(tmp_path) as session:
        result = session.run("pytest -v", cwd=tmp_path / "tests", timeout=30)

    run_args = calls[0][0]
    assert run_args[:4] == ["docker", "run", "-d", "--rm"]
    assert any(arg == f"{tmp_path}:/workspace" for arg in run_args)
    assert "--user" in run_args
    user_arg = run_args[run_args.index("--user") + 1]
    assert user_arg == f"{tmp_path.stat().st_uid}:{tmp_path.stat().st_gid}"
    assert "--network" in run_args
    assert "none" not in run_args

    exec_args = calls[1][0]
    assert exec_args[:3] == ["docker", "exec", "-i"]
    assert "/workspace/tests" in exec_args
    assert "-e" in exec_args
    assert "VIRTUAL_ENV=/opt/oscanner-venv" in exec_args
    assert "PATH=/opt/oscanner-venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" in exec_args
    assert "HOME=/tmp" in exec_args
    assert "PIP_CACHE_DIR=/tmp/pip-cache" in exec_args
    assert "PYTHONPATH=/opt/oscanner-venv/lib/python3.12/site-packages" in exec_args
    assert exec_args[-7:] == ["timeout", "-k", "5", "30", "/bin/sh", "-c", "pytest -v"]
    assert result.stdout == "ok"

    rm_args = calls[-1][0]
    assert rm_args[:3] == ["docker", "rm", "-f"]


def test_default_docker_image_includes_python_and_node(monkeypatch, tmp_path):
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return _DockerResult(args, stdout="container-id\n")

    monkeypatch.delenv("REPOS_RUNNER_DOCKER_IMAGE", raising=False)
    monkeypatch.setenv("REPOS_RUNNER_EXECUTOR", "docker")
    monkeypatch.setattr(sandbox.shutil, "which", lambda name: "/usr/bin/docker" if name == "docker" else None)
    monkeypatch.setattr(sandbox.subprocess, "run", fake_run)

    with sandbox.create_execution_session(tmp_path):
        pass

    run_args = calls[0][0]
    assert "oscanner-repos-runner:py3.12-node" in run_args


def test_docker_background_commands_use_container_python_env(monkeypatch, tmp_path):
    calls = []
    log_path = tmp_path / "runtime.log"

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        if args[:2] == ["docker", "run"]:
            return _DockerResult(args, stdout="container-id\n")
        return _DockerResult(args, stdout="ok")

    monkeypatch.setenv("REPOS_RUNNER_EXECUTOR", "docker")
    monkeypatch.setattr(sandbox.shutil, "which", lambda name: "/usr/bin/docker" if name == "docker" else None)
    monkeypatch.setattr(sandbox.subprocess, "run", fake_run)

    with sandbox.create_execution_session(tmp_path) as session:
        session.start_background(
            "python scripts/dev-app-backend.py",
            cwd=tmp_path,
            log_path=log_path,
            env={"PATH": "/host/bin", "HOME": "/home/ecs-user", "LANG": "C.UTF-8"},
        )

    exec_args = calls[1][0]
    shell_cmd = exec_args[-1]
    assert "PATH=/opt/oscanner-venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" in shell_cmd
    assert "HOME=/tmp" in shell_cmd
    assert "PYTHONPATH=/opt/oscanner-venv/lib/python3.12/site-packages" in shell_cmd
    assert "/host/bin" not in shell_cmd
    assert "/home/ecs-user" not in shell_cmd


def test_docker_session_timeout_raises_timeout_expired(monkeypatch, tmp_path):
    def fake_run(args, **kwargs):
        if args[:2] == ["docker", "run"]:
            return _DockerResult(args, stdout="container-id\n")
        raise subprocess.TimeoutExpired(args, kwargs.get("timeout") or 0)

    monkeypatch.setenv("REPOS_RUNNER_EXECUTOR", "docker")
    monkeypatch.setattr(sandbox.shutil, "which", lambda name: "/usr/bin/docker" if name == "docker" else None)
    monkeypatch.setattr(sandbox.subprocess, "run", fake_run)

    with sandbox.create_execution_session(tmp_path) as session:
        try:
            session.run("pytest -v", cwd=tmp_path, timeout=1)
        except subprocess.TimeoutExpired as error:
            assert "docker" in error.cmd
        else:
            raise AssertionError("expected TimeoutExpired")
