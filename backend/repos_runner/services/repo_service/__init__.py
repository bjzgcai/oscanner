"""
Repository service package.
"""

from .paths import (
    get_clone_source_dir,
    get_clone_source_dir_for_url,
    get_repos_dir,
    parse_repo_url,
    parse_repo_url_with_ref,
    repo_key_from_source_dir,
    repo_storage_key,
    source_dir_from_repo_key,
    fetch_gitee_tag_message,
    workspace_dir_from_repo_key,
)
from .llm import (
    _get_api_client,
    _message_text_content,
    _messages_create_with_fallback,
    DEFAULT_OPENROUTER_BASE_URL,
)
from .clone import clone_repository
from .venv import ensure_repo_venv, get_repo_venv_dir
from .detection import (
    detect_test_commands,
    _detect_frameworks_statically,
    _load_test_config,
    _save_test_config,
    _detect_commands_via_llm,
    _FRAMEWORK_MAP,
)
from .explore import explore_repository, _explore_via_messages_api, _build_repo_context
from .parsing import (
    _parse_json_report,
    _parse_go_json_report,
    _parse_test_output_with_regex,
    _parse_test_output_with_llm,
    _parse_test_output,
)
from .coverage import _extract_features_from_tag_message, _check_feature_coverage
from .report import _generate_test_report
from .runtime_evidence import collect_runtime_evidence, merge_runtime_feature_coverage
from .runtime_env import build_runtime_env_context, detect_required_env_keys
from .runner import run_tests
from .lifecycle import list_repos, delete_repo

__all__ = [
    # paths
    "get_clone_source_dir",
    "get_clone_source_dir_for_url",
    "get_repos_dir",
    "parse_repo_url",
    "parse_repo_url_with_ref",
    "repo_key_from_source_dir",
    "repo_storage_key",
    "source_dir_from_repo_key",
    "fetch_gitee_tag_message",
    "workspace_dir_from_repo_key",
    # llm
    "DEFAULT_OPENROUTER_BASE_URL",
    "_get_api_client",
    "_message_text_content",
    "_messages_create_with_fallback",
    # clone
    "clone_repository",
    # venv
    "ensure_repo_venv",
    "get_repo_venv_dir",
    # detection
    "_FRAMEWORK_MAP",
    "_detect_frameworks_statically",
    "_load_test_config",
    "_save_test_config",
    "detect_test_commands",
    "_detect_commands_via_llm",
    # explore
    "explore_repository",
    "_explore_via_messages_api",
    "_build_repo_context",
    # parsing
    "_parse_json_report",
    "_parse_go_json_report",
    "_parse_test_output_with_regex",
    "_parse_test_output_with_llm",
    "_parse_test_output",
    # coverage
    "_extract_features_from_tag_message",
    "_check_feature_coverage",
    # report
    "_generate_test_report",
    # runtime evidence
    "collect_runtime_evidence",
    "merge_runtime_feature_coverage",
    "build_runtime_env_context",
    "detect_required_env_keys",
    # runner
    "run_tests",
    # lifecycle
    "list_repos",
    "delete_repo",
]
