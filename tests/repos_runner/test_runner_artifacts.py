from fastapi import FastAPI
from fastapi.testclient import TestClient

from repos_runner.routes import runner


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(runner.router)
    return TestClient(app)


def test_runner_artifact_serves_runtime_screenshot(monkeypatch, tmp_path):
    repos_dir = tmp_path / "repos"
    screenshot = (
        repos_dir
        / "demo-repo"
        / "TEST_ARTIFACTS_class-01"
        / "runtime-evidence"
        / "screenshots"
        / "homepage.png"
    )
    screenshot.parent.mkdir(parents=True)
    screenshot.write_bytes(b"png")

    monkeypatch.setattr(runner, "get_repos_dir", lambda: repos_dir)

    client = _client()
    response = client.get(
        "/api/runner/artifact",
        params={
            "repo_url": "https://gitee.com/org/demo-repo",
            "path": "TEST_ARTIFACTS_class-01/runtime-evidence/screenshots/homepage.png",
        },
    )

    assert response.status_code == 200
    assert response.content == b"png"
    assert response.headers["content-type"] == "image/png"


def test_runner_artifact_serves_runtime_screenshot_by_repo_name(monkeypatch, tmp_path):
    repos_dir = tmp_path / "repos"
    screenshot = (
        repos_dir
        / "demo-repo"
        / "TEST_ARTIFACTS_class-01"
        / "runtime-evidence"
        / "screenshots"
        / "homepage.png"
    )
    screenshot.parent.mkdir(parents=True)
    screenshot.write_bytes(b"png")

    monkeypatch.setattr(runner, "get_repos_dir", lambda: repos_dir)

    client = _client()
    response = client.get(
        "/api/runner/artifact",
        params={
            "repo_name": "demo-repo",
            "path": "TEST_ARTIFACTS_class-01/runtime-evidence/screenshots/homepage.png",
        },
    )

    assert response.status_code == 200
    assert response.content == b"png"
    assert response.headers["content-type"] == "image/png"


def test_runner_artifact_rejects_paths_outside_test_artifacts(monkeypatch, tmp_path):
    repos_dir = tmp_path / "repos"
    secret = repos_dir / "demo-repo" / "README.md"
    secret.parent.mkdir(parents=True)
    secret.write_text("not public", encoding="utf-8")

    monkeypatch.setattr(runner, "get_repos_dir", lambda: repos_dir)

    client = _client()
    response = client.get(
        "/api/runner/artifact",
        params={
            "repo_url": "https://gitee.com/org/demo-repo",
            "path": "README.md",
        },
    )

    assert response.status_code == 404


def test_runner_artifact_rejects_path_traversal(monkeypatch, tmp_path):
    repos_dir = tmp_path / "repos"
    (repos_dir / "demo-repo").mkdir(parents=True)
    (repos_dir / "outside.png").write_bytes(b"png")

    monkeypatch.setattr(runner, "get_repos_dir", lambda: repos_dir)

    client = _client()
    response = client.get(
        "/api/runner/artifact",
        params={
            "repo_url": "https://gitee.com/org/demo-repo",
            "path": "../outside.png",
        },
    )

    assert response.status_code == 404
