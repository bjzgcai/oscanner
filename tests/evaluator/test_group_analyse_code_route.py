"""Tests for courses-style group repository evaluation."""

import sys
from pathlib import Path

import pytest
from fastapi.responses import StreamingResponse


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.mark.anyio
async def test_group_analyse_code_route_batches_repos_without_parallel_chunking(monkeypatch):
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
        use_cache=True,
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
    assert captured["use_chunking"] is False
    assert captured["max_fetch_workers"] == 4


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
        use_cache=True,
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
        use_chunking=False,
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
        use_chunking=False,
    )

    assert len(calls) == 1
    assert result["token_usage"] == {
        "input_tokens": 1001,
        "output_tokens": 101,
        "total_tokens": 1102,
        "source": "provider",
    }


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
        use_chunking=False,
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
        lambda repo_url, use_cache: ("gitee", "org", "repo", False),
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
        lambda repo_url, use_cache: ("gitee", "org", repo_url.rsplit("/", 1)[-1], False),
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
        lambda repo_url, use_cache: ("gitee", "org", "repo", False),
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

    def fake_sync(repo_url, use_cache):
        sync_calls.append((repo_url, use_cache))
        return ("gitee", "org", "repo", not use_cache)

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
        use_cache=True,
    )

    assert result["success"] is True
    assert sync_calls == [
        ("https://gitee.com/org/repo", True),
        ("https://gitee.com/org/repo", False),
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
        lambda repo_url, use_cache: ("gitee", "org", "repo", not use_cache),
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
        use_cache=True,
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
