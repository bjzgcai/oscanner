"""Batch operation routes - multi-repo processing."""

import json
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional

from evaluator.services import extract_github_data, extract_gitee_data, resolve_plugin_id
from evaluator.paths import get_platform_data_dir
from evaluator.utils import (
    get_author_from_commit,
    get_emails_from_commit,
    is_valid_email_identity,
    normalize_email_identity,
    parse_repo_url,
    parse_repo_url_with_ref,
)
from evaluator.config import DEFAULT_LLM_MODEL
from evaluator.routes.evaluation import evaluate_author

router = APIRouter()


NON_NUMERIC_SCORE_KEYS = {"reasoning", "summary", "analysis", "evidence", "recommendations"}


def _request_values(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        normalized = value.replace("\n", ",")
        return [part.strip() for part in normalized.split(",") if part.strip()]
    return [str(value).strip()] if str(value).strip() else []


def _parse_request_emails(request: Dict[str, Any], fallback_identity: Optional[str] = None) -> Optional[List[str]]:
    raw_emails: List[str] = []
    has_explicit_email_key = False
    for key in ("author_emails", "emails"):
        if key in request:
            has_explicit_email_key = True
            raw_emails.extend(_request_values(request.get(key)))

    if has_explicit_email_key:
        emails = [normalize_email_identity(email) for email in raw_emails if normalize_email_identity(email)]
        invalid = [email for email in emails if not is_valid_email_identity(email)]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Invalid email format: {', '.join(invalid)}")
        return list(dict.fromkeys(emails))

    identity = normalize_email_identity(fallback_identity or "")
    if "@" in identity:
        if not is_valid_email_identity(identity):
            raise HTTPException(status_code=400, detail=f"Invalid email format: {fallback_identity}")
        return [identity]

    return None


def _numeric_score(value: Any):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _plugin_numeric_scores(scores: Dict[str, Any]) -> Dict[str, float]:
    output: Dict[str, float] = {}
    for key, value in scores.items():
        if key in NON_NUMERIC_SCORE_KEYS:
            continue
        numeric = _numeric_score(value)
        if numeric is not None:
            output[key] = numeric
    return output


def _dimension_label(key: str) -> str:
    return key.replace("_", " ").title()


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

        parsed_ref = parse_repo_url_with_ref(url)
        parsed = (
            (parsed_ref.platform, parsed_ref.owner, parsed_ref.repo)
            if parsed_ref
            else None
        )
        if not parsed:
            result["message"] = "Invalid repository URL format"
            results.append(result)
            continue

        platform, owner, repo = parsed
        branch = parsed_ref.branch if parsed_ref else None
        result["owner"] = owner
        result["repo"] = repo
        result["platform"] = platform
        if branch:
            result["branch"] = branch

        # Check if data exists
        data_dir = get_platform_data_dir(platform, owner, repo, ref=branch)
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
                success = extract_github_data(owner, repo, branch=branch)
            else:
                success = extract_gitee_data(owner, repo, branch=branch)

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
    author_aliases = request.get("author_aliases", "")  # Legacy comma-separated names belonging to the same person
    author_emails = _parse_request_emails(request)

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
    user_defined_emails = set(author_emails or [])
    if user_defined_emails:
        print(f"📝 User-defined emails: {user_defined_emails}")

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

                    emails = get_emails_from_commit(commit_data)
                    if emails:
                        email = emails[0]

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

    # Pass 1.5: Handle user-defined emails/aliases
    # Merge all identity groups that match any of the user-defined identities.
    if user_defined_aliases or user_defined_emails:
        print(f"🔗 Grouping identities by user-defined identities...")
        matched_keys = []

        # Find all identity groups that contain names/emails matching user input.
        for canonical_key, identities in identity_groups.items():
            for identity in identities:
                identity_email = normalize_email_identity(identity["data"].get("email", ""))
                if (
                    identity["author"].lower().strip() in user_defined_aliases
                    or identity_email in user_defined_emails
                ):
                    matched_keys.append(canonical_key)
                    break

        # Also check orphaned authors
        orphaned_matches = []
        for orphan in orphaned_authors:
            orphan_email = normalize_email_identity(orphan["data"].get("email", ""))
            if orphan["author"].lower().strip() in user_defined_aliases or orphan_email in user_defined_emails:
                orphaned_matches.append(orphan)

        # If we found multiple groups/orphans matching the aliases, merge them
        if len(matched_keys) > 0 or len(orphaned_matches) > 0:
            # Create or use the first matched group as the primary group
            identity_key = ",".join(sorted(user_defined_emails or user_defined_aliases))
            if matched_keys:
                primary_key = f"user_identities:{identity_key}"
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
                primary_key = f"user_identities:{identity_key}"
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
    Compare a contributor's plugin rubric scores across multiple repositories

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
    model = request.get("model") or DEFAULT_LLM_MODEL
    requested_plugin_id = str(request.get("plugin") or "").strip()
    plugin_id = resolve_plugin_id(requested_plugin_id)
    if not isinstance(model, str):
        model = DEFAULT_LLM_MODEL

    if not contributor:
        raise HTTPException(status_code=400, detail="Contributor name or email is required")

    contributor = str(contributor).strip()
    contributor_emails = _parse_request_emails(request, contributor)

    # Parse legacy author aliases.
    author_aliases_str = request.get("author_aliases", "")
    contributor_aliases = None

    if contributor_emails:
        contributor_aliases = contributor_emails
        evaluation_identity = contributor_emails[0]
        request_body = {"emails": contributor_emails}
        print(f"🔗 Using {len(contributor_emails)} email identities for contributor '{contributor}': {contributor_emails}")
    elif author_aliases_str and isinstance(author_aliases_str, str):
        # Split by comma and normalize
        aliases = [name.strip().lower() for name in author_aliases_str.split(',') if name.strip()]
        # Check if contributor matches any of the aliases
        if contributor.lower().strip() in aliases:
            contributor_aliases = aliases
            print(f"🔗 Using {len(contributor_aliases)} aliases for contributor '{contributor}': {contributor_aliases}")
        else:
            # Contributor not in aliases list, just use the contributor name
            contributor_aliases = [contributor.lower().strip()]
        evaluation_identity = contributor
        request_body = {"aliases": contributor_aliases}
    else:
        # No aliases provided, use contributor name only
        contributor_aliases = [contributor.lower().strip()]
        evaluation_identity = contributor
        request_body = {"aliases": contributor_aliases}

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
        branch = repo_info.get("branch")

        if not owner or not repo:
            continue

        try:
            # Check if data exists for this repo
            data_dir = get_platform_data_dir(repo_platform, owner, repo, ref=branch)
            if not data_dir.exists() or not (data_dir / "commits").exists():
                # Try to extract data in real-time
                print(f"⚡ Data not found for {owner}/{repo}, triggering real-time extraction...")
                try:
                    if repo_platform == "github":
                        extraction_success = extract_github_data(owner, repo, branch=branch)
                    else:
                        extraction_success = extract_gitee_data(owner, repo, branch=branch)

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
                evaluation_identity,
                model=model,
                platform=repo_platform,
                branch=branch or "",
                plugin=plugin_id,
                request_body=request_body,
            )

            if eval_result.get("success"):
                evaluation = eval_result["evaluation"]
                scores = evaluation.get("scores", {})

                numeric_scores = _plugin_numeric_scores(scores)

                results.append({
                    "repo": f"{owner}/{repo}",
                    "owner": owner,
                    "repo_name": repo,
                    "scores": numeric_scores,
                    "total_commits": evaluation.get("total_commits_analyzed", 0),
                    "commits_summary": evaluation.get("commits_summary", {}),
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
    dimension_keys = []
    seen_dimensions = set()
    for result in results:
        for key in result["scores"].keys():
            if key not in seen_dimensions:
                seen_dimensions.add(key)
                dimension_keys.append(key)

    avg_scores = {}

    for dim in dimension_keys:
        scores_list = [r["scores"].get(dim, 0) for r in results]
        avg_scores[dim] = sum(scores_list) / len(scores_list) if scores_list else 0

    total_commits_all_repos = sum(r["total_commits"] for r in results)

    return {
        "success": True,
        "contributor": contributor,
        "plugin_requested": requested_plugin_id or None,
        "plugin_used": plugin_id,
        "comparisons": results,
        "dimension_keys": dimension_keys,
        "dimension_names": [_dimension_label(key) for key in dimension_keys],
        "aggregate": {
            "total_repos_evaluated": len(results),
            "total_commits": total_commits_all_repos,
            "average_scores": avg_scores
        },
        "failed_repos": failed_repos if failed_repos else None
    }
