#!/usr/bin/env python3
"""
CLI tool to run validation tests on the benchmark dataset
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Add parent directory to path to import evaluator modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluator.validation.validation_runner import ValidationRunner
from evaluator.validation.benchmark_dataset import benchmark_dataset


async def main():
    parser = argparse.ArgumentParser(
        description="Run validation tests on the oscanner evaluation system"
    )

    parser.add_argument(
        "--subset",
        type=str,
        default=None,
        help="Category subset to test (e.g., 'ground_truth', 'famous_developer')"
    )

    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: skip consistency test (faster)"
    )

    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="List all available categories"
    )

    parser.add_argument(
        "--list-repos",
        action="store_true",
        help="List all benchmark repositories"
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show dataset statistics"
    )

    parser.add_argument(
        "--list-runs",
        action="store_true",
        help="List previous validation runs"
    )

    parser.add_argument(
        "--show-run",
        type=str,
        metavar="RUN_ID",
        help="Show details of a specific validation run"
    )

    args = parser.parse_args()

    # Handle info commands
    if args.list_categories:
        categories = benchmark_dataset.get_categories()
        print("\nAvailable categories:")
        for cat in sorted(categories):
            repos = benchmark_dataset.get_by_category(cat)
            print(f"  {cat:30s} ({len(repos)} repos)")
        return

    if args.list_repos:
        repos = benchmark_dataset.get_all()
        print(f"\nBenchmark repositories ({len(repos)} total):\n")
        for repo in repos:
            print(f"  {repo.identifier:50s} | {repo.category:25s} | {repo.skill_level.value if repo.skill_level else 'N/A'}")
        return

    if args.stats:
        stats = benchmark_dataset.get_stats()
        print("\nDataset Statistics:")
        print(f"  Total repositories: {stats['total']}")
        print(f"  Ground truth: {stats['ground_truth']}")
        print(f"  Edge cases: {stats['edge_cases']}")
        print(f"  Categories: {stats['categories']}")
        print(f"  Platforms: {stats['platforms']}")
        print(f"\nBy Skill Level:")
        print(f"  Novice: {stats['novice']}")
        print(f"  Intermediate: {stats['intermediate']}")
        print(f"  Senior: {stats['senior']}")
        print(f"  Architect: {stats['architect']}")
        print(f"  Expert: {stats['expert']}")
        return

    if args.list_runs:
        runner = ValidationRunner(dataset=benchmark_dataset)
        runs = runner.list_validation_runs()
        if not runs:
            print("\nNo validation runs found.")
            return

        print(f"\nValidation Runs ({len(runs)} total):\n")
        for run in runs:
            status = "✅ PASS" if run['passed'] else "❌ FAIL"
            print(f"  {run['run_id']} | {status} | Score: {run['score']:.1f} | Duration: {run['duration']:.1f}s")
        return

    if args.show_run:
        runner = ValidationRunner(dataset=benchmark_dataset)
        run_data = runner.get_validation_run(args.show_run)
        if not run_data:
            print(f"\n❌ Validation run '{args.show_run}' not found")
            return

        print(f"\nValidation Run: {run_data['run_id']}")
        print(f"Timestamp: {run_data['timestamp']}")
        print(f"Overall: {'✅ PASS' if run_data['overall_passed'] else '❌ FAIL'}")
        print(f"Score: {run_data['overall_score']:.1f}/100")
        print(f"Duration: {run_data['duration_seconds']:.1f}s")
        print(f"\nTests:")
        for vr in run_data['validation_results']:
            status = "✅" if vr['passed'] else "❌"
            print(f"  {status} {vr['test_name']:30s} Score: {vr['score']:.1f}")

        return

    # Run validation
    print("\n" + "="*80)
    print("Starting Validation")
    print("="*80)
    print(f"Subset: {args.subset or 'ALL'}")
    print(f"Quick mode: {args.quick}")
    print("="*80 + "\n")

    # Note: We can't actually run evaluations here without the full server context
    # So we'll print instructions instead
    print("⚠️  To run actual validation tests, use the API endpoint:")
    print(f"\n  POST http://localhost:8000/api/benchmark/validate")
    print(f"  Body: {{'subset': '{args.subset}', 'quick_mode': {args.quick}}}")
    print("\nOr use curl:")
    print(f"\n  curl -X POST http://localhost:8000/api/benchmark/validate \\")
    print(f"       -H 'Content-Type: application/json' \\")
    print(f"       -d '{{'\"subset\"': '{args.subset}', '\"quick_mode\"': {str(args.quick).lower()}}}'")
    print("\nMake sure the evaluator server is running:")
    print("  cd evaluator && python server.py\n")


if __name__ == "__main__":
    asyncio.run(main())
