"""Trajectory service for managing user growth tracking."""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from evaluator.paths import get_trajectory_cache_path, get_platform_data_dir
from evaluator.schemas import TrajectoryCache, TrajectoryCheckpoint, CommitsRange, TrajectoryResponse, EvaluationSchema
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
    parallel_chunking: bool = True,
    max_parallel_workers: int = 3
) -> TrajectoryCheckpoint:
    """
    Create a checkpoint by evaluating exactly 3 commits.

    Args:
        commits: List of commits (ordered newest first)
        username: Username being evaluated
        checkpoint_id: Sequential checkpoint ID
        plugin_id: Plugin to use for evaluation
        model: LLM model to use
        language: Language for evaluation
        repos_analyzed: List of repo URLs analyzed
        aliases_used: List of aliases used in filtering
        parallel_chunking: Enable parallel chunking
        max_parallel_workers: Max parallel workers

    Returns:
        TrajectoryCheckpoint with evaluation result
    """
    # Take exactly 3 newest commits
    checkpoint_commits = commits[:3]

    if len(checkpoint_commits) < 3:
        raise ValueError(f"Need 3 commits for checkpoint, got {len(checkpoint_commits)}")

    # Extract commit range
    start_sha = checkpoint_commits[-1].get('sha') or checkpoint_commits[-1].get('hash')
    end_sha = checkpoint_commits[0].get('sha') or checkpoint_commits[0].get('hash')

    # Create a temporary "platform" for evaluation
    # Use the first repo URL to determine platform
    if repos_analyzed:
        platform, owner, repo = parse_repo_url(repos_analyzed[0])
    else:
        platform, owner, repo = 'github', 'unknown', 'unknown'

    # Create evaluator
    evaluator = get_or_create_evaluator(
        platform=platform,
        owner=owner,
        repo=repo,
        commits=checkpoint_commits,
        use_cache=False,
        plugin_id=plugin_id,
        model=model,
        parallel_chunking=parallel_chunking,
        max_parallel_workers=max_parallel_workers
    )

    # Evaluate
    print(f"[Trajectory] Evaluating checkpoint {checkpoint_id} with 3 commits")
    evaluation_result = evaluator.evaluate_engineer(
        commits=checkpoint_commits,
        username=username,
        max_commits=3,
        load_files=True,
        use_chunking=True
    )

    # Debug: Check type of evaluation_result
    print(f"[Trajectory] evaluation_result type: {type(evaluation_result)}")
    print(f"[Trajectory] evaluation_result keys: {list(evaluation_result.keys()) if isinstance(evaluation_result, dict) else 'NOT A DICT'}")

    # Ensure evaluation_result is a dict
    if not isinstance(evaluation_result, dict):
        raise TypeError(f"Expected dict from evaluate_engineer, got {type(evaluation_result)}")

    # Add required metadata fields (always set, don't check if exists)
    evaluation_result['evaluated_at'] = datetime.utcnow().isoformat()
    evaluation_result['plugin'] = plugin_id

    # Load plugin version
    try:
        meta, _, _ = load_scan_module(plugin_id)
        evaluation_result['plugin_version'] = meta.version
    except Exception as e:
        print(f"[Trajectory] Warning: Failed to load plugin version: {e}")
        evaluation_result['plugin_version'] = '0.1.0'

    # Debug: Verify fields were added
    print(f"[Trajectory] After adding metadata - evaluated_at: {evaluation_result.get('evaluated_at')}")
    print(f"[Trajectory] After adding metadata - plugin: {evaluation_result.get('plugin')}")
    print(f"[Trajectory] After adding metadata - plugin_version: {evaluation_result.get('plugin_version')}")

    # Convert to EvaluationSchema
    try:
        evaluation = EvaluationSchema(**evaluation_result)
    except Exception as e:
        print(f"[Trajectory] Validation error details:")
        print(f"[Trajectory] evaluation_result keys: {list(evaluation_result.keys())}")
        print(f"[Trajectory] evaluation_result: {json.dumps(evaluation_result, indent=2, default=str)}")
        raise

    # Create checkpoint
    checkpoint = TrajectoryCheckpoint(
        checkpoint_id=checkpoint_id,
        created_at=datetime.utcnow().isoformat(),
        commits_range=CommitsRange(
            start_sha=start_sha,
            end_sha=end_sha,
            commit_count=3
        ),
        evaluation=evaluation,
        repos_analyzed=repos_analyzed,
        aliases_used=aliases_used
    )

    return checkpoint


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
    print(f"[Trajectory] Can create {new_commits_count // 3} checkpoints with {new_commits_count % 3} commits remaining")

    # Check if we have enough commits for a checkpoint
    if new_commits_count < 3:
        return TrajectoryResponse(
            success=True,
            trajectory=trajectory,
            new_checkpoint_created=False,
            message=f"Found {new_commits_count} new commits. Need 3 commits to create checkpoint.",
            commits_pending=new_commits_count
        )

    # Create multiple checkpoints by processing commits in batches of 3
    checkpoints_created = 0
    commits_processed = 0
    remaining_commits = new_commits.copy()

    try:
        while len(remaining_commits) >= 3:
            # Take next 3 commits for checkpoint
            batch_commits = remaining_commits[:3]

            checkpoint = create_checkpoint_evaluation(
                commits=batch_commits,
                username=username,
                checkpoint_id=trajectory.total_checkpoints + 1,
                plugin_id=plugin_id,
                model=model,
                language=language,
                repos_analyzed=repos_analyzed,
                aliases_used=aliases,
                parallel_chunking=parallel_chunking,
                max_parallel_workers=max_parallel_workers
            )

            # Update trajectory
            trajectory.checkpoints.append(checkpoint)
            trajectory.total_checkpoints += 1
            trajectory.last_synced_sha = checkpoint.commits_range.end_sha
            trajectory.last_synced_at = checkpoint.created_at

            # Move to next batch
            remaining_commits = remaining_commits[3:]
            commits_processed += 3
            checkpoints_created += 1

            print(f"[Trajectory] Created checkpoint {checkpoint.checkpoint_id} ({commits_processed}/{new_commits_count} commits processed)")

        # Save to cache after all checkpoints created
        save_trajectory_cache(trajectory)

        pending_count = len(remaining_commits)
        if checkpoints_created == 1:
            message = f"Created checkpoint {trajectory.total_checkpoints} with 3 new commits."
        else:
            message = f"Created {checkpoints_created} checkpoints with {commits_processed} new commits."

        if pending_count > 0:
            message += f" {pending_count} commits pending (need 3 for next checkpoint)."

        return TrajectoryResponse(
            success=True,
            trajectory=trajectory,
            new_checkpoint_created=True,
            message=message,
            commits_pending=pending_count
        )

    except Exception as e:
        print(f"[Trajectory] Failed to create checkpoint: {e}")
        # Save any checkpoints that were successfully created
        if checkpoints_created > 0:
            try:
                save_trajectory_cache(trajectory)
            except Exception as save_error:
                print(f"[Trajectory] Failed to save partial progress: {save_error}")

        return TrajectoryResponse(
            success=False,
            trajectory=trajectory,
            new_checkpoint_created=checkpoints_created > 0,
            message=f"Created {checkpoints_created} checkpoints before error: {str(e)}",
            commits_pending=new_commits_count - commits_processed
        )
