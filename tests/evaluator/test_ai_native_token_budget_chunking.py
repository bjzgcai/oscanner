import importlib.util
import threading
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_ai_native_plugin():
    scan_path = PROJECT_ROOT / "plugins" / "zgc_ai_native_2026" / "scan" / "__init__.py"
    spec = importlib.util.spec_from_file_location("test_zgc_ai_native_2026_token_budget", scan_path)
    plugin = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(plugin)
    return plugin


def _commit(idx: int, patch: str = "+print('ok')") -> dict:
    return {
        "sha": f"sha-{idx}",
        "author": "alice",
        "commit": {
            "author": {"name": "alice", "date": f"2026-01-{idx:02d}T00:00:00Z"},
            "message": f"commit {idx}",
        },
        "files": [{"filename": f"file_{idx}.py", "patch": patch}],
    }


def test_ai_native_does_not_chunk_only_because_commit_count(monkeypatch):
    plugin = _load_ai_native_plugin()
    evaluator = plugin.create_commit_evaluator(
        data_dir="",
        api_key="test-key",
        model="deepseek/deepseek-v4-pro",
        language="en-US",
        max_input_tokens=1_000_000,
    )

    def fail_chunking(*_args, **_kwargs):
        raise AssertionError("commit count alone must not trigger chunking")

    monkeypatch.setattr(evaluator, "_evaluate_engineer_chunked", fail_chunking)
    monkeypatch.setattr(
        evaluator,
        "_evaluate_engineer_standard",
        lambda commits, username, load_files: {
            "username": username,
            "total_commits_analyzed": len(commits),
            "scores": {"reasoning": "single prompt"},
        },
    )

    result = evaluator.evaluate_engineer(
        commits=[_commit(idx) for idx in range(1, 26)],
        username="alice",
        max_commits=None,
        load_files=False,
    )

    assert result["total_commits_analyzed"] == 25
    assert result["scores"]["reasoning"] == "single prompt"


def test_ai_native_chunks_when_full_prompt_exceeds_token_budget(monkeypatch):
    plugin = _load_ai_native_plugin()
    evaluator = plugin.create_commit_evaluator(
        data_dir="",
        api_key="test-key",
        model="deepseek/deepseek-v4-pro",
        language="en-US",
        max_input_tokens=250,
    )
    monkeypatch.setattr(evaluator, "_estimate_tokens", lambda text: len(text))

    def fail_standard(*_args, **_kwargs):
        raise AssertionError("oversized prompt must be split before standard evaluation")

    monkeypatch.setattr(evaluator, "_evaluate_engineer_standard", fail_standard)
    monkeypatch.setattr(
        evaluator,
        "_evaluate_engineer_chunked",
        lambda commits, username, load_files: {
            "username": username,
            "total_commits_analyzed": len(commits),
            "chunked": True,
            "chunking_strategy": "parallel",
            "scores": {"reasoning": "split by token budget"},
        },
    )

    result = evaluator.evaluate_engineer(
        commits=[_commit(idx, patch="+" + ("x" * 500)) for idx in range(1, 4)],
        username="alice",
        max_commits=None,
        load_files=False,
    )

    assert result["chunked"] is True
    assert result["chunking_strategy"] == "parallel"


def test_ai_native_truncates_single_commit_that_exceeds_token_budget(monkeypatch):
    plugin = _load_ai_native_plugin()
    evaluator = plugin.create_commit_evaluator(
        data_dir="",
        api_key="test-key",
        model="deepseek/deepseek-v4-pro",
        language="en-US",
        max_input_tokens=6000,
    )
    monkeypatch.setattr(evaluator, "_estimate_tokens", lambda text: len(text))

    seen_contexts = []

    def fake_evaluate(context, username, chunk_idx=None):
        seen_contexts.append(context)
        assert "+xxxxxxxxxx" in context
        assert "truncated to fit LLM input budget" in context
        assert len(evaluator._build_evaluation_prompt(context, username, chunk_idx=chunk_idx)) <= evaluator.max_input_tokens
        return {
            "spec_quality": 70,
            "cloud_architecture": 70,
            "ai_engineering": 70,
            "mastery_professionalism": 70,
            "reasoning": "evaluated from truncated input",
        }

    monkeypatch.setattr(evaluator, "_evaluate_with_llm", fake_evaluate)

    result = evaluator.evaluate_engineer(
        commits=[_commit(1, patch="+" + ("x" * 20_000))],
        username="alice",
        max_commits=None,
        load_files=False,
    )

    assert seen_contexts
    assert result["scores"]["reasoning"] == "evaluated from truncated input"
    assert result["input_truncated"] is True
    assert "warnings" in result
    assert result["input_budget_errors"][0]["type"] == "single_commit_exceeds_budget"
    assert "A single commit exceeds the LLM input budget" in result["input_budget_errors"][0]["message"]


def test_ai_native_sizes_chunks_using_exact_final_prompt(monkeypatch):
    plugin = _load_ai_native_plugin()
    evaluator = plugin.create_commit_evaluator(
        data_dir="",
        api_key="test-key",
        model="deepseek/deepseek-v4-pro",
        language="en-US",
        max_input_tokens=6500,
    )
    monkeypatch.setattr(evaluator, "_estimate_tokens", lambda text: len(text))

    commits = [_commit(idx, patch="+" + ("x" * 3500)) for idx in range(1, 4)]
    chunks, _ = evaluator._split_commits_for_prompt_budget(commits, "alice", load_files=False)

    assert len(chunks) > 1
    for idx, chunk in enumerate(chunks, 1):
        context = evaluator._build_chunked_context(
            chunk,
            "alice",
            chunk_idx=idx,
            total_chunks=len(chunks),
            file_contents={},
            repo_structure=None,
        )
        assert evaluator._prompt_token_count(context, "alice", chunk_idx=idx) <= evaluator.max_input_tokens


def test_ai_native_evaluates_chunks_independently_in_parallel(monkeypatch):
    plugin = _load_ai_native_plugin()
    evaluator = plugin.create_commit_evaluator(
        data_dir="",
        api_key="test-key",
        model="deepseek/deepseek-v4-pro",
        language="en-US",
        max_input_tokens=100_000,
    )
    chunks = [[_commit(1)], [_commit(2), _commit(3), _commit(4)]]
    monkeypatch.setattr(
        evaluator,
        "_split_commits_for_prompt_budget",
        lambda commits, username, load_files: (chunks, []),
    )

    state_lock = threading.Lock()
    active = 0
    max_active = 0
    seen_contexts = []

    def fake_evaluate(context, username, chunk_idx=None):
        nonlocal active, max_active
        with state_lock:
            active += 1
            max_active = max(max_active, active)
            seen_contexts.append(context)
        time.sleep(0.05)
        with state_lock:
            active -= 1
        score = 20 if chunk_idx == 1 else 80
        return {
            "spec_quality": score,
            "cloud_architecture": score,
            "ai_engineering": score,
            "mastery_professionalism": score,
            "reasoning": f"chunk {chunk_idx} evidence",
        }

    monkeypatch.setattr(evaluator, "_evaluate_with_llm", fake_evaluate)

    result = evaluator._evaluate_engineer_chunked(
        [commit for chunk in chunks for commit in chunk],
        "alice",
        load_files=False,
    )

    assert max_active == 2
    assert all("PREVIOUS EVALUATION" not in context for context in seen_contexts)
    assert result["chunking_strategy"] == "parallel"
    assert result["chunks_processed"] == 2
    assert result["scores"]["spec_quality"] == 65
    assert result["scores"]["chunks_merged"] == 2
