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

    def _get_cache_path(self, url: str) -> Path:
        """
        Generate cache file path based on GitHub URL

        Args:
            url: GitHub repository or user URL

        Returns:
            Path to cache file
        """
        # Try to extract owner/repo from URL
        repo_match = re.search(r"github\.com/([^/]+)/([^/]+)", url)
        if repo_match:
            owner, repo = repo_match.groups()
            repo = repo.replace(".git", "")
            # Create path-like structure: data/owner/repo.json
            cache_path = self.cache_dir / owner / f"{repo}.json"
            # Ensure parent directory exists
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            return cache_path

        # Try to extract user from URL (e.g., https://github.com/username)
        user_match = re.search(r"github\.com/([^/]+)$", url)
        if user_match:
            username = user_match.group(1)
            # Create path-like structure: data/users/username.json
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
            repo_url: GitHub repository URL

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
            repo_url: GitHub repository URL
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

    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers"""
        headers = {
            "Accept": "application/vnd.github.v3+json"
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    def fetch_commit_data(self, owner: str, repo: str, commit_sha: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Fetch detailed commit data from GitHub API

        Args:
            owner: Repository owner
            repo: Repository name
            commit_sha: Commit SHA hash
            use_cache: Whether to use cached data if available

        Returns:
            Detailed commit data including files changed and diffs
        """
        # Create commit URL for cache key
        commit_url = f"https://github.com/{owner}/{repo}/commit/{commit_sha}"

        # Check cache first if enabled
        if use_cache:
            cached_data = self._load_commit_from_cache(owner, repo, commit_sha)
            if cached_data is not None:
                return cached_data.get("data", cached_data)

        # Make API request
        import requests

        api_url = f"{self.base_url}/repos/{owner}/{repo}/commits/{commit_sha}"
        print(f"[API] Fetching commit data from {api_url}")

        try:
            response = requests.get(api_url, headers=self._get_headers(), timeout=30)
            response.raise_for_status()

            commit_data = response.json()

            # Save to cache
            self._save_commit_to_cache(owner, repo, commit_sha, commit_data)

            return commit_data

        except requests.exceptions.RequestException as e:
            print(f"[API] Error fetching commit {commit_sha}: {e}")
            raise Exception(f"Failed to fetch commit data: {e}")

    def fetch_commits_list(self, owner: str, repo: str, limit: int = 100, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        Fetch list of commits from a repository

        Args:
            owner: Repository owner
            repo: Repository name
            limit: Maximum number of commits to fetch
            use_cache: Whether to use cached data if available

        Returns:
            List of commit summaries
        """
        # Create list URL for cache key
        list_url = f"https://github.com/{owner}/{repo}/commits"

        # Check cache first if enabled
        if use_cache:
            cached_data = self._load_commits_list_from_cache(owner, repo)
            if cached_data is not None:
                return cached_data.get("data", cached_data)

        # Make API request
        import requests

        api_url = f"{self.base_url}/repos/{owner}/{repo}/commits"
        params = {"per_page": min(limit, 100)}

        print(f"[API] Fetching commits list from {api_url}")

        try:
            response = requests.get(api_url, headers=self._get_headers(), params=params, timeout=30)
            response.raise_for_status()

            commits_list = response.json()

            # Save to cache
            self._save_commits_list_to_cache(owner, repo, commits_list)

            return commits_list

        except requests.exceptions.RequestException as e:
            print(f"[API] Error fetching commits list: {e}")
            raise Exception(f"Failed to fetch commits list: {e}")

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
