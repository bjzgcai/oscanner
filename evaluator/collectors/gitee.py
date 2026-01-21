"""
Gitee data collector

Collects engineering activity data from Gitee using the Gitee API.
"""

from typing import Dict, List, Optional, Any
import re
import os
import json
import hashlib
from datetime import datetime
from pathlib import Path

from evaluator.paths import get_data_dir


class GiteeCollector:
    """Collect data from Gitee"""

    def __init__(self, token: Optional[str] = None, public_token: Optional[str] = None, cache_dir: Optional[str] = None):
        """
        Initialize Gitee collector

        Args:
            token: Gitee personal access token for enterprise (z.gitee.cn) API access
            public_token: Gitee personal access token for public (gitee.com) API access
            cache_dir: Directory to store cached Gitee data
        """
        self.token = token  # For z.gitee.cn (enterprise)
        self.public_token = public_token  # For gitee.com (public)
        self.base_url = "https://gitee.com/api/v5"
        self.enterprise_base_url = "https://z.gitee.cn/api/v5"

        from evaluator.paths import get_data_dir
        self.cache_dir = Path(cache_dir).expanduser() if cache_dir else get_data_dir()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def collect_user_data(self, username: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Collect comprehensive data for a Gitee user

        Args:
            username: Gitee username
            use_cache: Whether to use cached data if available

        Returns:
            Dictionary containing collected data
        """
        # Create a pseudo-URL for cache key
        user_url = f"https://gitee.com/{username}"

        # Check cache first if enabled
        if use_cache:
            cached_data = self._load_from_cache(user_url)
            if cached_data is not None:
                return cached_data.get("data", cached_data)

        # Fetch data (in real implementation, this would use the Gitee API)
        print(f"[API] Fetching fresh data for user {username}")

        # In a real implementation, this would use the Gitee API
        # Structure matches GitHub collector for consistency
        data = {
            # Basic metrics
            "total_contributions": 0,
            "repos_contributed_to": 0,
            "pr_reviews_given": 0,
            "issues_created": 0,
            "issues_resolved": 0,
            "feature_implementations": 0,

            # Code metrics
            "commits": [],
            "pull_requests": [],
            "code_reviews": [],

            # Technology stack
            "languages": [],
            "ml_frameworks": [],
            "ml_pipeline_repos": [],

            # Architecture and design
            "api_designs": [],
            "architecture_docs": 0,
            "distributed_ai_systems": [],

            # Cloud native
            "dockerfile_count": 0,
            "orchestration_configs": [],
            "cicd_configs": [],
            "iac_files": [],

            # Collaboration
            "communication_quality_score": 0.0,
            "mentorship_score": 0.0,
            "team_collaboration_score": 0.0,

            # Leadership
            "owned_projects": [],
            "architecture_commits": 0,
            "trade_off_documentation": 0,

            # Intelligent development
            "automation_scripts": [],
            "ai_tool_configs": [],
            "custom_tools_developed": 0,
            "test_automation_score": 0.0,

            # Optimization
            "optimization_commits": 0,
            "resource_optimization_commits": 0,
            "generated_code_score": 0.0
        }

        # Save to cache
        self._save_to_cache(user_url, data)

        return data

    def collect_repo_data(self, repo_url: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Collect data from a specific repository

        Args:
            repo_url: Gitee repository URL (supports gitee.com and z.gitee.cn formats)
            use_cache: Whether to use cached data if available

        Returns:
            Dictionary containing repository data
        """
        # Check cache first if enabled
        if use_cache:
            cached_data = self._load_from_cache(repo_url)
            if cached_data is not None:
                return cached_data.get("data", cached_data)

        # Parse owner and repo from URL (supports both gitee.com and z.gitee.cn)
        owner, repo = self._parse_repo_url(repo_url)

        # Fetch data (in real implementation, this would use the Gitee API)
        print(f"[API] Fetching fresh data for {owner}/{repo}")
        data = self._analyze_repository(owner, repo)

        # Save to cache
        self._save_to_cache(repo_url, data)

        return data

    def _parse_repo_url(self, repo_url: str) -> tuple[str, str]:
        """
        Parse owner and repo from various Gitee URL formats

        Supported formats:
        - https://gitee.com/owner/repo
        - https://gitee.com/owner/repo.git
        - https://z.gitee.cn/owner/repos/owner/repo/sources
        - https://z.gitee.cn/owner/repos/owner/repo

        Args:
            repo_url: Gitee repository URL

        Returns:
            Tuple of (owner, repo)

        Raises:
            ValueError: If URL format is not recognized
        """
        # Try standard gitee.com format first
        match = re.search(r"gitee\.com/([^/]+)/([^/]+?)(?:\.git)?(?:/|$)", repo_url)
        if match:
            owner, repo = match.groups()
            return owner, repo

        # Try z.gitee.cn premium format: /owner/repos/owner/repo/sources
        match = re.search(r"z\.gitee\.cn/([^/]+)/repos/([^/]+)/([^/]+)", repo_url)
        if match:
            namespace, owner, repo = match.groups()
            # Use the owner from repos path
            return owner, repo

        raise ValueError(f"Invalid Gitee URL format: {repo_url}. Supported formats: gitee.com/owner/repo or z.gitee.cn/namespace/repos/owner/repo")

    def _analyze_repository(self, owner: str, repo: str) -> Dict[str, Any]:
        """
        Analyze a specific repository

        This is a template method that would make actual API calls
        in a production implementation.
        """
        # This would make real API calls to Gitee API endpoints
        return {
            "repo_name": f"{owner}/{repo}",
            "languages": [],
            "has_dockerfile": False,
            "has_kubernetes": False,
            "has_cicd": False,
            "has_iac": False,
            "ml_frameworks": [],
            "commit_count": 0,
            "pr_count": 0,
            "issue_count": 0
        }

    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers"""
        headers = {
            "Content-Type": "application/json"
        }
        # Note: Gitee uses access_token as query param, not Authorization header
        return headers

    def _get_api_base_url(self, owner: str = None, repo_url: str = None) -> str:
        """
        Determine which API base URL to use based on the repository

        Args:
            owner: Repository owner (may contain z.gitee.cn prefix)
            repo_url: Full repository URL

        Returns:
            API base URL to use
        """
        # Check if this is an enterprise repo
        if repo_url and "z.gitee.cn" in repo_url:
            return self.enterprise_base_url
        if owner and owner.startswith("z.gitee.cn"):
            return self.enterprise_base_url

        # Default to public API
        return self.base_url

    def _get_token_for_url(self, url: str) -> Optional[str]:
        """
        Get the appropriate token based on the URL

        Args:
            url: The URL being accessed

        Returns:
            The appropriate access token
        """
        if "z.gitee.cn" in url or self.enterprise_base_url in url:
            return self.token  # Enterprise token
        else:
            # Public token for gitee.com. If only `token` is provided (common),
            # fall back to it to avoid accidentally making unauthenticated calls.
            return self.public_token or self.token

    def _get_params(self, params: Dict[str, Any] = None, url: str = "") -> Dict[str, Any]:
        """
        Get API request parameters with access token

        Args:
            params: Additional parameters
            url: The URL being accessed (to determine which token to use)

        Returns:
            Parameters dict with access token
        """
        if params is None:
            params = {}

        # Gitee requires access_token as a query parameter
        # Use the appropriate token based on the URL
        token = self._get_token_for_url(url)
        if token:
            params["access_token"] = token

        return params

    def _get_cache_path(self, url: str) -> Path:
        """
        Generate cache file path based on Gitee URL

        Args:
            url: Gitee repository or user URL

        Returns:
            Path to cache file
        """
        # Try to parse owner/repo from URL
        try:
            owner, repo = self._parse_repo_url(url)
            # Create path-like structure: owner/repo.json
            cache_path = self.cache_dir / owner / f"{repo}.json"
            # Ensure parent directory exists
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            return cache_path
        except ValueError:
            pass

        # Try to extract user from URL (e.g., https://gitee.com/username)
        user_match = re.search(r"gitee\.com/([^/]+)$", url)
        if user_match:
            username = user_match.group(1)
            # Create path-like structure: users/username.json
            cache_path = self.cache_dir / "users" / f"{username}.json"
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            return cache_path

        # Fallback to hashed URL if pattern doesn't match
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return self.cache_dir / f"{url_hash}.json"

    def _load_from_cache(self, repo_url: str) -> Optional[Dict[str, Any]]:
        """
        Load cached data for a repository

        Args:
            repo_url: Gitee repository URL

        Returns:
            Cached data if exists, None otherwise
        """
        cache_path = self._get_cache_path(repo_url)

        if cache_path.exists():
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    print(f"[Cache] Loaded data from cache: {cache_path}")
                    return cached_data
            except (json.JSONDecodeError, IOError) as e:
                print(f"[Cache] Error loading cache file {cache_path}: {e}")
                return None

        return None

    def _save_to_cache(self, repo_url: str, data: Dict[str, Any]) -> None:
        """
        Save repository data to cache

        Args:
            repo_url: Gitee repository URL
            data: Data to cache
        """
        cache_path = self._get_cache_path(repo_url)

        try:
            # Add metadata to cached data
            cached_data = {
                "cached_at": datetime.now().isoformat(),
                "repo_url": repo_url,
                "data": data
            }

            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cached_data, f, indent=2, ensure_ascii=False)

            print(f"[Cache] Saved data to cache: {cache_path}")
        except IOError as e:
            print(f"[Cache] Error saving cache file {cache_path}: {e}")

    def fetch_commit_data(self, owner: str, repo: str, commit_sha: str, is_enterprise: bool = False) -> Dict[str, Any]:
        """
        Fetch detailed commit data from Gitee API

        Args:
            owner: Repository owner
            repo: Repository name
            commit_sha: Commit SHA hash
            is_enterprise: Whether this is an enterprise (z.gitee.cn) repository

        Returns:
            Detailed commit data including files changed and diffs
        """
        import requests

        # Use appropriate API base URL
        base_url = self.enterprise_base_url if is_enterprise else self.base_url
        api_url = f"{base_url}/repos/{owner}/{repo}/commits/{commit_sha}"
        print(f"[API] Fetching commit data from {api_url}")

        try:
            response = requests.get(
                api_url,
                headers=self._get_headers(),
                params=self._get_params(url=api_url),
                timeout=30
            )
            response.raise_for_status()

            commit_data = response.json()

            return commit_data

        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            # Try to get more detailed error info from response
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_body = e.response.json()
                    error_detail = f"{e} - Response: {error_body}"
                except:
                    error_detail = f"{e} - Response text: {e.response.text}"

            print(f"[API] Error fetching commit {commit_sha}: {error_detail}")
            raise Exception(f"Failed to fetch commit data: {error_detail}")

    def fetch_commits_list(self, owner: str, repo: str, limit: int = 100, is_enterprise: bool = False, **kwargs) -> List[Dict[str, Any]]:
        """
        Fetch list of commits from a repository

        Args:
            owner: Repository owner
            repo: Repository name
            limit: Maximum number of commits to fetch
            is_enterprise: Whether this is an enterprise (z.gitee.cn) repository
            **kwargs: Additional API parameters (e.g., since, until)

        Returns:
            List of commit summaries
        """
        import requests

        # Use appropriate API base URL
        base_url = self.enterprise_base_url if is_enterprise else self.base_url
        api_url = f"{base_url}/repos/{owner}/{repo}/commits"

        print(f"[API] Fetching commits list from {api_url}")

        try:
            # Combine limit parameter with auth parameters and additional kwargs
            base_params = {"per_page": min(limit, 100)}
            base_params.update(kwargs)  # Add since/until/etc parameters
            params = self._get_params(base_params, url=api_url)

            response = requests.get(
                api_url,
                headers=self._get_headers(),
                params=params,
                timeout=30
            )
            response.raise_for_status()

            commits_list = response.json()

            return commits_list

        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            # Try to get more detailed error info from response
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_body = e.response.json()
                    error_detail = f"{e} - Response: {error_body}"
                except:
                    error_detail = f"{e} - Response text: {e.response.text}"

            print(f"[API] Error fetching commits list: {error_detail}")
            raise Exception(f"Failed to fetch commits list: {error_detail}")

    def _get_commit_cache_path(self, owner: str, repo: str, commit_sha: str) -> Path:
        """
        Generate cache file path for a specific commit

        Args:
            owner: Repository owner
            repo: Repository name
            commit_sha: Commit SHA hash

        Returns:
            Path to commit cache file
        """
        cache_path = self.cache_dir / owner / repo / "commits" / f"{commit_sha}.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        return cache_path

    def _get_commits_list_cache_path(self, owner: str, repo: str) -> Path:
        """
        Generate cache file path for commits list

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Path to commits list cache file
        """
        cache_path = self.cache_dir / owner / repo / "commits_list.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        return cache_path

    def _load_commit_from_cache(self, owner: str, repo: str, commit_sha: str) -> Optional[Dict[str, Any]]:
        """
        Load cached commit data

        Args:
            owner: Repository owner
            repo: Repository name
            commit_sha: Commit SHA hash

        Returns:
            Cached commit data if exists, None otherwise
        """
        cache_path = self._get_commit_cache_path(owner, repo, commit_sha)

        if cache_path.exists():
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    print(f"[Cache] Loaded commit data from cache: {cache_path}")
                    return cached_data
            except (json.JSONDecodeError, IOError) as e:
                print(f"[Cache] Error loading cache file {cache_path}: {e}")
                return None

        return None

    def _load_commits_list_from_cache(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """
        Load cached commits list

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Cached commits list if exists, None otherwise
        """
        cache_path = self._get_commits_list_cache_path(owner, repo)

        if cache_path.exists():
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    print(f"[Cache] Loaded commits list from cache: {cache_path}")
                    return cached_data
            except (json.JSONDecodeError, IOError) as e:
                print(f"[Cache] Error loading cache file {cache_path}: {e}")
                return None

        return None

    def _save_commit_to_cache(self, owner: str, repo: str, commit_sha: str, data: Dict[str, Any]) -> None:
        """
        Save commit data to cache

        Args:
            owner: Repository owner
            repo: Repository name
            commit_sha: Commit SHA hash
            data: Commit data to cache
        """
        cache_path = self._get_commit_cache_path(owner, repo, commit_sha)

        try:
            cached_data = {
                "cached_at": datetime.now().isoformat(),
                "commit_sha": commit_sha,
                "repo": f"{owner}/{repo}",
                "data": data
            }

            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cached_data, f, indent=2, ensure_ascii=False)

            print(f"[Cache] Saved commit data to cache: {cache_path}")
        except IOError as e:
            print(f"[Cache] Error saving cache file {cache_path}: {e}")

    def _save_commits_list_to_cache(self, owner: str, repo: str, data: List[Dict[str, Any]]) -> None:
        """
        Save commits list to cache

        Args:
            owner: Repository owner
            repo: Repository name
            data: Commits list to cache
        """
        cache_path = self._get_commits_list_cache_path(owner, repo)

        try:
            cached_data = {
                "cached_at": datetime.now().isoformat(),
                "repo": f"{owner}/{repo}",
                "data": data
            }

            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cached_data, f, indent=2, ensure_ascii=False)

            print(f"[Cache] Saved commits list to cache: {cache_path}")
        except IOError as e:
            print(f"[Cache] Error saving cache file {cache_path}: {e}")

    def fetch_collaborators(self, owner: str, repo: str, use_cache: bool = True, is_enterprise: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch list of repository collaborators/members from Gitee API

        Args:
            owner: Repository owner
            repo: Repository name
            use_cache: Whether to use cached data if available
            is_enterprise: Whether this is an enterprise (z.gitee.cn) repository

        Returns:
            List of collaborators with their information
        """
        # Check cache first if enabled
        if use_cache:
            cached_data = self._load_collaborators_from_cache(owner, repo)
            if cached_data is not None:
                return cached_data.get("data", cached_data)

        # Make API request
        import requests

        # Use appropriate API base URL
        base_url = self.enterprise_base_url if is_enterprise else self.base_url
        api_url = f"{base_url}/repos/{owner}/{repo}/collaborators"

        print(f"[API] Fetching collaborators from {api_url}")

        try:
            # Gitee API supports pagination
            params = self._get_params({"per_page": 100, "page": 1}, url=api_url)

            response = requests.get(
                api_url,
                headers=self._get_headers(),
                params=params,
                timeout=30
            )
            response.raise_for_status()

            collaborators = response.json()

            # Save to cache
            self._save_collaborators_to_cache(owner, repo, collaborators)

            return collaborators

        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            # Try to get more detailed error info from response
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_body = e.response.json()
                    error_detail = f"{e} - Response: {error_body}"
                except:
                    error_detail = f"{e} - Response text: {e.response.text}"

            print(f"[API] Error fetching collaborators: {error_detail}")
            raise Exception(f"Failed to fetch collaborators: {error_detail}")

    def _get_collaborators_cache_path(self, owner: str, repo: str) -> Path:
        """
        Generate cache file path for collaborators list

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Path to collaborators cache file
        """
        cache_path = self.cache_dir / owner / repo / "collaborators.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        return cache_path

    def _load_collaborators_from_cache(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """
        Load cached collaborators list

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Cached collaborators list if exists, None otherwise
        """
        cache_path = self._get_collaborators_cache_path(owner, repo)

        if cache_path.exists():
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    print(f"[Cache] Loaded collaborators from cache: {cache_path}")
                    return cached_data
            except (json.JSONDecodeError, IOError) as e:
                print(f"[Cache] Error loading cache file {cache_path}: {e}")
                return None

        return None

    def _save_collaborators_to_cache(self, owner: str, repo: str, data: List[Dict[str, Any]]) -> None:
        """
        Save collaborators list to cache

        Args:
            owner: Repository owner
            repo: Repository name
            data: Collaborators list to cache
        """
        cache_path = self._get_collaborators_cache_path(owner, repo)

        try:
            cached_data = {
                "cached_at": datetime.now().isoformat(),
                "repo": f"{owner}/{repo}",
                "data": data
            }

            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cached_data, f, indent=2, ensure_ascii=False)

            print(f"[Cache] Saved collaborators to cache: {cache_path}")
        except IOError as e:
            print(f"[Cache] Error saving cache file {cache_path}: {e}")
