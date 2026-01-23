"""
Validation runner - orchestrates benchmark testing and validation
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field, asdict

from .benchmark_dataset import BenchmarkDataset, TestRepository, benchmark_dataset
from .validators import (
    ValidationResult,
    ConsistencyValidator,
    CorrelationValidator,
    DimensionValidator,
    TemporalValidator,
    OrderingValidator,
)


@dataclass
class BenchmarkEvaluationResult:
    """Result from evaluating a benchmark repository"""
    repo: TestRepository
    overall_score: float
    dimension_scores: Dict[str, float]
    evaluation_data: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "repo": {
                "platform": self.repo.platform,
                "owner": self.repo.owner,
                "repo": self.repo.repo,
                "author": self.repo.author,
                "category": self.repo.category,
                "skill_level": self.repo.skill_level.value if self.repo.skill_level else None,
            },
            "overall_score": self.overall_score,
            "dimension_scores": self.dimension_scores,
            "evaluation_data": self.evaluation_data,
            "timestamp": self.timestamp,
            "error": self.error,
        }


@dataclass
class ValidationRunResult:
    """Complete validation run result"""
    run_id: str
    timestamp: str
    dataset_stats: Dict[str, int]
    evaluation_count: int
    validation_results: List[ValidationResult]
    overall_passed: bool
    overall_score: float
    duration_seconds: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "dataset_stats": self.dataset_stats,
            "evaluation_count": self.evaluation_count,
            "validation_results": [vr.to_dict() for vr in self.validation_results],
            "overall_passed": self.overall_passed,
            "overall_score": self.overall_score,
            "duration_seconds": self.duration_seconds,
        }


class ValidationRunner:
    """
    Orchestrates benchmark evaluation and validation testing
    """

    def __init__(
        self,
        dataset: Optional[BenchmarkDataset] = None,
        evaluation_function=None,
        cache_dir: Optional[Path] = None,
    ):
        """
        Args:
            dataset: BenchmarkDataset instance (uses singleton if None)
            evaluation_function: Async function to evaluate repos (repo_url, author) -> eval_result
            cache_dir: Directory to cache evaluation results
        """
        self.dataset = dataset or benchmark_dataset
        self.evaluation_function = evaluation_function
        self.cache_dir = cache_dir or Path.home() / ".local/share/oscanner/validation_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Initialize validators
        self.validators = [
            ConsistencyValidator(variance_threshold=5.0),
            CorrelationValidator(target_correlation=0.7),
            DimensionValidator(),
            TemporalValidator(),
            OrderingValidator(),
        ]

    def _get_cache_path(self, repo: TestRepository) -> Path:
        """Get cache file path for a repository evaluation"""
        safe_name = f"{repo.platform}_{repo.owner}_{repo.repo}_{repo.author}.json"
        return self.cache_dir / safe_name

    def _load_cached_evaluation(self, repo: TestRepository) -> Optional[BenchmarkEvaluationResult]:
        """Load cached evaluation result if exists"""
        cache_path = self._get_cache_path(repo)
        if cache_path.exists():
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Reconstruct result (simplified - just the data)
                    return data
            except Exception as e:
                print(f"Error loading cache for {repo.identifier}: {e}")
        return None

    def _save_cached_evaluation(self, repo: TestRepository, result: BenchmarkEvaluationResult):
        """Save evaluation result to cache"""
        cache_path = self._get_cache_path(repo)
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving cache for {repo.identifier}: {e}")

    async def evaluate_repository(
        self,
        repo: TestRepository,
        use_cache: bool = True
    ) -> BenchmarkEvaluationResult:
        """
        Evaluate a single benchmark repository

        Args:
            repo: TestRepository to evaluate
            use_cache: Whether to use cached results

        Returns:
            BenchmarkEvaluationResult
        """
        # Check cache first
        if use_cache:
            cached = self._load_cached_evaluation(repo)
            if cached:
                print(f"Using cached result for {repo.identifier}")
                return BenchmarkEvaluationResult(
                    repo=repo,
                    overall_score=cached.get("overall_score", 0),
                    dimension_scores=cached.get("dimension_scores", {}),
                    evaluation_data=cached.get("evaluation_data", {}),
                    timestamp=cached.get("timestamp", ""),
                )

        # Run evaluation
        if self.evaluation_function is None:
            raise ValueError("No evaluation function provided")

        try:
            print(f"Evaluating {repo.identifier}...")
            eval_result = await self.evaluation_function(repo.repo_url, repo.author)

            # Extract scores
            overall_score = eval_result.get("overall_score", 0)
            dimension_scores = {}
            for dim in eval_result.get("dimensions", []):
                dim_name = dim.get("name", "unknown")
                dim_score = dim.get("score", 0)
                dimension_scores[dim_name] = dim_score

            result = BenchmarkEvaluationResult(
                repo=repo,
                overall_score=overall_score,
                dimension_scores=dimension_scores,
                evaluation_data=eval_result,
            )

            # Cache result
            self._save_cached_evaluation(repo, result)

            return result

        except Exception as e:
            print(f"Error evaluating {repo.identifier}: {e}")
            return BenchmarkEvaluationResult(
                repo=repo,
                overall_score=0,
                dimension_scores={},
                evaluation_data={},
                error=str(e),
            )

    async def run_consistency_test(
        self,
        repos: List[TestRepository],
        num_runs: int = 3
    ) -> Dict[str, Any]:
        """
        Run consistency test: evaluate same repos multiple times

        Returns:
            Dict suitable for ConsistencyValidator
        """
        print(f"\n=== Running Consistency Test (n={num_runs}) ===")
        results = {}

        for repo in repos:
            runs = []
            for i in range(num_runs):
                print(f"  Run {i+1}/{num_runs} for {repo.identifier}")
                result = await self.evaluate_repository(repo, use_cache=False)
                runs.append({
                    "overall_score": result.overall_score,
                    "dimensions": result.dimension_scores,
                })

            results[repo.identifier] = {"runs": runs}

        return results

    async def run_correlation_test(
        self,
        repos: List[TestRepository]
    ) -> Dict[str, Any]:
        """
        Run correlation test: compare actual vs expected scores

        Returns:
            Dict suitable for CorrelationValidator
        """
        print(f"\n=== Running Correlation Test ===")
        results = {}

        for repo in repos:
            result = await self.evaluate_repository(repo)

            results[repo.identifier] = {
                "actual_score": result.overall_score,
                "expected_range": repo.expected_score_range,
                "skill_level": repo.skill_level,
            }

        return results

    async def run_dimension_test(
        self,
        repos: List[TestRepository]
    ) -> Dict[str, Any]:
        """
        Run dimension test: check dimension-specific expectations

        Returns:
            Dict suitable for DimensionValidator
        """
        print(f"\n=== Running Dimension Test ===")
        results = {}

        for repo in repos:
            result = await self.evaluate_repository(repo)

            results[repo.identifier] = {
                "actual_dimensions": result.dimension_scores,
                "strong_dimensions": repo.strong_dimensions,
                "weak_dimensions": repo.weak_dimensions,
                "expected_dimension_scores": repo.expected_dimension_scores,
            }

        return results

    async def run_temporal_test(
        self,
        temporal_groups: Dict[str, List[TestRepository]]
    ) -> Dict[str, Any]:
        """
        Run temporal test: check evolution over time

        Returns:
            Dict suitable for TemporalValidator
        """
        print(f"\n=== Running Temporal Evolution Test ===")
        results = {}

        for dev_name, repos in temporal_groups.items():
            timeline = []
            for repo in repos:
                result = await self.evaluate_repository(repo)
                timeline.append({
                    "period": repo.time_period,
                    "score": result.overall_score,
                    "repo_id": repo.identifier,
                })

            results[dev_name] = {"timeline": timeline}

        return results

    async def run_ordering_test(
        self,
        repos: List[TestRepository]
    ) -> Dict[str, Any]:
        """
        Run ordering test: check skill level ordering

        Returns:
            Dict suitable for OrderingValidator
        """
        print(f"\n=== Running Ordering Test ===")
        results = {}

        for repo in repos:
            if repo.skill_level is None:
                continue

            result = await self.evaluate_repository(repo)

            results[repo.identifier] = {
                "score": result.overall_score,
                "skill_level": repo.skill_level,
            }

        return results

    async def run_full_validation(
        self,
        subset: Optional[str] = None,
        quick_mode: bool = False
    ) -> ValidationRunResult:
        """
        Run complete validation suite

        Args:
            subset: Category to test (None = all)
            quick_mode: Skip consistency test (faster)

        Returns:
            ValidationRunResult
        """
        start_time = datetime.utcnow()
        run_id = start_time.strftime("%Y%m%d_%H%M%S")

        print(f"\n{'='*60}")
        print(f"Starting Validation Run: {run_id}")
        print(f"{'='*60}")

        # Get test repositories
        if subset:
            test_repos = self.dataset.get_by_category(subset)
            print(f"Testing category: {subset} ({len(test_repos)} repos)")
        else:
            test_repos = self.dataset.get_all()
            print(f"Testing all categories ({len(test_repos)} repos)")

        validation_results = []

        # 1. Correlation Test (with all repos that have expectations)
        repos_with_expectations = [r for r in test_repos if r.expected_score_range]
        if repos_with_expectations:
            correlation_data = await self.run_correlation_test(repos_with_expectations)
            validator = CorrelationValidator()
            result = await validator.validate(correlation_data)
            validation_results.append(result)
            print(f"\n✓ Correlation Test: {'PASS' if result.passed else 'FAIL'} "
                  f"(score: {result.score:.1f})")

        # 2. Dimension Test
        repos_with_dim_expectations = [
            r for r in test_repos if r.strong_dimensions or r.weak_dimensions
        ]
        if repos_with_dim_expectations:
            dimension_data = await self.run_dimension_test(repos_with_dim_expectations)
            validator = DimensionValidator()
            result = await validator.validate(dimension_data)
            validation_results.append(result)
            print(f"\n✓ Dimension Test: {'PASS' if result.passed else 'FAIL'} "
                  f"(score: {result.score:.1f})")

        # 3. Temporal Test
        temporal_groups = self.dataset.get_temporal_groups()
        if temporal_groups:
            temporal_data = await self.run_temporal_test(temporal_groups)
            validator = TemporalValidator()
            result = await validator.validate(temporal_data)
            validation_results.append(result)
            print(f"\n✓ Temporal Test: {'PASS' if result.passed else 'FAIL'} "
                  f"(score: {result.score:.1f})")

        # 4. Ordering Test
        repos_with_levels = [r for r in test_repos if r.skill_level]
        if repos_with_levels:
            ordering_data = await self.run_ordering_test(repos_with_levels)
            validator = OrderingValidator()
            result = await validator.validate(ordering_data)
            validation_results.append(result)
            print(f"\n✓ Ordering Test: {'PASS' if result.passed else 'FAIL'} "
                  f"(score: {result.score:.1f})")

        # 5. Consistency Test (optional, slow)
        if not quick_mode:
            # Test consistency on a small subset
            consistency_sample = test_repos[:5]  # Just 5 repos
            consistency_data = await self.run_consistency_test(consistency_sample, num_runs=3)
            validator = ConsistencyValidator()
            result = await validator.validate(consistency_data)
            validation_results.append(result)
            print(f"\n✓ Consistency Test: {'PASS' if result.passed else 'FAIL'} "
                  f"(score: {result.score:.1f})")

        # Calculate overall results
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        overall_passed = all(vr.passed for vr in validation_results)
        overall_score = sum(vr.score for vr in validation_results) / len(validation_results) if validation_results else 0

        result = ValidationRunResult(
            run_id=run_id,
            timestamp=start_time.isoformat(),
            dataset_stats=self.dataset.get_stats(),
            evaluation_count=len(test_repos),
            validation_results=validation_results,
            overall_passed=overall_passed,
            overall_score=overall_score,
            duration_seconds=duration,
        )

        # Print summary
        print(f"\n{'='*60}")
        print(f"Validation Run Complete")
        print(f"{'='*60}")
        print(f"Overall: {'✅ PASS' if overall_passed else '❌ FAIL'}")
        print(f"Score: {overall_score:.1f}/100")
        print(f"Duration: {duration:.1f}s")
        print(f"Tests Run: {len(validation_results)}")
        print(f"Tests Passed: {sum(1 for vr in validation_results if vr.passed)}")

        # Save results
        self._save_run_result(result)

        return result

    def _save_run_result(self, result: ValidationRunResult):
        """Save validation run result to disk"""
        results_dir = self.cache_dir / "runs"
        results_dir.mkdir(exist_ok=True)

        result_path = results_dir / f"{result.run_id}.json"
        try:
            with open(result_path, 'w', encoding='utf-8') as f:
                json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
            print(f"\nResults saved to: {result_path}")
        except Exception as e:
            print(f"Error saving results: {e}")

    def list_validation_runs(self) -> List[Dict[str, Any]]:
        """List all previous validation runs"""
        results_dir = self.cache_dir / "runs"
        if not results_dir.exists():
            return []

        runs = []
        for result_file in sorted(results_dir.glob("*.json"), reverse=True):
            try:
                with open(result_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    runs.append({
                        "run_id": data.get("run_id"),
                        "timestamp": data.get("timestamp"),
                        "passed": data.get("overall_passed"),
                        "score": data.get("overall_score"),
                        "duration": data.get("duration_seconds"),
                    })
            except Exception as e:
                print(f"Error loading {result_file}: {e}")

        return runs

    def get_validation_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed results for a specific validation run"""
        results_dir = self.cache_dir / "runs"
        result_path = results_dir / f"{run_id}.json"

        if not result_path.exists():
            return None

        try:
            with open(result_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading run {run_id}: {e}")
            return None
