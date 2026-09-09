"""
GitHub data collector

Collects engineering activity data from GitHub using the GitHub API.
"""

from typing import Dict, List, Optional, Any
import re
import os
import json
from pathlib import Path

from evaluator.paths import get_data_dir


class GitHubCollector:
    """Collect data from GitHub"""

    def __init__(self, token: Optional[str] = None, data_dir: Optional[str] = None):
        """
        Initialize GitHub collector

        Args:
            token: GitHub personal access token for API access
            data_dir: Directory for collected GitHub data
        """
        self.token = token
        self.base_url = "https://api.github.com"
        self.data_dir = Path(data_dir).expanduser() if data_dir else get_data_dir()

        self.data_dir.mkdir(parents=True, exist_ok=True)

    def collect_user_data(self, username: str) -> Dict[str, Any]:
        """
        Collect comprehensive data for a GitHub user

        Args:
            username: GitHub username

        Returns:
            Dictionary containing collected data
        """
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

        return data

    def collect_repo_data(self, repo_url: str) -> Dict[str, Any]:
        """
        Collect data from a specific repository

        Args:
            repo_url: GitHub repository URL

        Returns:
            Dictionary containing repository data
        """
        # Parse repo URL
        match = re.search(r"github\.com/([^/]+)/([^/]+)", repo_url)
        if not match:
            raise ValueError(f"Invalid GitHub URL: {repo_url}")

        owner, repo = match.groups()
        repo = repo.replace(".git", "")

        # Fetch data (in real implementation, this would use the GitHub API)
        print(f"[API] Fetching fresh data for {owner}/{repo}")
        data = self._analyze_repository(owner, repo)

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

            next_url = getattr(response, 'links', {}).get('next', {}).get('url')
            while next_url:
                if not next_url.startswith(api_url + '?'):
                    raise RuntimeError("Unexpected commit pagination URL")
                response = requests.get(next_url, headers=self._get_headers(), timeout=30)
                response.raise_for_status()
                commit_data.setdefault('files', []).extend(response.json().get('files', []))
                next_url = getattr(response, 'links', {}).get('next', {}).get('url')
            if len(commit_data.get('files', [])) >= 3000:
                raise RuntimeError("GitHub commit exceeds the complete file listing limit")

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

    def fetch_check_runs_for_ref(
        self,
        owner: str,
        repo: str,
        ref: str,
        limit: int = 100,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Fetch GitHub Checks API runs for a commit SHA, branch, or tag.

        Args:
            owner: Repository owner
            repo: Repository name
            ref: Commit SHA, branch name, or tag name
            limit: Maximum number of check runs to fetch
            **kwargs: Additional API parameters, such as status, filter,
                check_name, or app_id

        Returns:
            List of check run objects
        """
        payload = self._get_json(
            f"/repos/{owner}/{repo}/commits/{ref}/check-runs",
            params={"per_page": min(limit, 100), **kwargs},
        )
        if isinstance(payload, dict):
            return payload.get("check_runs", [])[:limit]
        return []

    def fetch_check_run_annotations(
        self,
        owner: str,
        repo: str,
        check_run_id: int,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Fetch annotations for a check run.

        Args:
            owner: Repository owner
            repo: Repository name
            check_run_id: GitHub check run ID
            limit: Maximum number of annotations to fetch

        Returns:
            List of check run annotations
        """
        payload = self._get_json(
            f"/repos/{owner}/{repo}/check-runs/{check_run_id}/annotations",
            params={"per_page": min(limit, 100)},
        )
        return payload[:limit] if isinstance(payload, list) else []

    def fetch_commit_statuses(
        self,
        owner: str,
        repo: str,
        ref: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Fetch legacy commit status contexts for a commit SHA, branch, or tag.

        Args:
            owner: Repository owner
            repo: Repository name
            ref: Commit SHA, branch name, or tag name
            limit: Maximum number of statuses to fetch

        Returns:
            List of status context objects in reverse chronological order
        """
        payload = self._get_json(
            f"/repos/{owner}/{repo}/commits/{ref}/statuses",
            params={"per_page": min(limit, 100)},
        )
        return payload[:limit] if isinstance(payload, list) else []

    def fetch_combined_status(self, owner: str, repo: str, ref: str) -> Dict[str, Any]:
        """
        Fetch the combined legacy status for a commit SHA, branch, or tag.

        Args:
            owner: Repository owner
            repo: Repository name
            ref: Commit SHA, branch name, or tag name

        Returns:
            Combined status object with state and status contexts
        """
        payload = self._get_json(f"/repos/{owner}/{repo}/commits/{ref}/status")
        return payload if isinstance(payload, dict) else {}

    def fetch_workflow_runs(
        self,
        owner: str,
        repo: str,
        limit: int = 100,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Fetch GitHub Actions workflow runs for a repository.

        Args:
            owner: Repository owner
            repo: Repository name
            limit: Maximum number of workflow runs to fetch
            **kwargs: Additional API parameters, such as actor, branch, event,
                status, head_sha, created, or exclude_pull_requests

        Returns:
            List of workflow run objects
        """
        payload = self._get_json(
            f"/repos/{owner}/{repo}/actions/runs",
            params={"per_page": min(limit, 100), **kwargs},
        )
        if isinstance(payload, dict):
            return payload.get("workflow_runs", [])[:limit]
        return []

    def fetch_workflow_run_jobs(
        self,
        owner: str,
        repo: str,
        run_id: int,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Fetch jobs for a GitHub Actions workflow run.

        Args:
            owner: Repository owner
            repo: Repository name
            run_id: GitHub Actions workflow run ID
            limit: Maximum number of jobs to fetch

        Returns:
            List of workflow job objects
        """
        payload = self._get_json(
            f"/repos/{owner}/{repo}/actions/runs/{run_id}/jobs",
            params={"per_page": min(limit, 100)},
        )
        if isinstance(payload, dict):
            return payload.get("jobs", [])[:limit]
        return []

    def fetch_workflow(
        self,
        owner: str,
        repo: str,
        workflow_id: str,
    ) -> Dict[str, Any]:
        """
        Fetch GitHub Actions workflow metadata by workflow ID, file name, or path.

        Args:
            owner: Repository owner
            repo: Repository name
            workflow_id: Workflow ID, workflow file name, or workflow file path

        Returns:
            Workflow metadata object
        """
        payload = self._get_json(
            f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}"
        )
        return payload if isinstance(payload, dict) else {}

    def fetch_ci_quality_signals(
        self,
        owner: str,
        repo: str,
        ref: str,
        *,
        include_annotations: bool = False,
        include_workflow_jobs: bool = False,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Fetch CI and quality evidence for a commit SHA, branch, or tag.

        This combines Checks API results, legacy commit statuses, combined
        status, and GitHub Actions workflow runs matching the ref as head_sha.
        Use it as repository-local context for matched commits or PR head SHAs.

        Args:
            owner: Repository owner
            repo: Repository name
            ref: Commit SHA, branch name, or tag name
            include_annotations: Whether to fetch check run annotations
            include_workflow_jobs: Whether to fetch jobs for matching workflow
                runs
            limit: Maximum item count per endpoint

        Returns:
            Dictionary containing check runs, statuses, combined status, and
            workflow runs. Endpoint errors are captured under warnings.
        """
        warnings: List[str] = []

        def collect(label: str, callback):
            try:
                return callback()
            except Exception as exc:
                warnings.append(f"{label}: {exc}")
                return [] if label != "combined_status" else {}

        check_runs = collect(
            "check_runs",
            lambda: self.fetch_check_runs_for_ref(owner, repo, ref, limit=limit),
        )
        statuses = collect(
            "commit_statuses",
            lambda: self.fetch_commit_statuses(owner, repo, ref, limit=limit),
        )
        combined_status = collect(
            "combined_status",
            lambda: self.fetch_combined_status(owner, repo, ref),
        )

        if include_annotations:
            for check_run in check_runs:
                check_run_id = (
                    check_run.get("id") if isinstance(check_run, dict) else None
                )
                if not check_run_id:
                    continue
                check_run["annotations"] = collect(
                    f"check_run_annotations:{check_run_id}",
                    lambda check_run_id=check_run_id: self.fetch_check_run_annotations(
                        owner,
                        repo,
                        check_run_id,
                        limit=limit,
                    ),
                )

        workflow_runs = collect(
            "workflow_runs",
            lambda: self.fetch_workflow_runs(owner, repo, limit=limit, head_sha=ref),
        )

        if include_workflow_jobs:
            for workflow_run in workflow_runs:
                run_id = workflow_run.get("id") if isinstance(workflow_run, dict) else None
                if not run_id:
                    continue
                workflow_run["jobs"] = collect(
                    f"workflow_run_jobs:{run_id}",
                    lambda run_id=run_id: self.fetch_workflow_run_jobs(
                        owner,
                        repo,
                        run_id,
                        limit=limit,
                    ),
                )

        return {
            "repo": f"{owner}/{repo}",
            "ref": ref,
            "check_runs": check_runs,
            "commit_statuses": statuses,
            "combined_status": combined_status,
            "workflow_runs": workflow_runs,
            "warnings": warnings,
        }

    def _get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Fetch JSON from the GitHub REST API."""
        import requests

        api_url = f"{self.base_url}{path}"
        print(f"[API] Fetching GitHub data from {api_url} with params: {params or {}}")

        try:
            response = requests.get(
                api_url,
                headers=self._get_headers(),
                params=params or {},
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"[API] Error fetching GitHub data: {e}")
            raise Exception(f"Failed to fetch GitHub data: {e}")


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
