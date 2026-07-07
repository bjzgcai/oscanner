import pytest


def test_provider_quota_guard_reserves_and_rejects(tmp_path, monkeypatch):
    from evaluator.services import provider_quota_guard as guard

    monkeypatch.setenv("OSCANNER_PROVIDER_QUOTA_FILE", str(tmp_path / "quota.json"))
    monkeypatch.setenv("OSCANNER_GITHUB_REST_DAILY_BUDGET", "2")

    guard.reserve_provider_quota("github_rest")
    guard.reserve_provider_quota("github_rest")

    with pytest.raises(guard.ProviderQuotaExceeded, match="今日平台额度已用完"):
        guard.reserve_provider_quota("github_rest")

    snapshot = guard.snapshot_provider_quota()
    assert snapshot["usage"]["github_rest"] == {"used": 2, "budget": 2}


def test_provider_quota_guard_classifies_provider_urls():
    from evaluator.services import provider_quota_guard as guard

    assert guard._bucket_for_url("https://api.github.com/repos/o/r") == "github_rest"
    assert guard._bucket_for_url("https://api.github.com/graphql") == "github_graphql"
    assert guard._bucket_for_url("https://gitee.com/api/v5/repos/o/r") == "gitee"
    assert guard._bucket_for_url("https://example.com/api/v5/repos/o/r") is None


def test_provider_quota_guard_can_patch_requests(tmp_path, monkeypatch):
    import requests
    from evaluator.services import provider_quota_guard as guard

    monkeypatch.setenv("OSCANNER_PROVIDER_QUOTA_FILE", str(tmp_path / "quota.json"))
    monkeypatch.setenv("OSCANNER_GITEE_DAILY_REQUEST_BUDGET", "1")
    guard.install_provider_quota_guard()

    class DummyResponse:
        status_code = 200

    def fake_original(_self, _method, _url, **_kwargs):
        return DummyResponse()

    monkeypatch.setattr(guard, "_ORIGINAL_REQUESTS_REQUEST", fake_original)

    response = requests.Session().get("https://gitee.com/api/v5/repos/o/r")
    assert response.status_code == 200

    with pytest.raises(guard.ProviderQuotaExceeded):
        requests.Session().get("https://gitee.com/api/v5/repos/o/r")


@pytest.mark.anyio
async def test_provider_quota_status_endpoint(tmp_path, monkeypatch):
    from evaluator.routes.config import get_provider_quota_status
    from evaluator.services import provider_quota_guard as guard

    monkeypatch.setenv("OSCANNER_PROVIDER_QUOTA_FILE", str(tmp_path / "quota.json"))
    monkeypatch.setenv("OSCANNER_GITHUB_GRAPHQL_DAILY_POINT_BUDGET", "10")

    guard.reserve_provider_quota("github_graphql", cost=3)

    snapshot = await get_provider_quota_status()
    assert snapshot["usage"]["github_graphql"] == {"used": 3, "budget": 10}
