from fastapi import FastAPI
from fastapi.testclient import TestClient

from evaluator.routes import plugins


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(plugins.router)
    return TestClient(app)


def test_get_default_plugin_rubric_returns_markdown():
    response = _client().get("/api/plugins/rubric")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["plugin"]["id"] == "zgc_ai_native_2026"
    assert payload["plugin"]["name"] == "ZGC AI-Native 2026"
    assert "评分规则" in payload["plugin"]["rubric"]


def test_get_explicit_plugin_rubric_returns_requested_plugin():
    response = _client().get("/api/plugins/rubric", params={"plugin_id": "zgc_ai_native_2026"})

    assert response.status_code == 200
    assert response.json()["plugin"]["id"] == "zgc_ai_native_2026"


def test_get_plugin_rubric_rejects_unknown_plugin():
    response = _client().get("/api/plugins/rubric", params={"plugin_id": "missing-plugin"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Plugin 'missing-plugin' not found"
