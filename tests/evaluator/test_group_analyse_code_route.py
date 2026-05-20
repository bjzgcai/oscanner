"""Tests for courses-style group repository evaluation."""

import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.responses import StreamingResponse


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _load_scan_plugin(plugin_id: str, module_name: str):
    scan_path = PROJECT_ROOT / "plugins" / plugin_id / "scan" / "__init__.py"
    spec = importlib.util.spec_from_file_location(module_name, scan_path)
    plugin = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(plugin)
    return plugin


class _FakeInvalidLlmResponse:
    is_success = True
    status_code = 200
    text = "ok"

    def json(self):
        return {"choices": [{"message": {"content": "still not json"}}]}


class _FakeValidRetryResponse:
    is_success = True
    status_code = 200
    text = "ok"

    def __init__(self, content: str):
        self._content = content

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


@pytest.mark.parametrize(
    ("plugin_id", "valid_content", "expected_key"),
    [
        (
            "zgc_simple",
            '{"ai_fullstack":81,"ai_architecture":82,"cloud_native":83,'
            '"open_source":84,"intelligent_dev":85,"leadership":86,"reasoning":"fixed"}',
            "ai_fullstack",
        ),
        (
            "zgc_ai_native_2026",
            '{"spec_quality":81,"cloud_architecture":82,'
            '"ai_engineering":83,"mastery_professionalism":84,"reasoning":"fixed"}',
            "spec_quality",
        ),
    ],
)
def test_plugin_parse_retry_returns_valid_retry_response(
    monkeypatch,
    plugin_id,
    valid_content,
    expected_key,
):
    plugin = _load_scan_plugin(plugin_id, f"test_{plugin_id}_parse_retry_success")
    evaluator = plugin.create_commit_evaluator(data_dir="", api_key="test-key", model="test-model")

    retry_calls = []

    def fake_post(*_args, **_kwargs):
        retry_calls.append(True)
        return _FakeValidRetryResponse(valid_content)

    monkeypatch.setattr(evaluator._http_client, "post", fake_post)

    result = evaluator._parse_llm_response_with_retry("not json", "original prompt", "test-model")

    assert len(retry_calls) == 1
    assert result[expected_key] == 81
    assert result["reasoning"] == "fixed"


@pytest.mark.parametrize("plugin_id", ["zgc_simple", "zgc_ai_native_2026"])
def test_plugin_parse_retry_exhaustion_raises_by_default(monkeypatch, plugin_id):
    plugin = _load_scan_plugin(plugin_id, f"test_{plugin_id}_parse_retry_raise")
    evaluator = plugin.create_commit_evaluator(data_dir="", api_key="test-key", model="test-model")

    retry_calls = []

    def fake_post(*_args, **_kwargs):
        retry_calls.append(True)
        return _FakeInvalidLlmResponse()

    monkeypatch.setattr(evaluator._http_client, "post", fake_post)

    with pytest.raises(RuntimeError, match="LLM response parsing failed"):
        evaluator._parse_llm_response_with_retry("not json", "original prompt", "test-model")

    assert len(retry_calls) == 1


def test_ai_native_part_evaluation_parse_failure_raises_by_default(monkeypatch):
    plugin = _load_scan_plugin("zgc_ai_native_2026", "test_ai_native_part_parse_failure")
    evaluator = plugin.create_commit_evaluator(data_dir="", api_key="test-key", model="test-model")

    monkeypatch.setattr(evaluator, "_complete_chat", lambda *_args, **_kwargs: "not json")
    monkeypatch.setattr(evaluator._http_client, "post", lambda *_args, **_kwargs: _FakeInvalidLlmResponse())

    with pytest.raises(RuntimeError, match="LLM part evaluation failed.*LLM response parsing failed"):
        evaluator._evaluate_part_with_llm("commits", "commit context", "https://gitee.com/org/repo")


def test_analyze_group_repositories_bubbles_llm_parse_failure(monkeypatch):
    from types import SimpleNamespace

    from evaluator.services import trajectory_service

    class FakeEvaluator:
        def evaluate_repository(self, **_kwargs):
            raise RuntimeError("LLM response parsing failed after retry: bad json")

    fake_scan = SimpleNamespace(create_commit_evaluator=lambda **_kwargs: FakeEvaluator())
    fake_meta = SimpleNamespace(version="0.1.0")

    monkeypatch.setattr(
        trajectory_service,
        "_sync_repo_for_group_eval",
        lambda repo_url: ("gitee", "org", "repo", True),
    )
    monkeypatch.setattr(
        trajectory_service,
        "_load_all_repo_commits",
        lambda repo_url: (
            [
                {
                    "sha": "sha-1",
                    "commit": {"author": {"name": "Ada", "date": "2026-01-01T00:00:00Z"}, "message": "init"},
                    "files": [{"filename": "README.md", "patch": "+hello"}],
                }
            ],
            PROJECT_ROOT,
        ),
    )
    monkeypatch.setattr(trajectory_service, "load_scan_module", lambda _plugin_id: (fake_meta, fake_scan, PROJECT_ROOT))
    monkeypatch.setattr(trajectory_service, "get_llm_api_key", lambda: "test-key")

    with pytest.raises(RuntimeError, match="LLM response parsing failed"):
        trajectory_service.analyze_group_repositories(
            repositories=[{"id": "s1", "repo_url": "https://gitee.com/org/repo"}],
            plugin_id="zgc_ai_native_2026",
            model="deepseek/deepseek-v4-pro",
            language="zh-CN",
        )


@pytest.mark.anyio
async def test_group_analyse_code_route_returns_500_for_llm_parse_failure(monkeypatch):
    from evaluator.routes import trajectory as trajectory_route

    def fake_analyze_group_repositories(**_kwargs):
        raise RuntimeError("LLM response parsing failed after retry: bad json")

    monkeypatch.setattr(trajectory_route, "get_llm_api_key", lambda: "test-key")
    monkeypatch.setattr(trajectory_route, "get_gitee_token", lambda: "gitee-token")
    monkeypatch.setattr(trajectory_route, "resolve_plugin_id", lambda plugin: plugin)
    monkeypatch.setattr(trajectory_route, "analyze_group_repositories", fake_analyze_group_repositories)

    with pytest.raises(HTTPException) as exc_info:
        await trajectory_route.group_analyse_code(
            request_body={
                "tag": "整体",
                "students": [
                    {"id": "s1", "username": "Alice", "repo_url": "https://gitee.com/org/repo-a"},
                ],
            },
            plugin="zgc_ai_native_2026",
            language="zh-CN",
            max_fetch_workers=4,
            forced_checker="",
            worktree_base="build",
        )

    assert exc_info.value.status_code == 500
    assert "LLM response parsing failed" in exc_info.value.detail


@pytest.mark.anyio
async def test_group_analyse_code_route_batches_repos_without_chunk_params(monkeypatch):
    from evaluator.routes import trajectory as trajectory_route

    captured = {}

    def fake_analyze_group_repositories(**kwargs):
        captured.update(kwargs)
        return {
            "success": True,
            "results": [
                {
                    "success": True,
                    "id": "s1",
                    "username": "Alice",
                    "repo_url": "https://gitee.com/org/repo-a",
                    "score": 88,
                    "checkpoint": {"evaluation": {"scores": {"total": 88}}},
                },
                {
                    "success": True,
                    "id": "s2",
                    "username": "Bob",
                    "repo_url": "https://github.com/org/repo-b",
                    "score": 83,
                    "checkpoint": {"evaluation": {"scores": {"total": 83}}},
                },
            ],
            "model_judging": {"primary_models": ["deepseek/deepseek-v4-pro"]},
        }

    monkeypatch.setattr(trajectory_route, "get_llm_api_key", lambda: "test-key")
    monkeypatch.setattr(trajectory_route, "get_github_token", lambda: "github-token")
    monkeypatch.setattr(trajectory_route, "get_gitee_token", lambda: "gitee-token")
    monkeypatch.setattr(trajectory_route, "resolve_plugin_id", lambda plugin: plugin)
    monkeypatch.setattr(trajectory_route, "analyze_group_repositories", fake_analyze_group_repositories)

    result = await trajectory_route.group_analyse_code(
        request_body={
            "tag": "整体",
            "students": [
                {"id": "s1", "username": "Alice", "repo_url": "https://gitee.com/org/repo-a"},
                {"id": "s2", "username": "Bob", "repo_url": "https://github.com/org/repo-b"},
            ],
        },
        plugin="zgc_ai_native_2026",
        language="zh-CN",
        max_fetch_workers=4,
        forced_checker="",
        worktree_base="build",
    )

    assert result["success"] is True
    assert [item["repo_url"] for item in captured["repositories"]] == [
        "https://gitee.com/org/repo-a",
        "https://github.com/org/repo-b",
    ]
    assert all("username" not in item for item in captured["repositories"])
    assert captured["model"] == "deepseek/deepseek-v4-pro"
    assert captured["full_repo"] is True
    assert "use_chunking" not in captured
    assert captured["max_fetch_workers"] == 4


@pytest.mark.anyio
async def test_group_analyse_code_route_maps_courses_branch_to_tree_url(monkeypatch):
    from evaluator.routes import trajectory as trajectory_route

    captured = {}

    def fake_analyze_group_repositories(**kwargs):
        captured.update(kwargs)
        return {
            "success": True,
            "results": [
                {
                    "success": True,
                    "id": "s1",
                    "repo_url": "https://gitee.com/zgcai/oscanner/tree/feat/update-gitee-ci-pipelines",
                    "score": 88,
                    "checkpoint": {"evaluation": {"scores": {"total": 88}}},
                },
            ],
            "model_judging": {"primary_models": ["deepseek/deepseek-v4-pro"]},
        }

    monkeypatch.setattr(trajectory_route, "get_llm_api_key", lambda: "test-key")
    monkeypatch.setattr(trajectory_route, "get_gitee_token", lambda: "gitee-token")
    monkeypatch.setattr(trajectory_route, "resolve_plugin_id", lambda plugin: plugin)
    monkeypatch.setattr(trajectory_route, "analyze_group_repositories", fake_analyze_group_repositories)

    result = await trajectory_route.group_analyse_code(
        request_body={
            "students": [
                {
                    "id": "s1",
                    "username": "Alice",
                    "repo_url": "https://gitee.com/zgcai/oscanner",
                    "repo_branch": "feat/update-gitee-ci-pipelines",
                },
            ],
        },
        plugin="zgc_ai_native_2026",
        language="zh-CN",
        max_fetch_workers=4,
        forced_checker="",
        worktree_base="build",
    )

    assert result["success"] is True
    assert captured["repositories"][0]["repo_url"] == (
        "https://gitee.com/zgcai/oscanner/tree/feat/update-gitee-ci-pipelines"
    )
    assert captured["repositories"][0]["repo_branch"] == "feat/update-gitee-ci-pipelines"


@pytest.mark.anyio
async def test_group_analyse_code_route_maps_single_courses_branch_to_tree_url(monkeypatch):
    from evaluator.routes import trajectory as trajectory_route

    captured = {}

    def fake_analyze_group_repositories(**kwargs):
        captured.update(kwargs)
        return {
            "success": True,
            "results": [
                {
                    "success": True,
                    "id": "s1",
                    "repo_url": "https://github.com/bjzgcai/oscanner/tree/9ba36e6a104ab1ffe296e0f71cf596bca12b2d6a",
                    "score": 88,
                    "checkpoint": {"evaluation": {"scores": {"total": 88}}},
                },
            ],
            "model_judging": {"primary_models": ["deepseek/deepseek-v4-pro"]},
        }

    monkeypatch.setattr(trajectory_route, "get_llm_api_key", lambda: "test-key")
    monkeypatch.setattr(trajectory_route, "get_github_token", lambda: "github-token")
    monkeypatch.setattr(trajectory_route, "resolve_plugin_id", lambda plugin: plugin)
    monkeypatch.setattr(trajectory_route, "analyze_group_repositories", fake_analyze_group_repositories)

    result = await trajectory_route.group_analyse_code(
        request_body={
            "id": "s1",
            "repo_url": "https://github.com/bjzgcai/oscanner",
            "repo_branch": "9ba36e6a104ab1ffe296e0f71cf596bca12b2d6a",
        },
        plugin="zgc_ai_native_2026",
        language="zh-CN",
        max_fetch_workers=4,
        forced_checker="",
        worktree_base="build",
    )

    assert result["success"] is True
    assert captured["repositories"][0]["repo_url"] == (
        "https://github.com/bjzgcai/oscanner/tree/9ba36e6a104ab1ffe296e0f71cf596bca12b2d6a"
    )
    assert captured["repositories"][0]["repo_branch"] == "9ba36e6a104ab1ffe296e0f71cf596bca12b2d6a"


@pytest.mark.anyio
async def test_group_analyse_code_route_preserves_courses_tree_branch_url(monkeypatch):
    from evaluator.routes import trajectory as trajectory_route

    tree_url = "https://gitee.com/zgcai/oscanner/tree/feat/update-gitee-ci-pipelines"
    captured = {}

    def fake_analyze_group_repositories(**kwargs):
        captured.update(kwargs)
        return {
            "success": True,
            "results": [
                {
                    "success": True,
                    "id": "s1",
                    "repo_url": tree_url,
                    "score": 88,
                    "checkpoint": {"evaluation": {"scores": {"total": 88}}},
                },
            ],
            "model_judging": {"primary_models": ["deepseek/deepseek-v4-pro"]},
        }

    monkeypatch.setattr(trajectory_route, "get_llm_api_key", lambda: "test-key")
    monkeypatch.setattr(trajectory_route, "get_gitee_token", lambda: "gitee-token")
    monkeypatch.setattr(trajectory_route, "resolve_plugin_id", lambda plugin: plugin)
    monkeypatch.setattr(trajectory_route, "analyze_group_repositories", fake_analyze_group_repositories)

    result = await trajectory_route.group_analyse_code(
        request_body={
            "students": [
                {
                    "id": "s1",
                    "username": "Alice",
                    "repo_url": tree_url,
                },
            ],
        },
        plugin="zgc_ai_native_2026",
        language="zh-CN",
        max_fetch_workers=4,
        forced_checker="",
        worktree_base="build",
    )

    assert result["success"] is True
    assert captured["repositories"][0]["repo_url"] == tree_url


@pytest.mark.anyio
async def test_group_analyse_code_route_streams_progress_and_final_result(monkeypatch):
    from evaluator.routes import trajectory as trajectory_route

    captured = {}

    class FakeRequest:
        headers = {"accept": "text/event-stream"}

    def fake_analyze_group_repositories(**kwargs):
        captured.update(kwargs)
        kwargs["progress_callback"]("section", {
            "title": "评估 Alice",
            "status": "running",
            "repo_url": "https://gitee.com/org/repo-a",
        })
        kwargs["progress_callback"]("token", {"content": "streamed judgment"})
        return {
            "success": True,
            "results": [
                {
                    "success": True,
                    "id": "s1",
                    "username": "Alice",
                    "repo_url": "https://gitee.com/org/repo-a",
                    "score": 88,
                    "checkpoint": {"evaluation": {"scores": {"total": 88}}},
                    "commits_analyzed": 12,
                },
            ],
            "model_judging": {"primary_models": ["deepseek/deepseek-v4-pro"]},
        }

    monkeypatch.setattr(trajectory_route, "get_llm_api_key", lambda: "test-key")
    monkeypatch.setattr(trajectory_route, "get_gitee_token", lambda: "gitee-token")
    monkeypatch.setattr(trajectory_route, "resolve_plugin_id", lambda plugin: plugin)
    monkeypatch.setattr(trajectory_route, "analyze_group_repositories", fake_analyze_group_repositories)

    response = await trajectory_route.group_analyse_code(
        request_body={
            "tag": "整体",
            "students": [
                {"id": "s1", "username": "Alice", "repo_url": "https://gitee.com/org/repo-a"},
            ],
        },
        request=FakeRequest(),
        plugin="zgc_ai_native_2026",
        language="zh-CN",
        max_fetch_workers=4,
        forced_checker="",
        worktree_base="build",
    )

    assert isinstance(response, StreamingResponse)

    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk if isinstance(chunk, bytes) else chunk.encode("utf-8"))
    body = b"".join(chunks).decode("utf-8")

    assert captured["progress_callback"]
    assert "event: section" in body
    assert "评估 Alice" in body
    assert "streamed judgment" in body
    assert "event: result" in body
    assert '"repo_url":"https://gitee.com/org/repo-a"' in body


def test_ai_native_plugin_evaluate_repository_uses_all_commits_without_chunking(monkeypatch):
    import importlib.util

    scan_path = PROJECT_ROOT / "plugins" / "zgc_ai_native_2026" / "scan" / "__init__.py"
    spec = importlib.util.spec_from_file_location("test_zgc_ai_native_2026_group_scan", scan_path)
    plugin = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(plugin)

    evaluator = plugin.create_commit_evaluator(
        data_dir="",
        api_key="test-key",
        model="deepseek/deepseek-v4-pro",
        language="zh-CN",
    )

    commits = [
        {
            "sha": f"sha-{idx}",
            "author": "Alice" if idx % 2 else "Bob",
            "commit": {
                "author": {"name": "Alice" if idx % 2 else "Bob", "date": f"2026-01-{idx:02d}T00:00:00Z"},
                "message": f"commit {idx}",
            },
            "files": [{"filename": f"file_{idx}.py", "patch": f"+print({idx})"}],
        }
        for idx in range(1, 31)
    ]

    contexts = []

    def fail_chunking(*_args, **_kwargs):
        raise AssertionError("full repository evaluation must not chunk")

    def fake_part_eval(part_name, part_context, username, chunk_idx=None):
        contexts.append((part_name, part_context, username, chunk_idx))
        return {
            "spec_quality": 80,
            "cloud_architecture": 70,
            "ai_engineering": 75,
            "mastery_professionalism": 85,
            "reasoning": "repo-level judgment",
        }

    def fake_merge(partial_results, username, checker_raw_analysis=None):
        return partial_results[0]

    monkeypatch.setattr(evaluator, "_evaluate_engineer_chunked", fail_chunking)
    monkeypatch.setattr(evaluator, "_evaluate_part_with_llm", fake_part_eval)
    monkeypatch.setattr(evaluator, "_merge_partial_evaluations", fake_merge)

    result = evaluator.evaluate_repository(
        commits=commits,
        repo_label="https://gitee.com/org/repo",
        load_files=False,
    )

    assert result["username"] == "https://gitee.com/org/repo"
    assert result["total_commits_analyzed"] == 30
    commits_context = next(context for part_name, context, *_ in contexts if part_name == "commits")
    assert "sha-1" in commits_context
    assert "sha-30" in commits_context
    assert "Commits: 30" in commits_context


def test_ai_native_plugin_evaluate_repository_reports_provider_token_usage(monkeypatch):
    import importlib.util

    scan_path = PROJECT_ROOT / "plugins" / "zgc_ai_native_2026" / "scan" / "__init__.py"
    spec = importlib.util.spec_from_file_location("test_zgc_ai_native_2026_group_scan_usage", scan_path)
    plugin = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(plugin)

    evaluator = plugin.create_commit_evaluator(
        data_dir="",
        api_key="test-key",
        model="deepseek/deepseek-v4-pro",
        language="zh-CN",
    )

    class FakeResponse:
        is_success = True

        def __init__(self, prompt_tokens, completion_tokens):
            self._prompt_tokens = prompt_tokens
            self._completion_tokens = completion_tokens

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"spec_quality":80,"cloud_architecture":70,'
                                '"ai_engineering":75,"mastery_professionalism":85,'
                                '"reasoning":"ok"}'
                            )
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": self._prompt_tokens,
                    "completion_tokens": self._completion_tokens,
                    "total_tokens": self._prompt_tokens + self._completion_tokens,
                },
            }

    calls = []

    def fake_post(*_args, json=None, **_kwargs):
        calls.append(json)
        return FakeResponse(
            prompt_tokens=1000 + len(calls),
            completion_tokens=100 + len(calls),
        )

    monkeypatch.setattr(evaluator._http_client, "post", fake_post)

    result = evaluator.evaluate_repository(
        commits=[
            {
                "sha": "sha-1",
                "commit": {"author": {"name": "Ada", "date": "2026-01-01T00:00:00Z"}, "message": "init"},
                "files": [{"filename": "README.md", "patch": "+hello"}],
            }
        ],
        repo_label="https://gitee.com/org/repo",
        load_files=False,
    )

    assert len(calls) == 1
    assert result["token_usage"] == {
        "input_tokens": 1001,
        "output_tokens": 101,
        "total_tokens": 1102,
        "source": "provider",
    }


def test_ai_native_plugin_reasoning_uses_structured_dimension_evidence(monkeypatch):
    plugin = _load_scan_plugin("zgc_ai_native_2026", "test_ai_native_structured_reasoning")
    evaluator = plugin.create_commit_evaluator(
        data_dir="",
        api_key="test-key",
        model="deepseek/deepseek-v4-pro",
        language="zh-CN",
    )

    def fake_part_eval(part_name, part_context, username, chunk_idx=None):
        return {
            "spec_quality": 82,
            "cloud_architecture": 76,
            "ai_engineering": 68,
            "mastery_professionalism": 88,
            "reasoning": f"{part_name} judgment",
        }

    monkeypatch.setattr(evaluator, "_evaluate_part_with_llm", fake_part_eval)

    result = evaluator.evaluate_repository(
        commits=[
            {
                "sha": "abc123456789",
                "commit": {
                    "author": {"name": "Ada", "date": "2026-01-01T00:00:00Z"},
                    "message": "refactor validation and add unit tests",
                },
                "files": [
                    {"filename": "backend/schemas/course.py", "patch": "+class Course"},
                    {"filename": "tests/test_course_schema.py", "patch": "+def test_schema"},
                ],
            },
            {
                "sha": "def987654321",
                "commit": {
                    "author": {"name": "Ada", "date": "2026-01-02T00:00:00Z"},
                    "message": "add docker compose and deployment workflow",
                },
                "files": [
                    {"filename": "docker-compose.yml", "patch": "+services:"},
                    {"filename": ".github/workflows/ci.yml", "patch": "+name: ci"},
                ],
            },
            {
                "sha": "fed555555555",
                "commit": {
                    "author": {"name": "Ada", "date": "2026-01-03T00:00:00Z"},
                    "message": "add llm prompt evaluation traces",
                },
                "files": [
                    {"filename": "backend/ai/prompts.py", "patch": "+PROMPT"},
                    {"filename": "evals/llm_trace.json", "patch": "+{}"},
                ],
            },
            {
                "sha": "999aaa111bbb",
                "commit": {
                    "author": {"name": "Ada", "date": "2026-01-04T00:00:00Z"},
                    "message": "document security tradeoffs in ADR",
                },
                "files": [
                    {"filename": "docs/adr/security.md", "patch": "+tradeoff"},
                    {"filename": "CHANGELOG.md", "patch": "+security notes"},
                ],
            },
        ],
        repo_label="https://gitee.com/org/repo",
        load_files=False,
    )

    reasoning = result["scores"]["reasoning"]
    for section in [
        "## 规范与内建质量",
        "## 云原生与架构演进",
        "## AI工程与自动演进",
        "## 工程修养与职业素养",
        "## 结论与建议",
    ]:
        assert section in reasoning

    assert "分数：82/100" in reasoning
    assert "等级：L4" in reasoning
    assert "abc12345" in reasoning
    assert "refactor validation and add unit tests" in reasoning
    assert "backend/schemas/course.py" in reasoning
    assert "docker-compose.yml" in reasoning
    assert "backend/ai/prompts.py" in reasoning
    assert "docs/adr/security.md" in reasoning
    assert reasoning.rfind("## 结论与建议") > reasoning.rfind("## 工程修养与职业素养")


def test_ai_native_structured_reasoning_keeps_dimension_assessments_separate():
    plugin = _load_scan_plugin("zgc_ai_native_2026", "test_ai_native_dimension_reasoning_separation")
    evaluator = plugin.create_commit_evaluator(
        data_dir="",
        api_key="test-key",
        model="deepseek/deepseek-v4-pro",
        language="zh-CN",
    )
    evaluator._latest_dimension_evidence = {key: [] for key in evaluator.dimensions.keys()}

    llm_reasoning = (
        "**提交记录**: ## 规范与内建质量\n"
        "规范判断：质量门禁较弱。\n\n"
        "## 云原生与架构演进\n"
        "云原生判断：没有部署自动化。\n\n"
        "## AI工程与自动演进\n"
        "AI判断：已有 agent 规则但缺少评测闭环。\n\n"
        "## 工程修养与职业素养\n"
        "职业判断：有 README 但缺少 ADR。\n\n"
        "## 结论与建议\n"
        "整体还停留在脚手架阶段，应优先补齐测试、部署和 AI eval。"
    )

    reasoning = evaluator._format_structured_reasoning(
        {
            "spec_quality": 15,
            "cloud_architecture": 0,
            "ai_engineering": 38,
            "mastery_professionalism": 27,
        },
        [llm_reasoning],
        checker_raw_analysis=None,
    )

    def section(title: str) -> str:
        start = reasoning.index(f"## {title}")
        next_start = reasoning.find("\n## ", start + 1)
        return reasoning[start:] if next_start == -1 else reasoning[start:next_start]

    ai_section = section("AI工程与自动演进")
    assert "AI判断：已有 agent 规则但缺少评测闭环。" in ai_section
    assert "规范判断：质量门禁较弱。" not in ai_section
    assert "云原生判断：没有部署自动化。" not in ai_section
    assert "职业判断：有 README 但缺少 ADR。" not in ai_section
    assert reasoning.count("规范判断：质量门禁较弱。") == 1
    assert reasoning.count("云原生判断：没有部署自动化。") == 1
    assert reasoning.count("AI判断：已有 agent 规则但缺少评测闭环。") == 1
    assert reasoning.count("职业判断：有 README 但缺少 ADR。") == 1

    conclusion = reasoning[reasoning.rfind("## 结论与建议"):]
    assert "脚手架阶段" in conclusion
    assert "规范判断：质量门禁较弱。" not in conclusion


def test_ai_native_structured_reasoning_retains_mid_length_assessments():
    plugin = _load_scan_plugin("zgc_ai_native_2026", "test_ai_native_reasoning_retention_length")
    evaluator = plugin.create_commit_evaluator(
        data_dir="",
        api_key="test-key",
        model="deepseek/deepseek-v4-pro",
        language="zh-CN",
    )
    evaluator._latest_dimension_evidence = {key: [] for key in evaluator.dimensions.keys()}

    dimension_detail = "维度细节" * 110
    conclusion_detail = "结论细节" * 120
    llm_reasoning = (
        "## 规范与内建质量\n"
        f"规范判断：{dimension_detail}。末尾维度保留。\n\n"
        "## 云原生与架构演进\n"
        "云原生判断：部署证据不足。\n\n"
        "## AI工程与自动演进\n"
        "AI判断：自动化闭环不足。\n\n"
        "## 工程修养与职业素养\n"
        "职业判断：文档记录不足。\n\n"
        "## 结论与建议\n"
        f"整体总结：{conclusion_detail}。末尾结论保留。"
    )

    reasoning = evaluator._format_structured_reasoning(
        {
            "spec_quality": 15,
            "cloud_architecture": 0,
            "ai_engineering": 38,
            "mastery_professionalism": 27,
        },
        [llm_reasoning],
        checker_raw_analysis=None,
    )

    assert "末尾维度保留" in reasoning
    assert "末尾结论保留" in reasoning


def test_ai_native_plugin_streaming_evaluation_reports_provider_token_usage(monkeypatch):
    import importlib.util

    scan_path = PROJECT_ROOT / "plugins" / "zgc_ai_native_2026" / "scan" / "__init__.py"
    spec = importlib.util.spec_from_file_location("test_zgc_ai_native_2026_group_scan_stream_usage", scan_path)
    plugin = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(plugin)

    events = []
    evaluator = plugin.create_commit_evaluator(
        data_dir="",
        api_key="test-key",
        model="deepseek/deepseek-v4-pro",
        language="zh-CN",
        progress_callback=lambda event, data: events.append((event, data)),
    )

    class FakeStreamResponse:
        is_success = True

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def iter_lines(self):
            yield 'data: {"choices":[{"delta":{"content":"{\\"spec_quality\\":80,\\"cloud_architecture\\":70,"}}]}\n\n'
            yield 'data: {"choices":[{"delta":{"content":"\\"ai_engineering\\":75,\\"mastery_professionalism\\":85,\\"reasoning\\":\\"ok\\"}"}}]}\n\n'
            yield 'data: {"choices":[],"usage":{"prompt_tokens":2345,"completion_tokens":123,"total_tokens":2468}}\n\n'
            yield "data: [DONE]\n\n"

    captured_payloads = []

    def fake_stream(*_args, json=None, **_kwargs):
        captured_payloads.append(json)
        return FakeStreamResponse()

    monkeypatch.setattr(evaluator._http_client, "stream", fake_stream)

    result = evaluator.evaluate_repository(
        commits=[
            {
                "sha": "sha-1",
                "commit": {"author": {"name": "Ada", "date": "2026-01-01T00:00:00Z"}, "message": "init"},
                "files": [{"filename": "README.md", "patch": "+hello"}],
            }
        ],
        repo_label="https://gitee.com/org/repo",
        load_files=False,
    )

    assert captured_payloads[0]["stream"] is True
    assert captured_payloads[0]["stream_options"] == {"include_usage": True}
    assert result["token_usage"] == {
        "input_tokens": 2345,
        "output_tokens": 123,
        "total_tokens": 2468,
        "source": "provider",
    }
    assert any(event == "token" for event, _data in events)


def test_analyze_group_repositories_exposes_row_and_total_token_usage(monkeypatch):
    from types import SimpleNamespace

    from evaluator.services import trajectory_service

    class FakeEvaluator:
        def evaluate_repository(self, **_kwargs):
            return {
                "username": "https://gitee.com/org/repo",
                "total_commits_analyzed": 1,
                "files_loaded": 0,
                "mode": "moderate",
                "scores": {
                    "spec_quality": 80,
                    "cloud_architecture": 70,
                    "ai_engineering": 75,
                    "mastery_professionalism": 85,
                    "reasoning": "ok",
                },
                "commits_summary": {},
                "token_usage": {
                    "input_tokens": 2345,
                    "output_tokens": 123,
                    "total_tokens": 2468,
                    "source": "provider",
                },
            }

    fake_scan = SimpleNamespace(create_commit_evaluator=lambda **_kwargs: FakeEvaluator())
    fake_meta = SimpleNamespace(version="0.1.0")

    monkeypatch.setattr(
        trajectory_service,
        "_sync_repo_for_group_eval",
        lambda repo_url: ("gitee", "org", "repo", False),
    )
    monkeypatch.setattr(
        trajectory_service,
        "_load_all_repo_commits",
        lambda repo_url: (
            [
                {
                    "sha": "sha-1",
                    "commit": {"author": {"date": "2026-01-01T00:00:00Z"}, "message": "init"},
                }
            ],
            PROJECT_ROOT,
        ),
    )
    monkeypatch.setattr(trajectory_service, "load_scan_module", lambda _plugin_id: (fake_meta, fake_scan, PROJECT_ROOT))
    monkeypatch.setattr(trajectory_service, "get_llm_api_key", lambda: "test-key")

    result = trajectory_service.analyze_group_repositories(
        repositories=[
            {
                "id": "s1",
                "username": "Alice",
                "repo_url": "https://gitee.com/org/repo",
            }
        ],
        plugin_id="zgc_ai_native_2026",
        model="deepseek/deepseek-v4-pro",
        language="zh-CN",
    )

    assert result["token_usage"] == {
        "input_tokens": 2345,
        "output_tokens": 123,
        "total_tokens": 2468,
        "source": "provider",
    }
    assert result["results"][0]["token_usage"] == result["token_usage"]


def test_analyze_group_repositories_applies_per_repo_commit_ranges(monkeypatch):
    from types import SimpleNamespace

    from evaluator.services import trajectory_service

    captured_commits = {}

    class FakeEvaluator:
        def evaluate_repository(self, commits, repo_label, **_kwargs):
            captured_commits[repo_label] = [commit["sha"] for commit in commits]
            return {
                "username": repo_label,
                "total_commits_analyzed": len(commits),
                "files_loaded": 0,
                "mode": "moderate",
                "scores": {
                    "total": len(commits),
                    "reasoning": "range ok",
                },
                "commits_summary": {},
            }

    fake_scan = SimpleNamespace(create_commit_evaluator=lambda **_kwargs: FakeEvaluator())
    fake_meta = SimpleNamespace(version="0.1.0")
    commits_by_repo = {
        "https://gitee.com/org/repo-a": [
            {"sha": "a-latest", "commit": {"author": {"date": "2026-01-04T00:00:00Z"}, "message": "latest"}},
            {"sha": "a-tag", "commit": {"author": {"date": "2026-01-03T00:00:00Z"}, "message": "tag"}},
            {"sha": "a-middle", "commit": {"author": {"date": "2026-01-02T00:00:00Z"}, "message": "middle"}},
            {"sha": "a-first", "commit": {"author": {"date": "2026-01-01T00:00:00Z"}, "message": "first"}},
        ],
        "https://gitee.com/org/repo-b": [
            {"sha": "b-latest", "commit": {"author": {"date": "2026-01-04T00:00:00Z"}, "message": "latest"}},
            {"sha": "b-tag", "commit": {"author": {"date": "2026-01-03T00:00:00Z"}, "message": "tag"}},
            {"sha": "b-prev", "commit": {"author": {"date": "2026-01-02T00:00:00Z"}, "message": "prev"}},
            {"sha": "b-first", "commit": {"author": {"date": "2026-01-01T00:00:00Z"}, "message": "first"}},
        ],
    }

    monkeypatch.setattr(
        trajectory_service,
        "_sync_repo_for_group_eval",
        lambda repo_url: ("gitee", "org", repo_url.rsplit("/", 1)[-1], False),
    )
    monkeypatch.setattr(
        trajectory_service,
        "_load_all_repo_commits",
        lambda repo_url: (commits_by_repo[repo_url], PROJECT_ROOT),
    )
    monkeypatch.setattr(trajectory_service, "load_scan_module", lambda _plugin_id: (fake_meta, fake_scan, PROJECT_ROOT))
    monkeypatch.setattr(trajectory_service, "get_llm_api_key", lambda: "test-key")

    result = trajectory_service.analyze_group_repositories(
        repositories=[
            {
                "id": "s1",
                "username": "Alice",
                "repo_url": "https://gitee.com/org/repo-a",
                "end_sha": "a-tag",
            },
            {
                "id": "s2",
                "username": "Bob",
                "repo_url": "https://gitee.com/org/repo-b",
                "start_sha": "b-prev",
                "end_sha": "b-tag",
            },
        ],
        plugin_id="zgc_ai_native_2026",
        model="deepseek/deepseek-v4-pro",
        language="zh-CN",
    )

    assert result["success"] is True
    assert captured_commits == {
        "https://gitee.com/org/repo-a": ["a-tag", "a-middle", "a-first"],
        "https://gitee.com/org/repo-b": ["b-tag", "b-prev"],
    }
    assert result["results"][0]["checkpoint"]["commits_range"] == {
        "start_sha": "a-first",
        "end_sha": "a-tag",
        "commit_count": 3,
    }
    assert result["results"][1]["checkpoint"]["commits_range"] == {
        "start_sha": "b-prev",
        "end_sha": "b-tag",
        "commit_count": 2,
    }


def test_analyze_group_repositories_reports_repo_scoped_missing_sha(monkeypatch):
    from types import SimpleNamespace

    from evaluator.services import trajectory_service

    fake_scan = SimpleNamespace(create_commit_evaluator=lambda **_kwargs: None)
    fake_meta = SimpleNamespace(version="0.1.0")

    monkeypatch.setattr(
        trajectory_service,
        "_sync_repo_for_group_eval",
        lambda repo_url: ("gitee", "org", "repo", False),
    )
    monkeypatch.setattr(
        trajectory_service,
        "_load_all_repo_commits",
        lambda repo_url: (
            [
                {
                    "sha": "existing-sha",
                    "commit": {"author": {"date": "2026-01-01T00:00:00Z"}, "message": "init"},
                }
            ],
            PROJECT_ROOT,
        ),
    )
    monkeypatch.setattr(trajectory_service, "load_scan_module", lambda _plugin_id: (fake_meta, fake_scan, PROJECT_ROOT))

    result = trajectory_service.analyze_group_repositories(
        repositories=[
            {
                "id": "s1",
                "username": "Alice",
                "repo_url": "https://gitee.com/org/repo",
                "end_sha": "missing-sha",
            }
        ],
        plugin_id="zgc_ai_native_2026",
        model="deepseek/deepseek-v4-pro",
        language="zh-CN",
    )

    assert result["success"] is False
    assert result["results"][0]["message"] == (
        "end_sha 'missing-sha' not found in repository commits. "
        "Please verify the commit hash exists in the repository."
    )
    assert "specified user" not in result["results"][0]["message"]


def test_analyze_group_repositories_refreshes_and_retries_missing_sha(monkeypatch):
    from types import SimpleNamespace

    from evaluator.services import trajectory_service

    sync_calls = []
    load_calls = []
    evaluated_commits = []

    class FakeEvaluator:
        def evaluate_repository(self, commits, repo_label, **_kwargs):
            evaluated_commits.extend(commit["sha"] for commit in commits)
            return {
                "username": repo_label,
                "total_commits_analyzed": len(commits),
                "files_loaded": 0,
                "mode": "moderate",
                "scores": {
                    "total": len(commits),
                    "reasoning": "retried after refresh",
                },
                "commits_summary": {},
            }

    def fake_sync(repo_url):
        sync_calls.append(repo_url)
        return ("gitee", "org", "repo", True)

    def fake_load(repo_url):
        load_calls.append(repo_url)
        if len(load_calls) == 1:
            return (
                [
                    {
                        "sha": "existing-sha",
                        "commit": {"author": {"date": "2026-01-01T00:00:00Z"}, "message": "init"},
                    }
                ],
                PROJECT_ROOT,
            )
        return (
            [
                {
                    "sha": "target-sha",
                    "commit": {"author": {"date": "2026-01-02T00:00:00Z"}, "message": "target"},
                },
                {
                    "sha": "existing-sha",
                    "commit": {"author": {"date": "2026-01-01T00:00:00Z"}, "message": "init"},
                },
            ],
            PROJECT_ROOT,
        )

    fake_scan = SimpleNamespace(create_commit_evaluator=lambda **_kwargs: FakeEvaluator())
    fake_meta = SimpleNamespace(version="0.1.0")

    monkeypatch.setattr(trajectory_service, "_sync_repo_for_group_eval", fake_sync)
    monkeypatch.setattr(trajectory_service, "_load_all_repo_commits", fake_load)
    monkeypatch.setattr(trajectory_service, "load_scan_module", lambda _plugin_id: (fake_meta, fake_scan, PROJECT_ROOT))
    monkeypatch.setattr(trajectory_service, "get_llm_api_key", lambda: "test-key")

    result = trajectory_service.analyze_group_repositories(
        repositories=[
            {
                "id": "s1",
                "username": "Alice",
                "repo_url": "https://gitee.com/org/repo",
                "end_sha": "target-sha",
            }
        ],
        plugin_id="zgc_ai_native_2026",
        model="deepseek/deepseek-v4-pro",
        language="zh-CN",
    )

    assert result["success"] is True
    assert sync_calls == [
        "https://gitee.com/org/repo",
        "https://gitee.com/org/repo",
    ]
    assert load_calls == [
        "https://gitee.com/org/repo",
        "https://gitee.com/org/repo",
    ]
    assert evaluated_commits == ["target-sha", "existing-sha"]
    assert result["results"][0]["commits_analyzed"] == 2


def test_analyze_group_repositories_fetches_missing_gitee_boundary_sha(monkeypatch):
    from types import SimpleNamespace

    from evaluator.services import trajectory_service

    load_calls = []
    boundary_sync_calls = []
    evaluated_commits = []

    class FakeEvaluator:
        def evaluate_repository(self, commits, repo_label, **_kwargs):
            evaluated_commits.extend(commit["sha"] for commit in commits)
            return {
                "username": repo_label,
                "total_commits_analyzed": len(commits),
                "files_loaded": 0,
                "mode": "moderate",
                "scores": {
                    "total": len(commits),
                    "reasoning": "tag boundary synced",
                },
                "commits_summary": {},
            }

    def fake_load(repo_url):
        load_calls.append(repo_url)
        if len(load_calls) < 3:
            return (
                [
                    {
                        "sha": "existing-sha",
                        "commit": {"author": {"date": "2026-01-01T00:00:00Z"}, "message": "init"},
                    }
                ],
                PROJECT_ROOT,
            )
        return (
            [
                {
                    "sha": "tag-sha",
                    "commit": {"author": {"date": "2026-01-02T00:00:00Z"}, "message": "tag"},
                },
                {
                    "sha": "existing-sha",
                    "commit": {"author": {"date": "2026-01-01T00:00:00Z"}, "message": "init"},
                },
            ],
            PROJECT_ROOT,
        )

    def fake_sync_boundary(owner, repo, shas):
        boundary_sync_calls.append((owner, repo, shas))
        return True

    fake_scan = SimpleNamespace(create_commit_evaluator=lambda **_kwargs: FakeEvaluator())
    fake_meta = SimpleNamespace(version="0.1.0")

    monkeypatch.setattr(
        trajectory_service,
        "_sync_repo_for_group_eval",
        lambda repo_url: ("gitee", "org", "repo", True),
    )
    monkeypatch.setattr(trajectory_service, "_load_all_repo_commits", fake_load)
    monkeypatch.setattr(trajectory_service, "sync_gitee_commits_by_sha", fake_sync_boundary, raising=False)
    monkeypatch.setattr(trajectory_service, "load_scan_module", lambda _plugin_id: (fake_meta, fake_scan, PROJECT_ROOT))
    monkeypatch.setattr(trajectory_service, "get_llm_api_key", lambda: "test-key")

    result = trajectory_service.analyze_group_repositories(
        repositories=[
            {
                "id": "s1",
                "repo_url": "https://gitee.com/org/repo",
                "tag": "Coursework_Submit_2.3",
                "end_sha": "tag-sha",
            }
        ],
        plugin_id="zgc_ai_native_2026",
        model="deepseek/deepseek-v4-pro",
        language="zh-CN",
    )

    assert result["success"] is True
    assert boundary_sync_calls == [("org", "repo", ["tag-sha"])]
    assert load_calls == [
        "https://gitee.com/org/repo",
        "https://gitee.com/org/repo",
        "https://gitee.com/org/repo",
    ]
    assert evaluated_commits == ["tag-sha", "existing-sha"]
    assert result["results"][0]["sync"]["boundary_sync"] is True
