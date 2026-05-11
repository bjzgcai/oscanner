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
    assert "--network" in run_args
    assert "none" not in run_args

    exec_args = calls[1][0]
    assert exec_args[:3] == ["docker", "exec", "-i"]
    assert "/workspace/tests" in exec_args
    assert exec_args[-3:] == ["/bin/sh", "-lc", "pytest -v"]
    assert result.stdout == "ok"

    rm_args = calls[-1][0]
    assert rm_args[:3] == ["docker", "rm", "-f"]


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
