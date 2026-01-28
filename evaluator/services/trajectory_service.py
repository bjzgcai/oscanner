"""Trajectory service for managing user growth tracking."""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta

from evaluator.paths import get_trajectory_cache_path, get_platform_data_dir
from evaluator.config import get_llm_api_key
from evaluator.schemas import (
    TrajectoryCache,
    TrajectoryCheckpoint,
    CommitsRange,
    TrajectoryResponse,
    EvaluationSchema,
    PeriodAccumulationState,
)
from evaluator.utils import load_commits_from_local, is_commit_by_author
from evaluator.services.evaluation_service import get_or_create_evaluator
from evaluator.services.extraction_service import extract_github_data, extract_gitee_data
from evaluator.plugin_registry import load_scan_module


def load_trajectory_cache(username: str) -> Optional[TrajectoryCache]:
    """
    Load trajectory cache from disk.

    Args:
        username: Username to load trajectory for

    Returns:
        TrajectoryCache if exists, None otherwise
    """
    cache_path = get_trajectory_cache_path(username)

    if not cache_path.exists():
        return None

    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return TrajectoryCache(**data)
    except Exception as e:
        print(f"[Trajectory] Failed to load cache for {username}: {e}")
        return None


def save_trajectory_cache(trajectory: TrajectoryCache) -> None:
    """
    Save trajectory cache to disk with atomic write.

    Args:
        trajectory: TrajectoryCache to save
    """
    cache_path = get_trajectory_cache_path(trajectory.username)
    tmp_path = cache_path.with_suffix('.json.tmp')

    try:
        # Write to temp file first
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(trajectory.model_dump(), f, indent=2, ensure_ascii=False)

        # Atomic rename
        tmp_path.rename(cache_path)
        print(f"[Trajectory] Saved cache for {trajectory.username} with {trajectory.total_checkpoints} checkpoints")
    except Exception as e:
        print(f"[Trajectory] Failed to save cache: {e}")
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def parse_repo_url(repo_url: str) -> Tuple[str, str, str]:
    """
    Parse repository URL to extract platform, owner, and repo name.

    Args:
        repo_url: Repository URL (GitHub or Gitee)

    Returns:
        Tuple of (platform, owner, repo)
    """
    import re

    # GitHub patterns
    github_patterns = [
        r'https?://(?:www\.)?github\.com/([^/]+)/([^/\s]+?)(?:\.git)?/?$',
        r'github\.com/([^/]+)/([^/\s]+?)(?:\.git)?/?$',
        r'git@github\.com:([^/]+)/([^/\s]+?)(?:\.git)?$',
    ]

    for pattern in github_patterns:
        match = re.match(pattern, repo_url.strip())
        if match:
            return ('github', match.group(1), match.group(2))

    # Gitee patterns
    gitee_patterns = [
        r'https?://(?:www\.)?gitee\.com/([^/]+)/([^/\s]+?)(?:\.git)?/?$',
        r'gitee\.com/([^/]+)/([^/\s]+?)(?:\.git)?/?$',
        r'git@gitee\.com:([^/]+)/([^/\s]+?)(?:\.git)?$',
    ]

    for pattern in gitee_patterns:
        match = re.match(pattern, repo_url.strip())
        if match:
            return ('gitee', match.group(1), match.group(2))

    raise ValueError(f"Unable to parse repository URL: {repo_url}")


def ensure_repo_data_synced(repo_url: str, max_commits: int = 500) -> Tuple[str, str, str, bool]:
    """
    Ensure repository data is synced locally. If not present or stale, extract it.

    Args:
        repo_url: Repository URL
        max_commits: Maximum commits to fetch

    Returns:
        Tuple of (platform, owner, repo, was_synced)
        was_synced is True if data was freshly extracted

    Raises:
        Exception if extraction fails
    """
    platform, owner, repo = parse_repo_url(repo_url)
    data_dir = get_platform_data_dir(platform, owner, repo)

    # Check if data already exists
    commits_index = data_dir / "commits_index.json"
    data_exists = commits_index.exists()

    if data_exists:
        print(f"[Trajectory] Found existing data for {platform}/{owner}/{repo}")
        return platform, owner, repo, False

    # Extract data
    print(f"[Trajectory] No local data found for {platform}/{owner}/{repo}, extracting...")

    if platform == "github":
        success = extract_github_data(owner, repo)
    elif platform == "gitee":
        success = extract_gitee_data(owner, repo, max_commits=max_commits)
    else:
        raise ValueError(f"Unsupported platform: {platform}")

    if not success:
        raise Exception(f"Failed to extract data from {repo_url}")

    print(f"[Trajectory] Successfully extracted data for {platform}/{owner}/{repo}")
    return platform, owner, repo, True



def get_new_commits_from_repos(
    repo_urls: List[str],
    username: str,
    aliases: List[str],
    last_synced_sha: Optional[str]
) -> Tuple[int, List[Dict[str, Any]], List[str]]:
    """
    Get new commits from all tracked repositories.

    Args:
        repo_urls: List of repository URLs
        username: Primary username
        aliases: List of author aliases (including username)
        last_synced_sha: SHA of last synced commit (None for first analysis)

    Returns:
        Tuple of (new_commits_count, new_commits_list, repos_analyzed)
    """
    all_commits = []
    repos_analyzed = []

    # Normalize aliases
    normalized_aliases = [alias.lower().strip() for alias in aliases if alias]
    if username.lower() not in normalized_aliases:
        normalized_aliases.append(username.lower())

    for repo_url in repo_urls:
        try:
            platform, owner, repo = parse_repo_url(repo_url)
            data_dir = get_platform_data_dir(platform, owner, repo)

            if not data_dir.exists():
                print(f"[Trajectory] Warning: No local data for {repo_url}")
                continue

            # Load all commits (they are ordered newest first)
            commits = load_commits_from_local(data_dir, limit=None)
            if not commits:
                print(f"[Trajectory] No commits loaded from {platform}/{owner}/{repo}")
                continue

            # Filter by author
            author_commits = [
                c for c in commits
                if any(is_commit_by_author(c, alias) for alias in normalized_aliases)
            ]

            print(f"[Trajectory] Loaded {len(commits)} total commits, {len(author_commits)} by {username} in {platform}/{owner}/{repo}")

            # If last_synced_sha exists, only take commits after it
            if last_synced_sha:
                new_commits = []
                for commit in author_commits:
                    commit_sha = commit.get('sha') or commit.get('hash')
                    if commit_sha == last_synced_sha:
                        break
                    new_commits.append(commit)
                print(f"[Trajectory] {len(new_commits)} new commits since {last_synced_sha[:8]}")
                all_commits.extend(new_commits)
            else:
                all_commits.extend(author_commits)

            repos_analyzed.append(repo_url)

        except Exception as e:
            print(f"[Trajectory] Error processing {repo_url}: {e}")
            continue

    # Sort all commits by date (newest first)
    all_commits.sort(
        key=lambda c: c.get('commit', {}).get('author', {}).get('date', '') or c.get('date', ''),
        reverse=True
    )

    return len(all_commits), all_commits, repos_analyzed


def create_checkpoint_evaluation(
    commits: List[Dict[str, Any]],
    username: str,
    checkpoint_id: int,
    plugin_id: str,
    model: str,
    language: str,
    repos_analyzed: List[str],
    aliases_used: List[str],
    repo_start_date: Optional[datetime] = None,
    previous_checkpoint: Optional[TrajectoryCheckpoint] = None,
    parallel_chunking: bool = True,
    max_parallel_workers: int = 3
) -> TrajectoryCheckpoint:
    """
    Create a checkpoint by evaluating commits (10+ commits).

    Args:
        commits: List of commits (10+ commits, ordered newest first)
        username: Username being evaluated
        checkpoint_id: Sequential checkpoint ID
        plugin_id: Plugin to use for evaluation
        model: LLM model to use
        language: Language for evaluation
        repos_analyzed: List of repo URLs analyzed
        aliases_used: List of aliases used in filtering
        repo_start_date: Repository start date (for period metadata)
        previous_checkpoint: Previous checkpoint for comparison
        parallel_chunking: Enable parallel chunking
        max_parallel_workers: Max parallel workers

    Returns:
        TrajectoryCheckpoint with evaluation result
    """
    if len(commits) < 10:
        raise ValueError(f"Need at least 10 commits for checkpoint, got {len(commits)}")

    # Sort commits oldest to newest for analysis
    sorted_commits = sorted(
        commits,
        key=lambda c: c.get('commit', {}).get('author', {}).get('date', '') or c.get('date', ''),
        reverse=False
    )

    # Extract commit range (oldest to newest)
    start_sha = sorted_commits[0].get('sha') or sorted_commits[0].get('hash')
    end_sha = sorted_commits[-1].get('sha') or sorted_commits[-1].get('hash')

    # Build period metadata
    if repo_start_date:
        period_start, period_end, accumulated_periods = build_period_metadata(sorted_commits, repo_start_date)
    else:
        period_start = None
        period_end = None
        accumulated_periods = 1

    # Create a temporary "platform" for evaluation
    # Use the first repo URL to determine platform
    if repos_analyzed:
        platform, owner, repo = parse_repo_url(repos_analyzed[0])
    else:
        platform, owner, repo = 'github', 'unknown', 'unknown'

    # Create evaluator with previous checkpoint context
    # Extract previous scores if available
    previous_scores = None
    if previous_checkpoint:
        previous_scores = previous_checkpoint.evaluation.scores.model_dump()
        print(f"[Trajectory] Passing previous checkpoint scores to evaluator: {list(previous_scores.keys())}")

    # Load scan module and create evaluator
    meta, scan_mod, _ = load_scan_module(plugin_id)

    # Create evaluator with previous checkpoint scores support
    evaluator = scan_mod.create_commit_evaluator(
        data_dir=str(get_platform_data_dir(platform, owner, repo)),
        api_key=get_llm_api_key(),
        model=model,
        mode="moderate",
        parallel_chunking=parallel_chunking,
        max_parallel_workers=max_parallel_workers,
        previous_checkpoint_scores=previous_scores,
    )

    # Evaluate
    print(f"[Trajectory] Evaluating checkpoint {checkpoint_id} with {len(commits)} commits (previous_checkpoint: {previous_checkpoint.checkpoint_id if previous_checkpoint else 'None'})")
    evaluation_result = evaluator.evaluate_engineer(
        commits=sorted_commits,
        username=username,
        max_commits=len(commits),
        load_files=True,
        use_chunking=True
    )

    # Debug: Check type of evaluation_result
    print(f"[Trajectory] evaluation_result type: {type(evaluation_result)}")
    print(f"[Trajectory] evaluation_result keys: {list(evaluation_result.keys()) if isinstance(evaluation_result, dict) else 'NOT A DICT'}")

    # Ensure evaluation_result is a dict
    if not isinstance(evaluation_result, dict):
        raise TypeError(f"Expected dict from evaluate_engineer, got {type(evaluation_result)}")

    # Add required metadata fields
    evaluation_result['evaluated_at'] = datetime.utcnow().isoformat()
    evaluation_result['plugin'] = plugin_id

    # Load plugin version
    try:
        meta, _, _ = load_scan_module(plugin_id)
        evaluation_result['plugin_version'] = meta.version
    except Exception as e:
        print(f"[Trajectory] Warning: Failed to load plugin version: {e}")
        evaluation_result['plugin_version'] = '0.1.0'

    # Convert to EvaluationSchema
    try:
        evaluation = EvaluationSchema(**evaluation_result)
    except Exception as e:
        print(f"[Trajectory] Validation error details:")
        print(f"[Trajectory] evaluation_result keys: {list(evaluation_result.keys())}")
        print(f"[Trajectory] evaluation_result: {json.dumps(evaluation_result, indent=2, default=str)}")
        raise

    # Calculate growth comparison if previous checkpoint exists
    growth_comparison = None
    if previous_checkpoint:
        growth_comparison = calculate_growth_comparison(
            current_scores=evaluation.scores.model_dump(),
            previous_scores=previous_checkpoint.evaluation.scores.model_dump()
        )

    # Create checkpoint
    checkpoint = TrajectoryCheckpoint(
        checkpoint_id=checkpoint_id,
        created_at=datetime.utcnow().isoformat(),
        commits_range=CommitsRange(
            start_sha=start_sha,
            end_sha=end_sha,
            commit_count=len(commits),
            period_start=period_start,
            period_end=period_end,
            accumulated_from_periods=accumulated_periods
        ),
        evaluation=evaluation,
        repos_analyzed=repos_analyzed,
        aliases_used=aliases_used,
        previous_checkpoint_id=previous_checkpoint.checkpoint_id if previous_checkpoint else None,
        growth_comparison=growth_comparison
    )

    return checkpoint


def calculate_growth_comparison(
    current_scores: Dict[str, Any],
    previous_scores: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Calculate growth comparison metrics between current and previous scores.

    Args:
        current_scores: Current evaluation scores
        previous_scores: Previous evaluation scores

    Returns:
        Dictionary with growth comparison metrics
    """
    dimension_changes = {}
    improved_dimensions = []
    regressed_dimensions = []

    # Compare each dimension
    for key in current_scores.keys():
        if key == 'reasoning':
            continue

        current_val = current_scores.get(key)
        previous_val = previous_scores.get(key)

        # Only compare if both have numeric values
        if isinstance(current_val, (int, float)) and isinstance(previous_val, (int, float)):
            change = current_val - previous_val
            dimension_changes[key] = change

            if change > 0:
                improved_dimensions.append(key)
            elif change < 0:
                regressed_dimensions.append(key)

    # Determine overall trend
    if improved_dimensions and not regressed_dimensions:
        overall_trend = "increasing"
    elif regressed_dimensions and not improved_dimensions:
        overall_trend = "decreasing"
    elif improved_dimensions and regressed_dimensions:
        # Mixed: determine by magnitude
        total_improvement = sum(dimension_changes[d] for d in improved_dimensions)
        total_regression = sum(abs(dimension_changes[d]) for d in regressed_dimensions)
        if total_improvement > total_regression:
            overall_trend = "increasing"
        elif total_regression > total_improvement:
            overall_trend = "decreasing"
        else:
            overall_trend = "stable"
    else:
        overall_trend = "stable"

    return {
        "dimension_changes": dimension_changes,
        "overall_trend": overall_trend,
        "improved_dimensions": improved_dimensions,
        "regressed_dimensions": regressed_dimensions
    }


def get_commits_by_date(
    username: str,
    repo_urls: List[str],
    aliases: List[str]
) -> List[Dict[str, Any]]:
    """
    Get commits grouped by date for visualization.

    Args:
        username: Primary username
        repo_urls: List of repository URLs
        aliases: List of author name aliases

    Returns:
        List of {date: "YYYY-MM-DD", count: int} sorted by date
    """
    from collections import defaultdict

    # Normalize aliases
    normalized_aliases = [alias.lower().strip() for alias in aliases if alias]
    if username.lower() not in normalized_aliases:
        normalized_aliases.append(username.lower())

    # Collect all commits by date
    commits_by_date = defaultdict(int)

    for repo_url in repo_urls:
        try:
            platform, owner, repo = parse_repo_url(repo_url)
            data_dir = get_platform_data_dir(platform, owner, repo)

            if not data_dir.exists():
                print(f"[Trajectory] Warning: No local data for {repo_url}")
                continue

            # Load commits_list.json directly (contains all commits)
            commits_list_path = data_dir / "commits_list.json"
            if not commits_list_path.exists():
                print(f"[Trajectory] Warning: commits_list.json not found in {data_dir}")
                continue

            with open(commits_list_path, 'r', encoding='utf-8') as f:
                commits = json.load(f)

            if not commits:
                continue

            # Filter by author and group by date
            for commit in commits:
                # Check if commit is by this author
                if not any(is_commit_by_author(commit, alias) for alias in normalized_aliases):
                    continue

                # Extract date from commit.author.date
                commit_data = commit.get('commit', {})
                author_data = commit_data.get('author', {})
                date_str = author_data.get('date', '')

                if not date_str:
                    continue

                # Parse ISO 8601 date and extract YYYY-MM-DD
                try:
                    date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    date_only = date_obj.strftime('%Y-%m-%d')
                    commits_by_date[date_only] += 1
                except Exception as e:
                    print(f"[Trajectory] Warning: Failed to parse date {date_str}: {e}")
                    continue

        except Exception as e:
            print(f"[Trajectory] Error processing {repo_url}: {e}")
            continue

    # Convert to sorted list
    result = [
        {"date": date, "count": count}
        for date, count in sorted(commits_by_date.items())
    ]

    print(f"[Trajectory] Found {len(result)} days with commits for {username}")
    return result


def get_repo_start_date(
    repo_urls: List[str],
    username: str,
    aliases: List[str]
) -> Optional[datetime]:
    """
    Get the earliest commit date across all tracked repositories.

    Args:
        repo_urls: List of repository URLs
        username: Primary username
        aliases: List of author aliases

    Returns:
        Datetime of earliest commit, or None if no commits found
    """
    # Normalize aliases
    normalized_aliases = [alias.lower().strip() for alias in aliases if alias]
    if username.lower() not in normalized_aliases:
        normalized_aliases.append(username.lower())

    earliest_date = None

    for repo_url in repo_urls:
        try:
            platform, owner, repo = parse_repo_url(repo_url)
            data_dir = get_platform_data_dir(platform, owner, repo)

            if not data_dir.exists():
                print(f"[Trajectory] Warning: No local data for {repo_url}")
                continue

            # Load commits
            commits = load_commits_from_local(data_dir, limit=None)
            if not commits:
                continue

            # Filter by author
            author_commits = [
                c for c in commits
                if any(is_commit_by_author(c, alias) for alias in normalized_aliases)
            ]

            if not author_commits:
                continue

            # Find oldest commit (commits are ordered newest first)
            oldest_commit = author_commits[-1]
            commit_data = oldest_commit.get('commit', {})
            author_data = commit_data.get('author', {})
            date_str = author_data.get('date', '') or oldest_commit.get('date', '')

            if not date_str:
                continue

            # Parse ISO 8601 date
            try:
                commit_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                if earliest_date is None or commit_date < earliest_date:
                    earliest_date = commit_date
                    print(f"[Trajectory] Found earliest commit in {platform}/{owner}/{repo}: {commit_date.isoformat()}")
            except Exception as e:
                print(f"[Trajectory] Warning: Failed to parse date {date_str}: {e}")
                continue

        except Exception as e:
            print(f"[Trajectory] Error processing {repo_url}: {e}")
            continue

    return earliest_date


def group_commits_by_period(
    commits: List[Dict[str, Any]],
    repo_start_date: datetime,
    accumulated_shas: List[str] = None
) -> Tuple[List[List[Dict[str, Any]]], List[str], int]:
    """
    Group commits into 2-week periods with 10-commit minimum threshold.

    Args:
        commits: List of commits (ordered newest first)
        repo_start_date: Start date of repository (earliest commit)
        accumulated_shas: Previously accumulated commit SHAs (for incremental updates)

    Returns:
        Tuple of (checkpoint_groups, remaining_commit_shas, periods_accumulated)
        - checkpoint_groups: List of commit groups ready for evaluation (each has 10+ commits)
        - remaining_commit_shas: SHAs of commits not yet forming a checkpoint
        - periods_accumulated: Number of periods that contributed to the last checkpoint
    """
    # Sort commits oldest to newest (chronological order)
    sorted_commits = sorted(
        commits,
        key=lambda c: c.get('commit', {}).get('author', {}).get('date', '') or c.get('date', ''),
        reverse=False
    )

    # Initialize accumulation buffer with previously accumulated commits
    if accumulated_shas:
        # Find previously accumulated commits in the sorted list
        accumulated_commits = [c for c in sorted_commits if (c.get('sha') or c.get('hash')) in accumulated_shas]
        # Remove them from sorted list to avoid double-counting
        sorted_commits = [c for c in sorted_commits if (c.get('sha') or c.get('hash')) not in accumulated_shas]
        print(f"[Trajectory] Loaded {len(accumulated_commits)} previously accumulated commits")
    else:
        accumulated_commits = []

    checkpoint_groups = []

    # Group commits by 2-week periods
    periods = {}  # {period_index: [commits]}
    for commit in sorted_commits:
        # Get commit date
        commit_data = commit.get('commit', {})
        author_data = commit_data.get('author', {})
        date_str = author_data.get('date', '') or commit.get('date', '')

        if not date_str:
            print(f"[Trajectory] Warning: Commit without date, skipping")
            continue

        try:
            commit_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except Exception as e:
            print(f"[Trajectory] Warning: Failed to parse date {date_str}: {e}")
            continue

        # Calculate which 2-week period this commit falls into
        days_from_start = (commit_date - repo_start_date).days
        period_index = days_from_start // 14

        if period_index not in periods:
            periods[period_index] = []
        periods[period_index].append(commit)

    # Process periods in order
    periods_accumulated = 0
    for period_index in sorted(periods.keys()):
        period_commits = periods[period_index]

        # Add period commits to accumulation
        accumulated_commits.extend(period_commits)
        periods_accumulated += 1

        print(f"[Trajectory] Period {period_index}: added {len(period_commits)} commits (total accumulated: {len(accumulated_commits)})")

        # Check if we have enough commits for a checkpoint
        if len(accumulated_commits) >= 10:
            # Create checkpoint with ALL accumulated commits
            checkpoint_groups.append(accumulated_commits.copy())
            print(f"[Trajectory] Created checkpoint group with {len(accumulated_commits)} commits (accumulated from {periods_accumulated} periods)")

            # Reset accumulation
            accumulated_commits = []
            periods_accumulated = 0

    # Extract SHAs of remaining commits
    remaining_shas = [(c.get('sha') or c.get('hash')) for c in accumulated_commits]

    print(f"[Trajectory] Grouping complete: {len(checkpoint_groups)} checkpoint groups, {len(remaining_shas)} commits remaining")

    return checkpoint_groups, remaining_shas, periods_accumulated


def build_period_metadata(
    commits: List[Dict[str, Any]],
    repo_start_date: datetime
) -> Tuple[str, str, int]:
    """
    Build period metadata for a checkpoint.

    Args:
        commits: List of commits in the checkpoint
        repo_start_date: Start date of repository

    Returns:
        Tuple of (period_start, period_end, accumulated_from_periods)
    """
    # Find earliest and latest commit dates
    dates = []
    for commit in commits:
        commit_data = commit.get('commit', {})
        author_data = commit_data.get('author', {})
        date_str = author_data.get('date', '') or commit.get('date', '')

        if date_str:
            try:
                commit_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                dates.append(commit_date)
            except Exception:
                continue

    if not dates:
        # Fallback: use repo start date
        period_start = repo_start_date
        period_end = repo_start_date + timedelta(weeks=2)
        return period_start.isoformat(), period_end.isoformat(), 1

    earliest = min(dates)
    latest = max(dates)

    # Calculate which period the earliest commit falls into
    weeks_from_start = (earliest - repo_start_date).days // 14
    period_start = repo_start_date + timedelta(weeks=2 * weeks_from_start)

    # Calculate which period the latest commit falls into
    weeks_from_start_latest = (latest - repo_start_date).days // 14
    period_end_latest = repo_start_date + timedelta(weeks=2 * (weeks_from_start_latest + 1))

    # Number of periods spanned
    periods_spanned = weeks_from_start_latest - weeks_from_start + 1

    return period_start.isoformat(), period_end_latest.isoformat(), periods_spanned


def analyze_growth_trajectory(
    username: str,
    repo_urls: List[str],
    aliases: List[str],
    plugin_id: str,
    model: str,
    language: str,
    use_cache: bool = True,
    parallel_chunking: bool = True,
    max_parallel_workers: int = 3
) -> TrajectoryResponse:
    """
    Main orchestration function for growth trajectory analysis.

    Args:
        username: Primary username
        repo_urls: List of repository URLs to track
        aliases: List of author name aliases
        plugin_id: Plugin to use for evaluation
        model: LLM model to use
        language: Language for evaluation
        use_cache: Whether to use cached trajectory
        parallel_chunking: Enable parallel chunking
        max_parallel_workers: Max parallel workers

    Returns:
        TrajectoryResponse with analysis results
    """
    # Load existing trajectory
    trajectory = load_trajectory_cache(username) if use_cache else None

    if trajectory is None:
        print(f"[Trajectory] No cache found for {username}, initializing")
        trajectory = TrajectoryCache(
            username=username,
            repo_urls=repo_urls,
            checkpoints=[],
            last_synced_sha=None,
            last_synced_at=None,
            total_checkpoints=0
        )
    else:
        # Update repo URLs
        trajectory.repo_urls = repo_urls

    # Ensure all repos have data synced
    print(f"[Trajectory] Ensuring data is synced for {len(repo_urls)} repositories")
    for repo_url in repo_urls:
        try:
            platform, owner, repo, was_synced = ensure_repo_data_synced(repo_url, max_commits=500)
            if was_synced:
                print(f"[Trajectory] Extracted fresh data for {platform}/{owner}/{repo}")
        except Exception as e:
            print(f"[Trajectory] Warning: Failed to sync {repo_url}: {e}")
            # Continue with other repos even if one fails

    # Get new commits
    new_commits_count, new_commits, repos_analyzed = get_new_commits_from_repos(
        repo_urls=repo_urls,
        username=username,
        aliases=aliases,
        last_synced_sha=trajectory.last_synced_sha
    )

    print(f"[Trajectory] Found {new_commits_count} new commits (last_synced_sha: {trajectory.last_synced_sha})")

    # Get or calculate repo start date
    if trajectory.repo_start_date:
        repo_start_date = datetime.fromisoformat(trajectory.repo_start_date)
        print(f"[Trajectory] Using cached repo_start_date: {repo_start_date.date()}")
    else:
        repo_start_date = get_repo_start_date(repo_urls, username, aliases)
        if repo_start_date:
            trajectory.repo_start_date = repo_start_date.isoformat()
            print(f"[Trajectory] Calculated repo_start_date: {repo_start_date.date()}")
        else:
            print(f"[Trajectory] Warning: Could not determine repo start date")
            return TrajectoryResponse(
                success=False,
                trajectory=trajectory,
                new_checkpoint_created=False,
                message="Could not determine repository start date",
                commits_pending=new_commits_count
            )

    # Group commits by period with accumulation logic
    accumulated_shas = trajectory.accumulation_state.accumulated_commits if trajectory.accumulation_state else []
    checkpoint_groups, remaining_shas, _ = group_commits_by_period(
        commits=new_commits,
        repo_start_date=repo_start_date,
        accumulated_shas=accumulated_shas
    )

    print(f"[Trajectory] Grouped into {len(checkpoint_groups)} checkpoint groups, {len(remaining_shas)} commits remaining")

    # Check if we have any checkpoint groups
    if not checkpoint_groups:
        # Update accumulation state
        current_period_start = repo_start_date
        weeks_elapsed = (datetime.now(repo_start_date.tzinfo) - repo_start_date).days // 14
        current_period_start = repo_start_date + timedelta(weeks=2 * weeks_elapsed)
        current_period_end = current_period_start + timedelta(weeks=2)

        trajectory.accumulation_state = PeriodAccumulationState(
            current_period_start=current_period_start.isoformat(),
            current_period_end=current_period_end.isoformat(),
            accumulated_commits=remaining_shas,
            repo_start_date=repo_start_date.isoformat()
        )

        # Save state
        save_trajectory_cache(trajectory)

        return TrajectoryResponse(
            success=True,
            trajectory=trajectory,
            new_checkpoint_created=False,
            message=f"Accumulated {len(remaining_shas)} commits. Need 10 commits to create checkpoint.",
            commits_pending=len(remaining_shas)
        )

    # Create checkpoints for each group
    checkpoints_created = 0
    commits_processed = 0

    try:
        for group_commits in checkpoint_groups:
            # Get previous checkpoint for comparison
            previous_checkpoint = trajectory.checkpoints[-1] if trajectory.checkpoints else None

            checkpoint = create_checkpoint_evaluation(
                commits=group_commits,
                username=username,
                checkpoint_id=trajectory.total_checkpoints + 1,
                plugin_id=plugin_id,
                model=model,
                language=language,
                repos_analyzed=repos_analyzed,
                aliases_used=aliases,
                repo_start_date=repo_start_date,
                previous_checkpoint=previous_checkpoint,
                parallel_chunking=parallel_chunking,
                max_parallel_workers=max_parallel_workers
            )

            # Update trajectory
            trajectory.checkpoints.append(checkpoint)
            trajectory.total_checkpoints += 1
            trajectory.last_synced_sha = checkpoint.commits_range.end_sha
            trajectory.last_synced_at = checkpoint.created_at

            commits_processed += len(group_commits)
            checkpoints_created += 1

            print(f"[Trajectory] Created checkpoint {checkpoint.checkpoint_id} with {len(group_commits)} commits ({commits_processed} commits processed)")

        # Update accumulation state with remaining commits
        current_period_start = repo_start_date
        weeks_elapsed = (datetime.now(repo_start_date.tzinfo) - repo_start_date).days // 14
        current_period_start = repo_start_date + timedelta(weeks=2 * weeks_elapsed)
        current_period_end = current_period_start + timedelta(weeks=2)

        trajectory.accumulation_state = PeriodAccumulationState(
            current_period_start=current_period_start.isoformat(),
            current_period_end=current_period_end.isoformat(),
            accumulated_commits=remaining_shas,
            repo_start_date=repo_start_date.isoformat()
        )

        # Save to cache after all checkpoints created
        save_trajectory_cache(trajectory)

        pending_count = len(remaining_shas)
        if checkpoints_created == 1:
            message = f"Created checkpoint {trajectory.total_checkpoints} with {commits_processed} commits."
        else:
            message = f"Created {checkpoints_created} checkpoints with {commits_processed} commits."

        if pending_count > 0:
            message += f" {pending_count} commits accumulated (need 10 for next checkpoint)."

        return TrajectoryResponse(
            success=True,
            trajectory=trajectory,
            new_checkpoint_created=True,
            message=message,
            commits_pending=pending_count
        )

    except Exception as e:
        print(f"[Trajectory] Failed to create checkpoint: {e}")
        import traceback
        traceback.print_exc()

        # Save any checkpoints that were successfully created
        if checkpoints_created > 0:
            try:
                # Update accumulation state before saving
                current_period_start = repo_start_date
                weeks_elapsed = (datetime.now(repo_start_date.tzinfo) - repo_start_date).days // 14
                current_period_start = repo_start_date + timedelta(weeks=2 * weeks_elapsed)
                current_period_end = current_period_start + timedelta(weeks=2)

                trajectory.accumulation_state = PeriodAccumulationState(
                    current_period_start=current_period_start.isoformat(),
                    current_period_end=current_period_end.isoformat(),
                    accumulated_commits=remaining_shas,
                    repo_start_date=repo_start_date.isoformat()
                )

                save_trajectory_cache(trajectory)
            except Exception as save_error:
                print(f"[Trajectory] Failed to save partial progress: {save_error}")

        return TrajectoryResponse(
            success=False,
            trajectory=trajectory,
            new_checkpoint_created=checkpoints_created > 0,
            message=f"Created {checkpoints_created} checkpoints before error: {str(e)}",
            commits_pending=len(remaining_shas)
        )
