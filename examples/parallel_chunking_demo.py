#!/usr/bin/env python3
"""
Example: Testing parallel vs sequential chunking strategies

This script demonstrates the difference between sequential and parallel chunking modes.
"""

import requests
import time
from typing import Dict, Any


API_BASE_URL = "http://localhost:8000"


def evaluate_author_with_mode(
    owner: str,
    repo: str,
    author: str,
    parallel: bool = False,
    max_workers: int = 3,
) -> Dict[str, Any]:
    """Evaluate an author with specified chunking mode."""

    url = f"{API_BASE_URL}/api/evaluate/{owner}/{repo}/{author}"
    params = {
        "use_chunking": True,
        "parallel_chunking": parallel,
        "max_parallel_workers": max_workers,
    }

    print(f"\n{'='*60}")
    print(f"Evaluating with {'PARALLEL' if parallel else 'SEQUENTIAL'} mode")
    if parallel:
        print(f"Workers: {max_workers}")
    print(f"{'='*60}\n")

    start_time = time.time()
    response = requests.post(url, params=params)
    elapsed = time.time() - start_time

    if response.status_code == 200:
        data = response.json()
        evaluation = data.get("evaluation", {})

        print(f"✓ Evaluation completed in {elapsed:.2f} seconds")
        print(f"  Strategy: {evaluation.get('chunking_strategy', 'unknown')}")
        print(f"  Chunks processed: {evaluation.get('chunks_processed', 0)}")
        print(f"  Total commits: {evaluation.get('total_commits_analyzed', 0)}")
        print(f"  Files loaded: {evaluation.get('files_loaded', 0)}")

        scores = evaluation.get("scores", {})
        print(f"\nScores:")
        for key, value in scores.items():
            if key != "reasoning" and isinstance(value, (int, float)):
                print(f"  {key}: {value}")

        return {
            "elapsed": elapsed,
            "evaluation": evaluation,
        }
    else:
        print(f"✗ Request failed: {response.status_code}")
        print(f"  Error: {response.text}")
        return {"elapsed": elapsed, "error": response.text}


def compare_modes(owner: str, repo: str, author: str):
    """Compare sequential vs parallel chunking performance."""

    print("\n" + "="*60)
    print("CHUNKING STRATEGY COMPARISON")
    print("="*60)

    # Test sequential mode
    sequential_result = evaluate_author_with_mode(
        owner, repo, author,
        parallel=False
    )

    # Test parallel mode with 3 workers
    parallel_result = evaluate_author_with_mode(
        owner, repo, author,
        parallel=True,
        max_workers=3
    )

    # Print comparison
    print("\n" + "="*60)
    print("PERFORMANCE COMPARISON")
    print("="*60)

    seq_time = sequential_result.get("elapsed", 0)
    par_time = parallel_result.get("elapsed", 0)

    if seq_time > 0 and par_time > 0:
        speedup = seq_time / par_time
        print(f"\nSequential: {seq_time:.2f}s")
        print(f"Parallel:   {par_time:.2f}s")
        print(f"Speedup:    {speedup:.2f}x")

        if speedup > 1:
            print(f"\n✓ Parallel mode was {speedup:.2f}x faster!")
        elif speedup < 0.9:
            print(f"\n⚠ Sequential mode was faster (parallel overhead)")
        else:
            print(f"\n≈ Similar performance (small dataset)")


if __name__ == "__main__":
    # Example repository - replace with your own
    OWNER = "your-owner"
    REPO = "your-repo"
    AUTHOR = "your-author"

    print("\nParallel Chunking Demo")
    print("=" * 60)
    print("\nMake sure:")
    print("1. The API server is running (python -m evaluator.main)")
    print("2. Repository data has been extracted")
    print("3. LLM API key is configured\n")

    # Uncomment to run the comparison
    # compare_modes(OWNER, REPO, AUTHOR)

    print("\nTo use this script:")
    print("1. Replace OWNER, REPO, AUTHOR with your values")
    print("2. Uncomment the compare_modes() call")
    print("3. Run: python examples/parallel_chunking_demo.py\n")
