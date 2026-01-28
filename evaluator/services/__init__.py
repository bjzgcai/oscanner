"""Service modules for evaluator business logic."""

from evaluator.services.plugin_service import (
    get_plugins_snapshot,
    resolve_plugin_id,
    get_evaluation_cache_path,
)
from evaluator.services.extraction_service import (
    extract_github_data,
    extract_gitee_data,
    fetch_github_commits,
    fetch_gitee_commits,
    get_repo_data_dir,
)
from evaluator.services.evaluation_service import (
    get_or_create_evaluator,
    evaluate_author_incremental,
    get_empty_evaluation,
)
from evaluator.services.merge_service import merge_evaluations_logic
from evaluator.services.trajectory_service import (
    load_trajectory_cache,
    save_trajectory_cache,
    analyze_growth_trajectory,
    get_commits_by_date,
)

__all__ = [
    "get_plugins_snapshot",
    "resolve_plugin_id",
    "get_evaluation_cache_path",
    "extract_github_data",
    "extract_gitee_data",
    "fetch_github_commits",
    "fetch_gitee_commits",
    "get_repo_data_dir",
    "get_or_create_evaluator",
    "evaluate_author_incremental",
    "get_empty_evaluation",
    "merge_evaluations_logic",
    "load_trajectory_cache",
    "save_trajectory_cache",
    "analyze_growth_trajectory",
    "get_commits_by_date",
]
