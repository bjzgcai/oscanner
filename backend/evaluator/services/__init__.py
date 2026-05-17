"""Service modules for evaluator business logic."""

from evaluator.services.plugin_service import (
    get_plugins_snapshot,
    resolve_plugin_id,
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
    ensure_repo_evaluation_input_within_limit,
)
from evaluator.services.merge_service import merge_evaluations_logic
from evaluator.services.trajectory_service import (
    analyze_growth_trajectory,
    analyze_group_repositories,
    get_commits_by_date,
)

__all__ = [
    "get_plugins_snapshot",
    "resolve_plugin_id",
    "extract_github_data",
    "extract_gitee_data",
    "fetch_github_commits",
    "fetch_gitee_commits",
    "get_repo_data_dir",
    "get_or_create_evaluator",
    "evaluate_author_incremental",
    "get_empty_evaluation",
    "ensure_repo_evaluation_input_within_limit",
    "merge_evaluations_logic",
    "analyze_growth_trajectory",
    "analyze_group_repositories",
    "get_commits_by_date",
]
