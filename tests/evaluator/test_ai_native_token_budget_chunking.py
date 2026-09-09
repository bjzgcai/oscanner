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


def test_ai_native_splits_single_commit_without_discarding_input(monkeypatch):
    evaluator = _load_ai_native_plugin().create_commit_evaluator(
        data_dir="", api_key="test-key", max_input_tokens=6000)
    seen = []
    def extract(batch):
        seen.extend(batch)
        return []
    monkeypatch.setattr(evaluator, "_extract_evidence_batch", extract)
    monkeypatch.setattr(evaluator, "synthesize_evidence", lambda sources, facts: {"scores": {"reasoning": "final"}})
    result = evaluator._evaluate_engineer_chunked(
        [_commit(1, patch="+" + ("x" * 40000))], "alice", load_files=False)
    assert len(seen) > 2
    assert not result.get("input_truncated")
    fragments = [source for source in seen if source.get("path") == "file_1.py"]
    fragments.sort(key=lambda source: source.get("fragment", 0))
    assert sum(source["content"].count("x") for source in fragments) == 40000


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


def test_ai_native_extracts_chunks_in_parallel_and_scores_once(monkeypatch):
    evaluator = _load_ai_native_plugin().create_commit_evaluator(
        data_dir="", api_key="test-key", max_input_tokens=100000)
    monkeypatch.setattr(evaluator, "_source_batches", lambda sources: [sources[:2], sources[2:]])
    active = 0
    maximum = 0
    lock = threading.Lock()
    synthesis_calls = []
    def extract(batch):
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        time.sleep(0.05)
        with lock:
            active -= 1
        return [{"dimension": "spec_quality", "kind": "support", "text": "Visible tests", "refs": [batch[0]["id"]]}]
    def synthesize(sources, facts):
        synthesis_calls.append(facts)
        return {"scores": {"spec_quality": 57, "reasoning": "final"}}
    monkeypatch.setattr(evaluator, "_extract_evidence_batch", extract)
    monkeypatch.setattr(evaluator, "synthesize_evidence", synthesize)
    result = evaluator._evaluate_engineer_chunked([_commit(i) for i in range(1, 5)], "alice", load_files=False)
    assert maximum == 2
    assert len(synthesis_calls) == 1
    assert len(synthesis_calls[0]) == 2
    assert result["scores"]["spec_quality"] == 57
    assert "chunks_merged" not in result["scores"]
    assert result["chunking_strategy"] == "evidence_synthesis"
