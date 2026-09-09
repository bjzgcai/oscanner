"""
Gitee data collector

Collects engineering activity data from Gitee using the Gitee API.
"""

from typing import Dict, List, Optional, Any
import re
import os
import json
from pathlib import Path

from evaluator.paths import get_data_dir


class GiteeCollector:
    """Collect data from Gitee"""

    def __init__(self, token: Optional[str] = None, public_token: Optional[str] = None, data_dir: Optional[str] = None):
        """
        Initialize Gitee collector

        Args:
            token: Gitee personal access token for enterprise (z.gitee.cn) API access
            public_token: Gitee personal access token for public (gitee.com) API access
            data_dir: Directory for collected Gitee data
        """
        self.token = token  # For z.gitee.cn (enterprise)
        self.public_token = public_token  # For gitee.com (public)
        self.base_url = "https://gitee.com/api/v5"
        self.enterprise_base_url = "https://z.gitee.cn/api/v5"

        from evaluator.paths import get_data_dir
        self.data_dir = Path(data_dir).expanduser() if data_dir else get_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def collect_user_data(self, username: str) -> Dict[str, Any]:
        """
        Collect comprehensive data for a Gitee user

        Args:
            username: Gitee username

        Returns:
            Dictionary containing collected data
        """
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

        return data

    def collect_repo_data(self, repo_url: str) -> Dict[str, Any]:
        """
        Collect data from a specific repository

        Args:
            repo_url: Gitee repository URL (supports gitee.com and z.gitee.cn formats)

        Returns:
            Dictionary containing repository data
        """
        # Parse owner and repo from URL (supports both gitee.com and z.gitee.cn)
        owner, repo = self._parse_repo_url(repo_url)

        # Fetch data (in real implementation, this would use the Gitee API)
        print(f"[API] Fetching fresh data for {owner}/{repo}")
        data = self._analyze_repository(owner, repo)

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
            status = e.response.status_code if e.response is not None else "network error"
            # Gitee credentials are query parameters; never log request exception URLs.
            raise RuntimeError(f"Failed to fetch Gitee commit {commit_sha}: {status}") from None

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

    def fetch_collaborators(self, owner: str, repo: str, is_enterprise: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch list of repository collaborators/members from Gitee API

        Args:
            owner: Repository owner
            repo: Repository name
            is_enterprise: Whether this is an enterprise (z.gitee.cn) repository

        Returns:
            List of collaborators with their information
        """
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
