#!/usr/bin/env python3
"""
Full Repository Evaluator - Analyze entire repository and ALL contributors

This script loads:
- ALL commits (not just top 30)
- ALL files
- Repository structure
- Pull requests data

Then evaluates ALL contributors in ONE comprehensive API call.

Token usage: ~650k tokens (NOT 12,000k!)
Cost: ~$0.03-0.05 per repository
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
import requests
from collections import Counter
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')


class FullRepoEvaluator:
    """Evaluate entire repository and all contributors in one comprehensive analysis"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPEN_ROUTER_KEY")
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"

    def load_all_data(self, data_dir: Path) -> Dict[str, Any]:
        """
        Load ALL data from repository extraction

        Args:
            data_dir: Path to extracted data directory

        Returns:
            Complete repository data
        """
        print(f"\n{'='*80}")
        print("LOADING REPOSITORY DATA")
        print(f"{'='*80}")

        repo_data = {
            "commits": [],
            "files": {},
            "structure": None,
            "info": None,
            "contributors": {}
        }

        # 1. Load repository info
        print("\n[1/5] Loading repository info...")
        repo_info_path = data_dir / "repo_info.json"
        if repo_info_path.exists():
            with open(repo_info_path, 'r', encoding='utf-8') as f:
                repo_data["info"] = json.load(f)
            print(f"  ✓ Repository: {repo_data['info'].get('name', 'Unknown')}")

        # 2. Load repository structure
        print("\n[2/5] Loading repository structure...")
        for structure_file in ["repo_structure.json", "repo_tree.json"]:
            structure_path = data_dir / structure_file
            if structure_path.exists():
                with open(structure_path, 'r', encoding='utf-8') as f:
                    repo_data["structure"] = json.load(f)
                print(f"  ✓ Loaded from {structure_file}")
                break

        # 3. Load ALL commits
        print("\n[3/5] Loading ALL commits...")
        commits_index_path = data_dir / "commits_index.json"
        if commits_index_path.exists():
            with open(commits_index_path, 'r', encoding='utf-8') as f:
                commits_index = json.load(f)
            print(f"  ✓ Found {len(commits_index)} commits in index")

            # Load detailed commit data
            commits_dir = data_dir / "commits"
            loaded_count = 0
            for commit_info in commits_index:
                commit_sha = commit_info.get("hash") or commit_info.get("sha")
                if not commit_sha:
                    continue

                commit_json_path = commits_dir / f"{commit_sha}.json"
                if commit_json_path.exists():
                    try:
                        with open(commit_json_path, 'r', encoding='utf-8') as f:
                            commit_data = json.load(f)
                            repo_data["commits"].append(commit_data)
                            loaded_count += 1

                            # Track contributors
                            author = commit_data.get("commit", {}).get("author", {}).get("name")
                            if author:
                                if author not in repo_data["contributors"]:
                                    repo_data["contributors"][author] = {
                                        "name": author,
                                        "commits": 0,
                                        "additions": 0,
                                        "deletions": 0,
                                        "files": set()
                                    }
                                repo_data["contributors"][author]["commits"] += 1
                                stats = commit_data.get("stats", {})
                                repo_data["contributors"][author]["additions"] += stats.get("additions", 0)
                                repo_data["contributors"][author]["deletions"] += stats.get("deletions", 0)

                                # Track files modified
                                for file_info in commit_data.get("files", []):
                                    filename = file_info.get("filename")
                                    if filename:
                                        repo_data["contributors"][author]["files"].add(filename)

                    except Exception as e:
                        print(f"  ⚠ Failed to load {commit_sha}: {e}")

            print(f"  ✓ Loaded {loaded_count} detailed commits")

        # 4. Load ALL files
        print("\n[4/5] Loading ALL file contents...")
        files_dir = data_dir / "files"
        if files_dir.exists():
            loaded_files = 0
            for file_path in files_dir.rglob("*"):
                if file_path.is_file() and not file_path.name.endswith('.json'):
                    try:
                        # Get relative path from files directory
                        rel_path = file_path.relative_to(files_dir)
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            # Truncate very large files
                            if len(content) > 50000:
                                content = content[:50000] + "\n\n[... file truncated ...]"
                            repo_data["files"][str(rel_path)] = content
                            loaded_files += 1
                    except Exception as e:
                        # Skip binary files or unreadable files
                        pass

            print(f"  ✓ Loaded {loaded_files} file contents")

        # 5. Calculate statistics
        print("\n[5/5] Calculating statistics...")
        # Convert sets to lists for JSON serialization
        for contributor in repo_data["contributors"].values():
            contributor["files"] = list(contributor["files"])
            contributor["files_count"] = len(contributor["files"])

        total_additions = sum(c.get("stats", {}).get("additions", 0) for c in repo_data["commits"])
        total_deletions = sum(c.get("stats", {}).get("deletions", 0) for c in repo_data["commits"])

        print(f"\n{'='*80}")
        print("REPOSITORY SUMMARY")
        print(f"{'='*80}")
        print(f"Total commits: {len(repo_data['commits'])}")
        print(f"Total files loaded: {len(repo_data['files'])}")
        print(f"Total contributors: {len(repo_data['contributors'])}")
        print(f"Total changes: +{total_additions} -{total_deletions}")
        print(f"\nTop contributors:")
        sorted_contributors = sorted(
            repo_data["contributors"].values(),
            key=lambda x: x["commits"],
            reverse=True
        )
        for i, contrib in enumerate(sorted_contributors[:10], 1):
            print(f"  {i}. {contrib['name']}: {contrib['commits']} commits, "
                  f"+{contrib['additions']} -{contrib['deletions']}")

        return repo_data

    def estimate_tokens(self, repo_data: Dict[str, Any]) -> int:
        """Estimate total token count for the repository data"""
        # Calculate approximate tokens
        commits_text = json.dumps(repo_data["commits"][:100])  # Sample
        files_text = "\n".join(list(repo_data["files"].values())[:10])  # Sample

        commits_tokens = len(commits_text) * len(repo_data["commits"]) // 100 // 4
        files_tokens = sum(len(content) for content in repo_data["files"].values()) // 4
        metadata_tokens = 50000 // 4  # Rough estimate for structure, info, etc.

        total_tokens = commits_tokens + files_tokens + metadata_tokens
        return total_tokens

    def build_full_context(self, repo_data: Dict[str, Any], max_tokens: int = 180000) -> str:
        """
        Build comprehensive context from all repository data

        Args:
            repo_data: Complete repository data
            max_tokens: Maximum tokens to use

        Returns:
            Formatted context string
        """
        context_parts = []

        # Repository overview
        if repo_data["info"]:
            info = repo_data["info"]
            context_parts.append(f"""# Repository: {info.get('name', 'Unknown')}

**Description**: {info.get('description', 'N/A')}
**Language**: {info.get('language', 'N/A')}
**Stars**: {info.get('stargazers_count', 0)}
**Forks**: {info.get('forks_count', 0)}
**Created**: {info.get('created_at', 'N/A')}
**Updated**: {info.get('updated_at', 'N/A')}
""")

        # Repository structure
        if repo_data["structure"]:
            context_parts.append("\n## Repository Structure\n")
            structure = repo_data["structure"]
            tree = structure.get("tree", structure) if isinstance(structure, dict) else structure

            directories = set()
            file_types = Counter()

            for item in tree[:200]:
                path = item.get("path", "")
                if item.get("type") == "tree":
                    directories.add(path.split('/')[0])
                elif item.get("type") == "blob":
                    ext = path.split('.')[-1] if '.' in path else 'no_ext'
                    file_types[ext] += 1

            context_parts.append(f"**Directories**: {', '.join(sorted(directories)[:20])}\n")
            context_parts.append(f"**File types**: {dict(file_types.most_common(15))}\n")

        # Contributors overview
        context_parts.append("\n## Contributors\n")
        sorted_contributors = sorted(
            repo_data["contributors"].values(),
            key=lambda x: x["commits"],
            reverse=True
        )
        for i, contrib in enumerate(sorted_contributors[:20], 1):
            context_parts.append(
                f"{i}. **{contrib['name']}**: {contrib['commits']} commits, "
                f"{contrib['files_count']} files, "
                f"+{contrib['additions']} -{contrib['deletions']}\n"
            )

        # Commits analysis (sample most significant commits)
        context_parts.append("\n## Significant Commits\n")
        # Sort commits by lines changed
        significant_commits = sorted(
            repo_data["commits"],
            key=lambda c: c.get("stats", {}).get("additions", 0) + c.get("stats", {}).get("deletions", 0),
            reverse=True
        )[:50]  # Top 50 most significant commits

        for i, commit in enumerate(significant_commits, 1):
            commit_info = commit.get("commit", {})
            author = commit_info.get("author", {}).get("name", "Unknown")
            message = commit_info.get("message", "")
            stats = commit.get("stats", {})

            context_parts.append(f"\n### Commit {i}: {message[:100]}\n")
            context_parts.append(f"**Author**: {author}\n")
            context_parts.append(f"**Changes**: +{stats.get('additions', 0)} -{stats.get('deletions', 0)}\n")

            # Include diffs for top 20 commits
            if i <= 20:
                files = commit.get("files", [])
                if files:
                    context_parts.append("**Files**:\n")
                    for file_info in files[:5]:
                        filename = file_info.get("filename", "")
                        patch = file_info.get("patch", "")
                        context_parts.append(f"- `{filename}`\n")
                        if patch and len(patch) < 2000:
                            context_parts.append(f"```diff\n{patch[:1000]}\n```\n")

        # Key file contents
        context_parts.append("\n## Key Files\n")
        # Determine key files by frequency of modification
        file_frequency = Counter()
        for commit in repo_data["commits"]:
            for file_info in commit.get("files", []):
                filename = file_info.get("filename", "")
                if filename:
                    file_frequency[filename] += 1

        key_files = [f for f, _ in file_frequency.most_common(20)]
        for filepath in key_files:
            if filepath in repo_data["files"]:
                content = repo_data["files"][filepath]
                ext = filepath.split('.')[-1] if '.' in filepath else ''
                context_parts.append(f"\n### `{filepath}`\n")
                context_parts.append(f"```{ext}\n{content[:5000]}\n```\n")

        # Combine and truncate if needed
        full_context = "\n".join(context_parts)

        # Check token limit
        estimated_tokens = len(full_context) // 4
        if estimated_tokens > max_tokens:
            # Truncate to fit
            target_chars = max_tokens * 4
            full_context = full_context[:target_chars]
            full_context += "\n\n[... Context truncated to fit token limit ...]"
            print(f"\n⚠ Context truncated from ~{estimated_tokens} to ~{max_tokens} tokens")
        else:
            print(f"\n✓ Context size: ~{estimated_tokens} tokens")

        return full_context

    def evaluate_all_contributors(
        self,
        repo_data: Dict[str, Any],
        context: str
    ) -> Dict[str, Any]:
        """
        Evaluate all contributors using LLM with full repository context

        Args:
            repo_data: Complete repository data
            context: Formatted context string

        Returns:
            Evaluation results for all contributors
        """
        if not self.api_key:
            print("[Error] No API key configured!")
            return {}

        print(f"\n{'='*80}")
        print("EVALUATING ALL CONTRIBUTORS")
        print(f"{'='*80}")

        # Build prompt
        contributors_list = sorted(
            repo_data["contributors"].values(),
            key=lambda x: x["commits"],
            reverse=True
        )

        contributor_names = [c["name"] for c in contributors_list[:10]]  # Top 10
        print(f"\nEvaluating: {', '.join(contributor_names)}")

        prompt = f"""You are an expert engineering evaluator. Analyze the COMPLETE repository data below and evaluate EACH contributor's engineering capabilities.

{context}

TASK: Evaluate the following contributors across six dimensions (0-100 each):

**Contributors to evaluate**: {', '.join(contributor_names)}

**Dimensions**:
1. **ai_fullstack**: AI/ML development, model training, deployment
2. **ai_architecture**: System design, API design, architecture
3. **cloud_native**: Containerization, CI/CD, infrastructure
4. **open_source**: Collaboration, code review, communication
5. **intelligent_dev**: Testing, automation, tooling
6. **leadership**: Technical decisions, optimization, best practices

IMPORTANT: Return ONLY a valid JSON object. No text before or after.

Format:
{{
  "contributors": {{
    "contributor_name_1": {{
      "ai_fullstack": <0-100>,
      "ai_architecture": <0-100>,
      "cloud_native": <0-100>,
      "open_source": <0-100>,
      "intelligent_dev": <0-100>,
      "leadership": <0-100>,
      "reasoning": "Brief explanation of this contributor's strengths and areas to develop"
    }},
    "contributor_name_2": {{ ... }},
    ...
  }},
  "team_analysis": "Overall team dynamics, collaboration patterns, and recommendations (3-5 sentences)"
}}"""

        try:
            print("\nSending request to LLM...")
            response = requests.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "anthropic/claude-sonnet-4.5",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 8000
                },
                timeout=180
            )

            response.raise_for_status()
            result = response.json()

            # Parse response
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Extract JSON
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                evaluation_results = json.loads(content[start:end])
            else:
                evaluation_results = {}

            # Log token usage
            usage = result.get("usage", {})
            print(f"\n✓ Evaluation complete!")
            print(f"  Input tokens: {usage.get('prompt_tokens', 0):,}")
            print(f"  Output tokens: {usage.get('completion_tokens', 0):,}")
            print(f"  Total tokens: {usage.get('total_tokens', 0):,}")

            # Estimate cost (Claude Sonnet 4.5 pricing)
            input_cost = usage.get('prompt_tokens', 0) * 0.000003
            output_cost = usage.get('completion_tokens', 0) * 0.000015
            total_cost = input_cost + output_cost
            print(f"  Estimated cost: ${total_cost:.4f}")

            return evaluation_results

        except Exception as e:
            print(f"[Error] Evaluation failed: {e}")
            return {}

    def run_full_analysis(self, data_dir: str) -> Dict[str, Any]:
        """
        Run complete repository analysis

        Args:
            data_dir: Path to extracted data directory

        Returns:
            Complete analysis results
        """
        data_path = Path(data_dir)

        # Load all data
        repo_data = self.load_all_data(data_path)

        # Estimate tokens
        estimated_tokens = self.estimate_tokens(repo_data)
        print(f"\nEstimated total tokens: ~{estimated_tokens:,}")

        # Build context
        context = self.build_full_context(repo_data)

        # Evaluate all contributors
        evaluation_results = self.evaluate_all_contributors(repo_data, context)

        # Save results
        output_dir = Path("evaluations")
        output_dir.mkdir(exist_ok=True)

        repo_name = repo_data.get("info", {}).get("name", "unknown_repo")
        output_file = output_dir / f"{repo_name}_full_analysis.json"

        full_results = {
            "repository": repo_data.get("info"),
            "contributors_stats": repo_data.get("contributors"),
            "evaluation": evaluation_results,
            "metadata": {
                "total_commits": len(repo_data["commits"]),
                "total_files": len(repo_data["files"]),
                "total_contributors": len(repo_data["contributors"])
            }
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(full_results, f, indent=2, ensure_ascii=False)

        print(f"\n✓ Full analysis saved to: {output_file}")

        # Display summary
        self.display_results(evaluation_results)

        return full_results

    def display_results(self, evaluation_results: Dict[str, Any]):
        """Display evaluation results in a readable format"""
        print(f"\n{'='*80}")
        print("EVALUATION RESULTS")
        print(f"{'='*80}")

        contributors = evaluation_results.get("contributors", {})
        for name, scores in contributors.items():
            print(f"\n## {name}")
            print(f"  ai_fullstack:     {scores.get('ai_fullstack', 0):3d}/100")
            print(f"  ai_architecture:  {scores.get('ai_architecture', 0):3d}/100")
            print(f"  cloud_native:     {scores.get('cloud_native', 0):3d}/100")
            print(f"  open_source:      {scores.get('open_source', 0):3d}/100")
            print(f"  intelligent_dev:  {scores.get('intelligent_dev', 0):3d}/100")
            print(f"  leadership:       {scores.get('leadership', 0):3d}/100")
            if "reasoning" in scores:
                print(f"  Reasoning: {scores['reasoning']}")

        if "team_analysis" in evaluation_results:
            print(f"\n{'='*80}")
            print("TEAM ANALYSIS")
            print(f"{'='*80}")
            print(evaluation_results["team_analysis"])

        print(f"\n{'='*80}")


if __name__ == "__main__":
    # Configuration
    DATA_DIR = "data/shuxueshuxue/ink-and-memory"

    # Run full analysis
    evaluator = FullRepoEvaluator()
    results = evaluator.run_full_analysis(DATA_DIR)
