"""
Contributor clustering module for analyzing GitHub repository contributors.
Clusters contributors based on their names and emails from commits_list.json files.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict
from difflib import SequenceMatcher

from evaluator.paths import get_data_dir

class ContributorCluster:
    """Represents a cluster of contributor identities that likely belong to the same person."""

    def __init__(self):
        self.names: Set[str] = set()
        self.emails: Set[str] = set()
        self.commit_count: int = 0
        self.commits: List[str] = []  # SHA list

    def add_identity(self, name: str, email: str, commit_sha: str):
        """Add a contributor identity to this cluster."""
        self.names.add(name)
        self.emails.add(email)
        self.commits.append(commit_sha)
        self.commit_count += 1

    def get_primary_name(self) -> str:
        """Get the most representative name (shortest non-generic one)."""
        if not self.names:
            return "Unknown"
        # Filter out generic names
        non_generic = [n for n in self.names if n.lower() not in ['user', 'unknown', 'anonymous']]
        if non_generic:
            return min(non_generic, key=len)
        return min(self.names, key=len)

    def get_primary_email(self) -> str:
        """Get the most representative email."""
        if not self.emails:
            return "no-email"
        # Prefer non-noreply emails
        non_noreply = [e for e in self.emails if 'noreply' not in e.lower()]
        if non_noreply:
            return min(non_noreply, key=len)
        return min(self.emails, key=len)

    def to_dict(self) -> Dict:
        """Convert cluster to dictionary representation."""
        return {
            "primary_name": self.get_primary_name(),
            "primary_email": self.get_primary_email(),
            "all_names": sorted(list(self.names)),
            "all_emails": sorted(list(self.emails)),
            "commit_count": self.commit_count,
            "commits": self.commits
        }


class ContributorClusterer:
    """Clusters contributors based on name and email similarity."""

    def __init__(self, name_similarity_threshold: float = 0.85, email_domain_weight: float = 0.5):
        self.name_similarity_threshold = name_similarity_threshold
        self.email_domain_weight = email_domain_weight
        self.clusters: List[ContributorCluster] = []
        self.email_to_cluster: Dict[str, ContributorCluster] = {}
        self.name_to_clusters: Dict[str, List[ContributorCluster]] = defaultdict(list)

    def _normalize_name(self, name: str) -> str:
        """Normalize name for comparison."""
        return name.lower().strip()

    def _normalize_email(self, email: str) -> str:
        """Normalize email for comparison."""
        return email.lower().strip()

    def _get_email_username(self, email: str) -> str:
        """Extract username from email."""
        return email.split('@')[0] if '@' in email else email

    def _get_email_domain(self, email: str) -> str:
        """Extract domain from email."""
        return email.split('@')[1] if '@' in email else ""

    def _name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two names."""
        n1 = self._normalize_name(name1)
        n2 = self._normalize_name(name2)

        if n1 == n2:
            return 1.0

        # Check if one is substring of another
        if n1 in n2 or n2 in n1:
            return 0.9

        # Use sequence matcher
        return SequenceMatcher(None, n1, n2).ratio()

    def _email_similarity(self, email1: str, email2: str) -> float:
        """Calculate similarity between two emails."""
        e1 = self._normalize_email(email1)
        e2 = self._normalize_email(email2)

        if e1 == e2:
            return 1.0

        u1, d1 = self._get_email_username(e1), self._get_email_domain(e1)
        u2, d2 = self._get_email_username(e2), self._get_email_domain(e2)

        # Same username, different domain
        if u1 == u2:
            return 0.8

        # Same domain, similar username
        if d1 == d2 and d1:
            username_sim = SequenceMatcher(None, u1, u2).ratio()
            return 0.5 + 0.3 * username_sim

        return SequenceMatcher(None, e1, e2).ratio()

    def _should_merge(self, cluster: ContributorCluster, name: str, email: str) -> bool:
        """Determine if a contributor should be merged into a cluster."""
        # Exact email match
        if email in cluster.emails:
            return True

        # Check name similarity with any name in cluster
        for cluster_name in cluster.names:
            if self._name_similarity(name, cluster_name) >= self.name_similarity_threshold:
                # If names are similar, check email similarity
                for cluster_email in cluster.emails:
                    if self._email_similarity(email, cluster_email) > 0.6:
                        return True

        # Check email username match with different name
        email_username = self._get_email_username(email)
        for cluster_email in cluster.emails:
            cluster_username = self._get_email_username(cluster_email)
            if email_username == cluster_username and email_username:
                return True

        return False

    def add_contributor(self, name: str, email: str, commit_sha: str):
        """Add a contributor and cluster them appropriately."""
        norm_email = self._normalize_email(email)

        # Check if this email already belongs to a cluster
        if norm_email in self.email_to_cluster:
            cluster = self.email_to_cluster[norm_email]
            cluster.add_identity(name, email, commit_sha)
            return

        # Try to find a matching cluster
        candidate_clusters = self.name_to_clusters.get(self._normalize_name(name), [])

        for cluster in candidate_clusters:
            if self._should_merge(cluster, name, email):
                cluster.add_identity(name, email, commit_sha)
                self.email_to_cluster[norm_email] = cluster
                return

        # No matching cluster found, create new one
        new_cluster = ContributorCluster()
        new_cluster.add_identity(name, email, commit_sha)
        self.clusters.append(new_cluster)
        self.email_to_cluster[norm_email] = new_cluster
        self.name_to_clusters[self._normalize_name(name)].append(new_cluster)

    def get_clusters(self) -> List[Dict]:
        """Get all clusters as dictionaries, sorted by commit count."""
        clusters_data = [cluster.to_dict() for cluster in self.clusters]
        return sorted(clusters_data, key=lambda x: x['commit_count'], reverse=True)


def load_commits_list(repo_path: Path) -> List[Dict]:
    """Load commits_list.json from a repository path."""
    commits_file = repo_path / "commits_list.json"

    if not commits_file.exists():
        raise FileNotFoundError(f"commits_list.json not found at {commits_file}")

    with open(commits_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Handle both formats: {"data": [...]} and [...]
    if isinstance(data, list):
        return data
    elif isinstance(data, dict):
        return data.get('data', [])
    else:
        return []


def cluster_contributors(commits: List[Dict]) -> List[Dict]:
    """Cluster contributors from a list of commits."""
    clusterer = ContributorClusterer()

    for commit in commits:
        commit_data = commit.get('commit', {})
        sha = commit.get('sha', 'unknown')

        # Process author
        author = commit_data.get('author', {})
        if author.get('name') and author.get('email'):
            clusterer.add_contributor(
                author['name'],
                author['email'],
                sha
            )

        # Process committer (if different from author)
        committer = commit_data.get('committer', {})
        if committer.get('name') and committer.get('email'):
            # Only add if it's a different identity
            if (committer['name'] != author.get('name') or
                committer['email'] != author.get('email')):
                clusterer.add_contributor(
                    committer['name'],
                    committer['email'],
                    sha
                )

    return clusterer.get_clusters()


def process_repository(owner: str, repo: str, data_dir: Optional[Path] = None) -> Dict:
    """Process a single repository and cluster its contributors."""
    if data_dir is None:
        data_dir = get_data_dir()
    repo_path = data_dir / owner / repo

    if not repo_path.exists():
        raise FileNotFoundError(f"Repository path not found: {repo_path}")

    commits = load_commits_list(repo_path)
    clusters = cluster_contributors(commits)

    return {
        "repo": f"{owner}/{repo}",
        "total_commits": len(commits),
        "total_contributors": len(clusters),
        "contributors": clusters
    }


def process_all_repositories(data_dir: Optional[Path] = None) -> List[Dict]:
    """Process all repositories in the data directory."""
    if data_dir is None:
        data_dir = get_data_dir()
    results = []

    if not data_dir.exists():
        print(f"Data directory not found: {data_dir}")
        return results

    # Iterate through owner/repo structure
    for owner_dir in data_dir.iterdir():
        if not owner_dir.is_dir() or owner_dir.name.startswith('.'):
            continue

        for repo_dir in owner_dir.iterdir():
            if not repo_dir.is_dir() or repo_dir.name.startswith('.'):
                continue

            commits_file = repo_dir / "commits_list.json"
            if not commits_file.exists():
                continue

            try:
                result = process_repository(owner_dir.name, repo_dir.name, data_dir)
                results.append(result)
                print(f"Processed {result['repo']}: {result['total_contributors']} contributors")
            except Exception as e:
                print(f"Error processing {owner_dir.name}/{repo_dir.name}: {e}")

    return results


def main():
    """Main function to demonstrate contributor clustering."""
    import sys

    # Get data directory from command line or use default
    input_path = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else get_data_dir()

    print(f"Processing repositories in {input_path.absolute()}")
    print("-" * 60)

    results = []

    # Check if input_path is a specific repo directory (has commits_list.json)
    if (input_path / "commits_list.json").exists():
        # Extract owner and repo from path
        # Assuming path format: .../data/owner/repo or owner/repo
        parts = input_path.parts
        if len(parts) >= 2:
            repo_name = parts[-1]
            owner_name = parts[-2]

            # Get the parent directory (data dir)
            data_dir = input_path.parent.parent

            try:
                result = process_repository(owner_name, repo_name, data_dir)
                results.append(result)
                print(f"Processed {result['repo']}: {result['total_contributors']} contributors")
            except Exception as e:
                print(f"Error processing {owner_name}/{repo_name}: {e}")
        else:
            print(f"Error: Cannot determine owner/repo from path {input_path}")
    else:
        # Process all repositories in the data directory
        results = process_all_repositories(input_path)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    total_repos = len(results)
    total_contributors = sum(r['total_contributors'] for r in results)
    total_commits = sum(r['total_commits'] for r in results)

    print(f"Total repositories processed: {total_repos}")
    print(f"Total contributors: {total_contributors}")
    print(f"Total commits: {total_commits}")

    if results:
        print("\n" + "=" * 60)
        print("TOP REPOSITORIES BY CONTRIBUTOR COUNT")
        print("=" * 60)

        sorted_results = sorted(results, key=lambda x: x['total_contributors'], reverse=True)
        for result in sorted_results[:10]:
            print(f"{result['repo']}: {result['total_contributors']} contributors, {result['total_commits']} commits")

    # Save detailed results
    if len(results) == 1 and (input_path / "commits_list.json").exists():
        # Single repo mode: save in the repo directory
        output_file = input_path / "contributor_clusters.json"
    else:
        # Multi-repo mode: save in the data directory
        output_file = input_path / "contributor_clusters.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nDetailed results saved to: {output_file}")


if __name__ == "__main__":
    main()
