"""Batch operation routes - multi-repo processing."""

import json
from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from evaluator.services import extract_github_data, extract_gitee_data, resolve_plugin_id
from evaluator.paths import get_platform_data_dir
from evaluator.utils import parse_repo_url, get_author_from_commit
from evaluator.config import DEFAULT_LLM_MODEL
from evaluator.routes.evaluation import evaluate_author

router = APIRouter()


@router.post("/api/batch/extract")
async def batch_extract_repos(request: dict):
    """Batch extract multiple repositories (GitHub + Gitee)."""
    urls = request.get("urls", [])

    if not urls:
        raise HTTPException(status_code=400, detail="No URLs provided")
    if len(urls) < 2:
        raise HTTPException(status_code=400, detail="Please provide at least 2 repository URLs")
    if len(urls) > 5:
        raise HTTPException(status_code=400, detail="Please provide at most 5 repository URLs")

    results = []

    for url in urls:
        result = {
            "url": url,
            "status": "failed",
            "message": "",
            "data_exists": False
        }

        parsed = parse_repo_url(url)
        if not parsed:
            result["message"] = "Invalid repository URL format"
            results.append(result)
            continue

        platform, owner, repo = parsed
        result["owner"] = owner
        result["repo"] = repo
        result["platform"] = platform

        # Check if data exists
        data_dir = get_platform_data_dir(platform, owner, repo)
        commits_dir = data_dir / "commits"

        if data_dir.exists() and commits_dir.exists() and list(commits_dir.glob("*.json")):
            result["status"] = "skipped"
            result["message"] = "Repository data already exists"
            result["data_exists"] = True
            results.append(result)
            continue

        # Extract
        try:
            if platform == "github":
                success = extract_github_data(owner, repo)
            else:
                success = extract_gitee_data(owner, repo)

            if success:
                result["status"] = "extracted"
                result["message"] = "Successfully extracted repository data"
                result["data_exists"] = True
            else:
                result["status"] = "failed"
                result["message"] = "Failed to extract repository data"
        except Exception as e:
            result["status"] = "failed"
            result["message"] = f"Error: {str(e)}"

        results.append(result)

    # Summary
    extracted_count = sum(1 for r in results if r["status"] == "extracted")
    skipped_count = sum(1 for r in results if r["status"] == "skipped")
    failed_count = sum(1 for r in results if r["status"] == "failed")

    return {
        "success": True,
        "results": results,
        "summary": {
            "total": len(results),
            "extracted": extracted_count,
            "skipped": skipped_count,
            "failed": failed_count
        }
    }



@router.post("/api/batch/common-contributors")
async def find_common_contributors(request: dict):
    """
    Find common contributors across multiple repositories

    Request body:
    {
        "repos": [
            {"owner": "facebook", "repo": "react"},
            {"owner": "vercel", "repo": "next.js"}
        ]
    }

    Response:
    {
        "success": true,
        "common_contributors": [
            {
                "author": "John Doe",
                "email": "john@example.com",
                "repos": [
                    {
                        "owner": "facebook",
                        "repo": "react",
                        "commits": 150
                    },
                    {
                        "owner": "vercel",
                        "repo": "next.js",
                        "commits": 75
                    }
                ],
                "total_commits": 225,
                "repo_count": 2
            }
        ],
        "summary": {
            "total_repos": 2,
            "total_common_contributors": 5
        }
    }
    """
    repos = request.get("repos", [])
    author_aliases = request.get("author_aliases", "")  # Comma-separated list of names belonging to the same person

    if not repos:
        raise HTTPException(status_code=400, detail="No repositories provided")

    if len(repos) < 2:
        raise HTTPException(status_code=400, detail="At least 2 repositories required to find common contributors")

    # Parse author aliases into a set of normalized names
    user_defined_aliases = set()
    if author_aliases and isinstance(author_aliases, str):
        # Split by comma and normalize
        aliases = [name.strip().lower() for name in author_aliases.split(',') if name.strip()]
        user_defined_aliases = set(aliases)
        if user_defined_aliases:
            print(f"📝 User-defined aliases: {user_defined_aliases}")

    # Load authors from each repository
    repo_authors = {}  # {repo_key: {author: {commits, email}}}

    for repo_info in repos:
        owner = repo_info.get("owner")
        repo = repo_info.get("repo")
        platform = repo_info.get("platform", "github")  # Default to github if not specified

        if not owner or not repo:
            continue

        repo_key = f"{owner}/{repo}"
        data_dir = get_platform_data_dir(platform, owner, repo)
        commits_dir = data_dir / "commits"

        if not commits_dir.exists():
            print(f"⚠ No commit data found for {repo_key}")
            continue

        authors_map = {}

        # Load all commit files
        for commit_file in commits_dir.glob("*.json"):
            try:
                with open(commit_file, 'r', encoding='utf-8') as f:
                    commit_data = json.load(f)
                    author = get_author_from_commit(commit_data)

                    # Get email and GitHub user ID
                    email = ""
                    github_id = None
                    github_login = None

                    if "commit" in commit_data:
                        email = commit_data.get("commit", {}).get("author", {}).get("email", "")

                    # Get GitHub user info if available
                    if "author" in commit_data and isinstance(commit_data["author"], dict):
                        github_id = commit_data["author"].get("id")
                        github_login = commit_data["author"].get("login")

                    if author:
                        if author not in authors_map:
                            authors_map[author] = {
                                "commits": 0,
                                "email": email,
                                "github_id": github_id,
                                "github_login": github_login
                            }
                        authors_map[author]["commits"] += 1
            except Exception as e:
                print(f"⚠ Error reading {commit_file}: {e}")
                continue

        if authors_map:
            repo_authors[repo_key] = authors_map
            print(f"✓ Loaded {len(authors_map)} authors from {repo_key}")

    if len(repo_authors) < 2:
        return {
            "success": True,
            "common_contributors": [],
            "summary": {
                "total_repos": len(repo_authors),
                "total_common_contributors": 0
            },
            "message": "Not enough repositories with data to find common contributors"
        }

    # Find common contributors using intelligent matching
    # Strategy: Two-pass matching
    # Pass 1: Group by GitHub ID/login (strong identity signals)
    # Pass 2: Match orphaned authors to existing groups by fuzzy name

    def normalize_name(name):
        """Normalize name for fuzzy matching"""
        normalized = name.lower().strip()
        parts = normalized.split()
        return parts[0] if parts else normalized

    def names_match_fuzzy(name1, name2):
        """Check if two names likely refer to the same person"""
        norm1 = normalize_name(name1)
        norm2 = normalize_name(name2)

        # Exact match on first name
        if norm1 == norm2:
            return True

        # One name contains the other as a word
        words1 = name1.lower().split()
        words2 = name2.lower().split()

        if norm1 in words2 or norm2 in words1:
            return True

        return False

    # Pass 1: Group by GitHub ID/login
    identity_groups = {}  # {canonical_key: [{"repo_key": str, "author": str, "data": dict}]}
    orphaned_authors = []  # Authors without GitHub ID/login

    for repo_key, authors_map in repo_authors.items():
        for author, author_data in authors_map.items():
            github_id = author_data.get("github_id")
            github_login = author_data.get("github_login")

            # Use GitHub ID/login as canonical identity
            if github_id:
                canonical_key = f"github_id:{github_id}"
            elif github_login:
                canonical_key = f"github_login:{github_login}"
            else:
                # No strong identity, mark as orphaned for second pass
                orphaned_authors.append({
                    "repo_key": repo_key,
                    "author": author,
                    "data": author_data
                })
                continue

            if canonical_key not in identity_groups:
                identity_groups[canonical_key] = []

            identity_groups[canonical_key].append({
                "repo_key": repo_key,
                "author": author,
                "data": author_data
            })

    # Pass 1.5: Handle user-defined aliases
    # Merge all identity groups that match any of the user-defined aliases
    if user_defined_aliases:
        print(f"🔗 Grouping identities by user-defined aliases...")
        matched_keys = []

        # Find all identity groups that contain names matching the user-defined aliases
        for canonical_key, identities in identity_groups.items():
            for identity in identities:
                if identity["author"].lower().strip() in user_defined_aliases:
                    matched_keys.append(canonical_key)
                    break

        # Also check orphaned authors
        orphaned_matches = []
        for orphan in orphaned_authors:
            if orphan["author"].lower().strip() in user_defined_aliases:
                orphaned_matches.append(orphan)

        # If we found multiple groups/orphans matching the aliases, merge them
        if len(matched_keys) > 0 or len(orphaned_matches) > 0:
            # Create or use the first matched group as the primary group
            if matched_keys:
                primary_key = f"aliases:{','.join(sorted(user_defined_aliases))}"
                # Merge all matched groups into the primary group
                merged_identities = []
                for key in matched_keys:
                    merged_identities.extend(identity_groups[key])
                    if key != primary_key:
                        del identity_groups[key]

                # Add orphaned matches
                merged_identities.extend(orphaned_matches)

                # Remove orphaned matches from the orphaned_authors list
                orphaned_authors = [o for o in orphaned_authors if o not in orphaned_matches]

                identity_groups[primary_key] = merged_identities
                print(f"✓ Merged {len(matched_keys)} groups + {len(orphaned_matches)} orphans by aliases")
            else:
                # Only orphaned matches - create new group
                primary_key = f"aliases:{','.join(sorted(user_defined_aliases))}"
                identity_groups[primary_key] = orphaned_matches
                orphaned_authors = [o for o in orphaned_authors if o not in orphaned_matches]
                print(f"✓ Created group from {len(orphaned_matches)} orphaned authors matching aliases")

    # Pass 2: Try to match orphaned authors to existing groups by fuzzy name
    unmatched_orphans = []

    for orphan in orphaned_authors:
        matched = False

        # Try to match with existing groups by comparing names
        for canonical_key, identities in identity_groups.items():
            # Check if orphan name matches any name in this group
            for identity in identities:
                if names_match_fuzzy(orphan["author"], identity["author"]):
                    # Found a match! Add to this group
                    identity_groups[canonical_key].append(orphan)
                    matched = True
                    break

            if matched:
                break

        if not matched:
            unmatched_orphans.append(orphan)

    # Pass 3: Group remaining unmatched orphans by exact name
    for orphan in unmatched_orphans:
        canonical_key = f"name:{orphan['author'].lower().strip()}"

        if canonical_key not in identity_groups:
            identity_groups[canonical_key] = []

        identity_groups[canonical_key].append(orphan)

    # Build common contributors from identity groups
    common_contributors = []

    for canonical_key, identities in identity_groups.items():
        # Get unique repos for this identity
        repos_map = {}  # {repo_key: identity}

        for identity in identities:
            repo_key = identity["repo_key"]
            if repo_key not in repos_map:
                repos_map[repo_key] = identity

        # Consider common if appears in at least 2 repos
        if len(repos_map) >= 2:
            repos_with_author = []

            for repo_key, identity in repos_map.items():
                owner, repo = repo_key.split("/", 1)
                author_data = identity["data"]

                repos_with_author.append({
                    "owner": owner,
                    "repo": repo,
                    "commits": author_data["commits"],
                    "email": author_data.get("email", ""),
                    "github_login": author_data.get("github_login", ""),
                })

            total_commits = sum(r["commits"] for r in repos_with_author)

            # Use the most complete name and email
            primary_identity = identities[0]
            display_name = primary_identity["author"]
            email = primary_identity["data"].get("email", "")
            github_login = primary_identity["data"].get("github_login", "")

            # Try to find the most complete name
            for identity in identities:
                if identity["data"].get("github_login"):
                    github_login = identity["data"]["github_login"]
                    display_name = identity["author"]
                    break

            # Collect all unique author names for this identity
            all_names = list(set(identity["author"] for identity in identities))

            common_contributors.append({
                "author": display_name,
                "aliases": all_names,  # All names associated with this person
                "email": email,
                "github_login": github_login,
                "repos": repos_with_author,
                "total_commits": total_commits,
                "repo_count": len(repos_with_author),
                "matched_by": canonical_key.split(":")[0]  # "github_id", "github_login", "aliases", or "name"
            })

    # Sort by repo_count (descending), then by total_commits (descending)
    common_contributors.sort(key=lambda x: (-x["repo_count"], -x["total_commits"]))

    return {
        "success": True,
        "common_contributors": common_contributors,
        "summary": {
            "total_repos": len(repo_authors),
            "total_common_contributors": len(common_contributors)
        }
    }


@router.post("/api/batch/compare-contributor")
async def compare_contributor_across_repos(request: dict):
    """
    Compare a contributor's six-dimensional scores across multiple repositories

    Request body:
    {
        "contributor": "John Doe",
        "repos": [
            {"owner": "facebook", "repo": "react"},
            {"owner": "vercel", "repo": "next.js"}
        ]
    }

    Response:
    {
        "success": true,
        "contributor": "John Doe",
        "comparisons": [
            {
                "repo": "facebook/react",
                "owner": "facebook",
                "repo_name": "react",
                "scores": {
                    "ai_model_fullstack": 85,
                    "ai_native_architecture": 70,
                    ...
                },
                "total_commits": 150
            }
        ],
        "dimension_names": [...],
        "dimension_display_names": [...]
    }
    """
    contributor = request.get("contributor")
    repos = request.get("repos", [])
    use_cache = bool(request.get("use_cache", True))
    model = request.get("model") or DEFAULT_LLM_MODEL
    requested_plugin_id = str(request.get("plugin") or "").strip()
    plugin_id = resolve_plugin_id(requested_plugin_id)
    if not isinstance(model, str):
        model = DEFAULT_LLM_MODEL

    # Parse author aliases
    author_aliases_str = request.get("author_aliases", "")
    contributor_aliases = None

    if author_aliases_str and isinstance(author_aliases_str, str):
        # Split by comma and normalize
        aliases = [name.strip().lower() for name in author_aliases_str.split(',') if name.strip()]
        # Check if contributor matches any of the aliases
        if contributor.lower().strip() in aliases:
            contributor_aliases = aliases
            print(f"🔗 Using {len(contributor_aliases)} aliases for contributor '{contributor}': {contributor_aliases}")
        else:
            # Contributor not in aliases list, just use the contributor name
            contributor_aliases = [contributor.lower().strip()]
    else:
        # No aliases provided, use contributor name only
        contributor_aliases = [contributor.lower().strip()]

    if not contributor:
        raise HTTPException(status_code=400, detail="Contributor name is required")

    if not repos:
        raise HTTPException(status_code=400, detail="At least one repository is required")

    if len(repos) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 repositories allowed")

    results = []
    failed_repos = []

    for repo_info in repos:
        owner = repo_info.get("owner")
        repo = repo_info.get("repo")
        repo_platform = repo_info.get("platform", "github")  # Default to github if not specified

        if not owner or not repo:
            continue

        try:
            # Check if data exists for this repo
            data_dir = get_platform_data_dir(repo_platform, owner, repo)
            if not data_dir.exists() or not (data_dir / "commits").exists():
                # Try to extract data in real-time
                print(f"⚡ Data not found for {owner}/{repo}, triggering real-time extraction...")
                try:
                    if repo_platform == "github":
                        extraction_success = extract_github_data(owner, repo)
                    else:
                        extraction_success = extract_gitee_data(owner, repo)

                    if not extraction_success:
                        failed_repos.append({
                            "repo": f"{owner}/{repo}",
                            "reason": "Failed to extract repository data in real-time"
                        })
                        continue

                    print(f"✓ Successfully extracted data for {owner}/{repo}")
                except Exception as extract_error:
                    print(f"✗ Extraction failed for {owner}/{repo}: {extract_error}")
                    failed_repos.append({
                        "repo": f"{owner}/{repo}",
                        "reason": f"Extraction error: {str(extract_error)}"
                    })
                    continue

            # Evaluate contributor in this repo
            eval_result = await evaluate_author(
                owner,
                repo,
                contributor,
                use_chunking=True,
                use_cache=use_cache,
                model=model,
                platform=repo_platform,
                plugin=plugin_id,
                request_body={"aliases": contributor_aliases},
            )

            if eval_result.get("success"):
                evaluation = eval_result["evaluation"]
                scores = evaluation.get("scores", {})

                results.append({
                    "repo": f"{owner}/{repo}",
                    "owner": owner,
                    "repo_name": repo,
                    "scores": {
                        "ai_model_fullstack": scores.get("ai_fullstack", 0),
                        "ai_native_architecture": scores.get("ai_architecture", 0),
                        "cloud_native": scores.get("cloud_native", 0),
                        "open_source_collaboration": scores.get("open_source", 0),
                        "intelligent_development": scores.get("intelligent_dev", 0),
                        "engineering_leadership": scores.get("leadership", 0)
                    },
                    "total_commits": evaluation.get("total_commits_analyzed", 0),
                    "commits_summary": evaluation.get("commits_summary", {}),
                    "cached": eval_result.get("metadata", {}).get("cached", False),
                    "plugin": evaluation.get("plugin", plugin_id),
                    "plugin_version": evaluation.get("plugin_version", ""),
                    "plugin_scan_path": evaluation.get("plugin_scan_path", ""),
                })
            else:
                error_msg = eval_result.get("message", "Evaluation failed")
                failed_repos.append({
                    "repo": f"{owner}/{repo}",
                    "reason": error_msg
                })

        except HTTPException as e:
            failed_repos.append({
                "repo": f"{owner}/{repo}",
                "reason": str(e.detail)
            })
        except Exception as e:
            print(f"✗ Failed to evaluate {contributor} in {owner}/{repo}: {e}")
            failed_repos.append({
                "repo": f"{owner}/{repo}",
                "reason": f"Error: {str(e)}"
            })

    if not results:
        return {
            "success": False,
            "message": "No evaluations found for this contributor across the specified repositories",
            "contributor": contributor,
            "failed_repos": failed_repos
        }

    # Calculate aggregate statistics
    avg_scores = {}
    dimension_keys = [
        "ai_model_fullstack",
        "ai_native_architecture",
        "cloud_native",
        "open_source_collaboration",
        "intelligent_development",
        "engineering_leadership"
    ]

    for dim in dimension_keys:
        scores_list = [r["scores"][dim] for r in results]
        avg_scores[dim] = sum(scores_list) / len(scores_list) if scores_list else 0

    total_commits_all_repos = sum(r["total_commits"] for r in results)

    return {
        "success": True,
        "contributor": contributor,
        "plugin_requested": requested_plugin_id or None,
        "plugin_used": plugin_id,
        "comparisons": results,
        "dimension_keys": dimension_keys,
        "dimension_names": [
            "AI Model Full-Stack & Trade-off Capability",
            "AI Native Architecture & Communication Design",
            "Cloud Native & Constraint Engineering",
            "Open Source Collaboration & Requirements Translation",
            "Intelligent Development & Human-Machine Collaboration",
            "Engineering Leadership & System Trade-offs"
        ],
        "aggregate": {
            "total_repos_evaluated": len(results),
            "total_commits": total_commits_all_repos,
            "average_scores": avg_scores
        },
        "failed_repos": failed_repos if failed_repos else None
    }
