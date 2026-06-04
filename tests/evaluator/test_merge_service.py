"""Regression tests for plugin-coherent multi-identity merging."""

import pytest

from evaluator.services import merge_service


def _ai_native_eval(name: str, spec: int, cloud: int, ai: int, mastery: int, commits: int):
    return {
        "username": name,
        "total_commits_evaluated": commits,
        "scores": {
            "spec_quality": spec,
            "cloud_architecture": cloud,
            "ai_engineering": ai,
            "mastery_professionalism": mastery,
            "reasoning": f"{name} reasoning",
        },
        "commits_summary": {
            "total_additions": commits * 10,
            "total_deletions": commits,
            "files_changed": commits,
            "languages": ["Python"],
        },
    }


def test_merge_evaluations_preserves_ai_native_score_keys(monkeypatch):
    monkeypatch.setattr(merge_service, "get_llm_api_key", lambda: None)

    result = merge_service.merge_evaluations_logic(
        [
            {
                "author": "alice@example.com",
                "weight": 2,
                "evaluation": _ai_native_eval("alice@example.com", 80, 70, 60, 90, 2),
            },
            {
                "author": "alice@work.com",
                "weight": 1,
                "evaluation": _ai_native_eval("alice@work.com", 50, 40, 30, 60, 1),
            },
        ],
        model="test-model",
    )

    assert result["scores"]["spec_quality"] == 70.0
    assert result["scores"]["cloud_architecture"] == 60.0
    assert result["scores"]["ai_engineering"] == 50.0
    assert result["scores"]["mastery_professionalism"] == 80.0
    assert "ai_fullstack" not in result["scores"]
    assert result["total_commits_analyzed"] == 3


def test_merge_evaluations_uses_configured_chat_completions_url(monkeypatch):
    captured = {}

    class FakeResponse:
        ok = True

        @staticmethod
        def json():
            return {"choices": [{"message": {"content": "merged reasoning"}}]}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs.get("json")
        return FakeResponse()

    monkeypatch.setenv("OSCANNER_LLM_CHAT_COMPLETIONS_URL", "https://llm.example/v1/chat/completions")
    monkeypatch.setattr(merge_service, "get_llm_api_key", lambda: "fake-key")
    monkeypatch.setattr(merge_service.requests, "post", fake_post)

    result = merge_service.merge_evaluations_logic(
        [
            {
                "author": "alice@example.com",
                "weight": 1,
                "evaluation": _ai_native_eval("alice@example.com", 80, 70, 60, 90, 1),
            },
            {
                "author": "alice@work.com",
                "weight": 1,
                "evaluation": _ai_native_eval("alice@work.com", 60, 50, 40, 70, 1),
            },
        ],
        model="custom-model",
    )

    assert captured["url"] == "https://llm.example/v1/chat/completions"
    assert captured["json"]["model"] == "custom-model"
    assert result["scores"]["reasoning"] == "merged reasoning"


def test_merge_rejects_zero_email_weights(monkeypatch):
    monkeypatch.setattr(merge_service, "get_llm_api_key", lambda: None)

    with pytest.raises(Exception) as exc_info:
        merge_service.merge_evaluations_logic(
            [
                {"author": "alice@example.com", "weight": 0, "evaluation": _ai_native_eval("a", 1, 1, 1, 1, 0)},
                {"author": "alice@work.com", "weight": 0, "evaluation": _ai_native_eval("b", 1, 1, 1, 1, 0)},
            ]
        )

    assert "Total weight cannot be zero" in str(exc_info.value)
