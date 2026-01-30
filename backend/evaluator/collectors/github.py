"""
GitHub data collector

Collects engineering activity data from GitHub using the GitHub API.
"""

from typing import Dict, List, Optional, Any
import re
import os
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

from evaluator.paths import get_data_dir


class GitHubCollector:
    """Collect data from GitHub"""

    def __init__(self, token: Optional[str] = None, cache_dir: Optional[str] = None):
        """
        Initialize GitHub collector

        Args:
            token: GitHub personal access token for API access
            cache_dir: Directory to store cached GitHub data
        """
        self.token = token
        self.base_url = "https://api.github.com"
        self.cache_dir = Path(cache_dir).expanduser() if cache_dir else get_data_dir()

        # Create cache directory if it doesn't exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def collect_user_data(self, username: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Collect comprehensive data for a GitHub user

        Args:
            username: GitHub username
            use_cache: Whether to use cached data if available

        Returns:
            Dictionary containing collected data
        """
        # Create a pseudo-URL for cache key
        user_url = f"https://github.com/{username}"

        # Check cache first if enabled
        if use_cache:
            cached_data = self._load_from_cache(user_url)
            if cached_data is not None:
                return cached_data.get("data", cached_data)

        # Fetch data (in real implementation, this would use the GitHub API)
        print(f"[API] Fetching fresh data for user {username}")

        # In a real implementation, this would use the GitHub API
        # For now, return a structured template
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
            repo_url: GitHub repository URL
            use_cache: Whether to use cached data if available

        Returns:
            Dictionary containing repository data
        """
        # Check cache first if enabled
        if use_cache:
            cached_data = self._load_from_cache(repo_url)
            if cached_data is not None:
                # Return the actual data, not the metadata wrapper
                return cached_data.get("data", cached_data)

        # Parse repo URL
        match = re.search(r"github\.com/([^/]+)/([^/]+)", repo_url)
        if not match:
            raise ValueError(f"Invalid GitHub URL: {repo_url}")

        owner, repo = match.groups()
        repo = repo.replace(".git", "")

        # Fetch data (in real implementation, this would use the GitHub API)
        print(f"[API] Fetching fresh data for {owner}/{repo}")
        data = self._analyze_repository(owner, repo)

        # Save to cache
        self._save_to_cache(repo_url, data)

        return data

    def _analyze_repository(self, owner: str, repo: str) -> Dict[str, Any]:
        """
        Analyze a specific repository

        This is a template method that would make actual API calls
        in a production implementation.
        """
        # This would make real API calls to:
        # - GET /repos/{owner}/{repo}
        # - GET /repos/{owner}/{repo}/commits
        # - GET /repos/{owner}/{repo}/pulls
        # - GET /repos/{owner}/{repo}/issues
        # - GET /repos/{owner}/{repo}/contents (to scan for specific files)

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

    def _scan_for_patterns(self, contents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Scan repository contents for specific patterns

        Args:
            contents: List of file contents from repository

        Returns:
            Dictionary of detected patterns
        """
        patterns = {
            # ML/AI frameworks
            "ml_frameworks": [
                "tensorflow", "pytorch", "keras", "scikit-learn",
                "transformers", "langchain", "openai"
            ],

            # Cloud native patterns
            "dockerfile": ["Dockerfile"],
            "kubernetes": ["deployment.yaml", "service.yaml", "k8s/"],
            "cicd": [".github/workflows/", ".gitlab-ci.yml", "Jenkinsfile"],
            "iac": ["terraform", "cloudformation", "pulumi"],

            # Automation
            "automation": ["scripts/", ".sh", "Makefile", "tasks.py"],

            # AI tools
            "ai_tools": [".cursor/", "copilot", ".aider"]
        }

        detected = {
            "ml_frameworks": [],
            "dockerfile_count": 0,
            "orchestration_configs": [],
            "cicd_configs": [],
            "iac_files": [],
            "automation_scripts": [],
            "ai_tool_configs": []
        }

        # In a real implementation, scan through file contents
        # and detect patterns

        return detected

    def _analyze_commits(self, commits: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze commit history for patterns

        Args:
            commits: List of commits from API

        Returns:
            Analysis results
        """
        optimization_keywords = [
            "optim", "performance", "speed", "faster", "improve",
            "reduce", "efficient"
        ]

        architecture_keywords = [
            "architect", "design", "refactor", "restructure",
            "pattern", "system"
        ]

        return {
            "optimization_commits": 0,
            "architecture_commits": 0,
            "total_commits": len(commits)
        }

    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers"""
        headers = {
            "Accept": "application/vnd.github.v3+json"
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    def fetch_commit_data(self, owner: str, repo: str, commit_sha: str) -> Dict[str, Any]:
        """
        Fetch detailed commit data from GitHub API

        Args:
            owner: Repository owner
            repo: Repository name
            commit_sha: Commit SHA hash

        Returns:
            Detailed commit data including files changed and diffs
        """
        import requests

        api_url = f"{self.base_url}/repos/{owner}/{repo}/commits/{commit_sha}"
        print(f"[API] Fetching commit data from {api_url}")

        try:
            response = requests.get(api_url, headers=self._get_headers(), timeout=30)
            response.raise_for_status()

            commit_data = response.json()

            return commit_data

        except requests.exceptions.RequestException as e:
            print(f"[API] Error fetching commit {commit_sha}: {e}")
            raise Exception(f"Failed to fetch commit data: {e}")

    def fetch_commits_list(self, owner: str, repo: str, limit: int = 100, **kwargs) -> List[Dict[str, Any]]:
        """
        Fetch list of commits from a repository

        Args:
            owner: Repository owner
            repo: Repository name
            limit: Maximum number of commits to fetch
            **kwargs: Additional API parameters (e.g., since, until)

        Returns:
            List of commit summaries
        """
        import requests

        api_url = f"{self.base_url}/repos/{owner}/{repo}/commits"
        params = {"per_page": min(limit, 100)}

        # Add any additional parameters (e.g., since for incremental fetch)
        params.update(kwargs)

        print(f"[API] Fetching commits list from {api_url} with params: {params}")

        try:
            response = requests.get(api_url, headers=self._get_headers(), params=params, timeout=30)
            response.raise_for_status()

            commits_list = response.json()

            return commits_list

        except requests.exceptions.RequestException as e:
            print(f"[API] Error fetching commits list: {e}")
            raise Exception(f"Failed to fetch commits list: {e}")


# Example implementation with actual API calls (commented out)
"""
import requests

class GitHubCollector:
    def __init__(self, token: Optional[str] = None):
        self.token = token
        self.base_url = "https://api.github.com"
        self.session = requests.Session()
        self.session.headers.update(self._get_headers())

    def collect_user_data(self, username: str) -> Dict[str, Any]:
        # Get user info
        user_response = self.session.get(f"{self.base_url}/users/{username}")
        user_data = user_response.json()

        # Get user repos
        repos_response = self.session.get(f"{self.base_url}/users/{username}/repos")
        repos = repos_response.json()

        # Get events
        events_response = self.session.get(f"{self.base_url}/users/{username}/events")
        events = events_response.json()

        # Analyze data
        return self._process_user_data(user_data, repos, events)
"""
