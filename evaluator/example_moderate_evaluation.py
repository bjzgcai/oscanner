#!/usr/bin/env python3
"""
Example: Using the Moderate Evaluator with local data

This demonstrates how to evaluate contributors using the moderate approach
(diffs + file contents) from locally extracted data.
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

from evaluator.paths import get_home_dir
from evaluator.plugin_registry import load_scan_module

# Load environment variables
load_dotenv('.env.local')


def load_commits_from_local(data_dir: Path, limit: int = 30) -> list:
    """
    Load commits from local extracted data

    Args:
        data_dir: Path to data directory (e.g., data/shuxueshuxue/ink-and-memory)
        limit: Maximum commits to load

    Returns:
        List of commit data
    """
    commits_index_path = data_dir / "commits_index.json"

    if not commits_index_path.exists():
        print(f"[Error] Commits index not found: {commits_index_path}")
        return []

    # Load commits index
    with open(commits_index_path, 'r', encoding='utf-8') as f:
        commits_index = json.load(f)

    # Load detailed commit data
    commits = []
    commits_dir = data_dir / "commits"

    for commit_info in commits_index[:limit]:
        commit_sha = commit_info.get("hash") or commit_info.get("sha")

        if not commit_sha:
            continue

        # Try to load commit JSON
        commit_json_path = commits_dir / f"{commit_sha}.json"

        if commit_json_path.exists():
            try:
                with open(commit_json_path, 'r', encoding='utf-8') as f:
                    commit_data = json.load(f)
                    commits.append(commit_data)
            except Exception as e:
                print(f"[Warning] Failed to load {commit_sha}: {e}")

    print(f"[Info] Loaded {len(commits)} detailed commits")
    return commits


def evaluate_from_local_data(
    data_dir: str,
    username: str,
    mode: str = "moderate",
    max_commits: int = 30
):
    """
    Evaluate an engineer from local extracted data

    Args:
        data_dir: Path to extracted data (e.g., "data/shuxueshuxue/ink-and-memory")
        username: Username to evaluate
        mode: "conservative" or "moderate"
        max_commits: Maximum commits to analyze
    """
    data_path = Path(data_dir)

    if not data_path.exists():
        print(f"[Error] Data directory not found: {data_dir}")
        return

    print("=" * 80)
    print(f"Evaluating {username} from local data")
    print(f"Mode: {mode}")
    print(f"Data: {data_dir}")
    print("=" * 80)

    # Initialize evaluator
    api_key = os.getenv("OPEN_ROUTER_KEY")
    meta, scan_mod, scan_path = load_scan_module("zgc_simple")
    evaluator = scan_mod.create_commit_evaluator(
        data_dir=str(data_path),
        api_key=api_key,
        model=os.getenv("OSCANNER_LLM_MODEL") or None,
        mode=mode,
    )
    print(f"[Plugin] example uses plugin={meta.plugin_id} scan={scan_path}")

    # Load commits
    print("\n[1/3] Loading commits...")
    commits = load_commits_from_local(data_path, limit=max_commits)

    if not commits:
        print("[Error] No commits loaded!")
        return

    # Filter commits by username (optional)
    # In your case, you might want all commits to evaluate the contributor
    # Or filter by author name if needed

    # Evaluate
    print(f"\n[2/3] Evaluating with {mode} mode...")
    result = evaluator.evaluate_engineer(
        commits=commits,
        username=username,
        max_commits=max_commits,
        load_files=(mode == "moderate")
    )

    # Display results
    print("\n[3/3] Results:")
    print("=" * 80)
    print(f"Username: {result['username']}")
    print(f"Mode: {result['mode']}")
    print(f"Commits analyzed: {result['total_commits_analyzed']}")
    print(f"Files loaded: {result['files_loaded']}")
    print("\nScores:")

    scores = result['scores']
    for dimension, score in scores.items():
        if dimension != "reasoning":
            print(f"  {dimension}: {score}/100")

    if "reasoning" in scores:
        print(f"\nReasoning: {scores['reasoning']}")

    print("\nCommits Summary:")
    summary = result['commits_summary']
    print(f"  Total additions: {summary['total_additions']}")
    print(f"  Total deletions: {summary['total_deletions']}")
    print(f"  Files changed: {summary['files_changed']}")
    print(f"  Languages: {', '.join(summary['languages'])}")
    print("=" * 80)

    # Save result (default to user oscanner home)
    output_dir = get_home_dir() / "evaluations" / "examples"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"{username}_{mode}_evaluation.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to: {output_file}")

    return result


def compare_modes(data_dir: str, username: str, max_commits: int = 30):
    """
    Compare conservative vs moderate evaluation modes

    Args:
        data_dir: Path to extracted data
        username: Username to evaluate
        max_commits: Maximum commits to analyze
    """
    print("\n" + "=" * 80)
    print("COMPARING EVALUATION MODES")
    print("=" * 80)

    # Run conservative evaluation
    print("\n### Conservative Mode (Diffs Only) ###")
    conservative_result = evaluate_from_local_data(
        data_dir=data_dir,
        username=username,
        mode="conservative",
        max_commits=max_commits
    )

    # Run moderate evaluation
    print("\n### Moderate Mode (Diffs + Files) ###")
    moderate_result = evaluate_from_local_data(
        data_dir=data_dir,
        username=username,
        mode="moderate",
        max_commits=max_commits
    )

    # Compare results
    if conservative_result and moderate_result:
        print("\n" + "=" * 80)
        print("COMPARISON")
        print("=" * 80)

        print("\nScore Differences:")
        for dim in conservative_result['scores']:
            if dim != "reasoning":
                cons_score = conservative_result['scores'][dim]
                mod_score = moderate_result['scores'][dim]
                diff = mod_score - cons_score
                symbol = "+" if diff > 0 else ""
                print(f"  {dim}: {cons_score} -> {mod_score} ({symbol}{diff})")

        print("\nFiles Loaded:")
        print(f"  Conservative: {conservative_result['files_loaded']}")
        print(f"  Moderate: {moderate_result['files_loaded']}")


if __name__ == "__main__":
    # Example: Evaluate from the ink-and-memory moderate dataset
    DATA_DIR = "data/shuxueshuxue/ink-and-memory"
    USERNAME = "shuxueshuxue"  # Replace with actual contributor username

    # Option 1: Single evaluation (moderate mode)
    evaluate_from_local_data(
        data_dir=DATA_DIR,
        username=USERNAME,
        mode="moderate",
        max_commits=30
    )

    # Option 2: Compare modes (uncomment to run)
    # compare_modes(
    #     data_dir=DATA_DIR,
    #     username=USERNAME,
    #     max_commits=30
    # )
