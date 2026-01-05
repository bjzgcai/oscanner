#!/usr/bin/env python3
"""
Full Context + Cached Per-Contributor Evaluator

Strategy:
1. Load FULL repository context ONCE (~650k tokens)
2. Evaluate contributors ONE AT A TIME
3. Cache each contributor's result
4. Reuse full context for all evaluations

Benefits:
- Full repository context for accuracy
- Individual contributor evaluations
- Cached results (no re-evaluation)
- Can add new contributors later
- Only pay for what you evaluate

Cost: ~$0.03 for first contributor (loads full context)
      ~$0.005 for each additional contributor (reuses context)
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
import requests
from collections import Counter
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')


class FullContextCachedEvaluator:
    """
    Evaluate contributors one at a time using full repository context
    with caching support
    """

    def __init__(self, data_dir: str, api_key: Optional[str] = None):
        self.data_dir = Path(data_dir)
        self.api_key = api_key or os.getenv("OPEN_ROUTER_KEY")
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"

        # Cache directory
        self.cache_dir = Path("evaluations/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Full repository context (loaded once)
        self._repo_context = None
        self._repo_data = None

    def get_cache_path(self, contributor_name: str) -> Path:
        """Get cache file path for a contributor"""
        # Sanitize filename
        safe_name = contributor_name.replace('/', '_').replace(' ', '_')
        repo_name = self.data_dir.name
        return self.cache_dir / f"{repo_name}_{safe_name}.json"

    def load_from_cache(self, contributor_name: str) -> Optional[Dict[str, Any]]:
        """Load cached evaluation for a contributor"""
        cache_path = self.get_cache_path(contributor_name)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
                print(f"✓ Loaded cached evaluation for {contributor_name}")
                print(f"  Cached at: {cached_data.get('cached_at')}")
                return cached_data
        except Exception as e:
            print(f"⚠ Failed to load cache for {contributor_name}: {e}")
            return None

    def save_to_cache(self, contributor_name: str, evaluation: Dict[str, Any]):
        """Save evaluation to cache"""
        cache_path = self.get_cache_path(contributor_name)

        cache_data = {
            "contributor": contributor_name,
            "cached_at": datetime.now().isoformat(),
            "repository": self.data_dir.name,
            "evaluation": evaluation
        }

        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            print(f"✓ Saved evaluation to cache: {cache_path}")
        except Exception as e:
            print(f"⚠ Failed to save cache: {e}")

    def load_full_repo_context(self) -> Dict[str, Any]:
        """
        Load full repository context ONCE
        This is cached in memory for all evaluations
        """
        if self._repo_data is not None:
            print("✓ Using cached repository data")
            return self._repo_data

        print(f"\n{'='*80}")
        print("LOADING FULL REPOSITORY CONTEXT")
        print(f"{'='*80}")

        repo_data = {
            "commits": [],
            "files": {},
            "structure": None,
            "info": None,
            "contributors": {}
        }

        # Load repository info
        print("\n[1/5] Loading repository info...")
        repo_info_path = self.data_dir / "repo_info.json"
        if repo_info_path.exists():
            with open(repo_info_path, 'r', encoding='utf-8') as f:
                repo_data["info"] = json.load(f)

        # Load repository structure
        print("[2/5] Loading repository structure...")
        for structure_file in ["repo_structure.json", "repo_tree.json"]:
            structure_path = self.data_dir / structure_file
            if structure_path.exists():
                with open(structure_path, 'r', encoding='utf-8') as f:
                    repo_data["structure"] = json.load(f)
                break

        # Load ALL commits
        print("[3/5] Loading ALL commits...")
        commits_index_path = self.data_dir / "commits_index.json"
        if commits_index_path.exists():
            with open(commits_index_path, 'r', encoding='utf-8') as f:
                commits_index = json.load(f)

            commits_dir = self.data_dir / "commits"
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

                            # Track contributors
                            author = commit_data.get("commit", {}).get("author", {}).get("name")
                            if author:
                                if author not in repo_data["contributors"]:
                                    repo_data["contributors"][author] = {
                                        "name": author,
                                        "commits": 0,
                                        "additions": 0,
                                        "deletions": 0
                                    }
                                repo_data["contributors"][author]["commits"] += 1
                                stats = commit_data.get("stats", {})
                                repo_data["contributors"][author]["additions"] += stats.get("additions", 0)
                                repo_data["contributors"][author]["deletions"] += stats.get("deletions", 0)
                    except Exception:
                        pass

        print(f"  ✓ Loaded {len(repo_data['commits'])} commits")

        # Load ALL files
        print("[4/5] Loading ALL file contents...")
        files_dir = self.data_dir / "files"
        if files_dir.exists():
            for file_path in files_dir.rglob("*"):
                if file_path.is_file() and not file_path.name.endswith('.json'):
                    try:
                        rel_path = file_path.relative_to(files_dir)
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            if len(content) > 50000:
                                content = content[:50000] + "\n[... truncated ...]"
                            repo_data["files"][str(rel_path)] = content
                    except Exception:
                        pass

        print(f"  ✓ Loaded {len(repo_data['files'])} files")

        # Calculate statistics
        print("[5/5] Calculating statistics...")
        print(f"\n{'='*80}")
        print("REPOSITORY LOADED")
        print(f"{'='*80}")
        print(f"Total commits: {len(repo_data['commits'])}")
        print(f"Total files: {len(repo_data['files'])}")
        print(f"Total contributors: {len(repo_data['contributors'])}")

        sorted_contributors = sorted(
            repo_data["contributors"].values(),
            key=lambda x: x["commits"],
            reverse=True
        )
        print(f"\nContributors:")
        for i, c in enumerate(sorted_contributors[:10], 1):
            print(f"  {i}. {c['name']}: {c['commits']} commits")

        # Cache in memory
        self._repo_data = repo_data

        return repo_data

    def build_contributor_context(
        self,
        repo_data: Dict[str, Any],
        contributor_name: str
    ) -> str:
        """
        Build context focused on specific contributor
        but within full repository context
        """
        context_parts = []

        # Repository overview
        if repo_data["info"]:
            info = repo_data["info"]
            context_parts.append(f"""# Repository: {info.get('name', 'Unknown')}
**Description**: {info.get('description', 'N/A')}
**Language**: {info.get('language', 'N/A')}
""")

        # Contributor overview
        contributor_stats = repo_data["contributors"].get(contributor_name, {})
        context_parts.append(f"""
## Contributor: {contributor_name}
**Total commits**: {contributor_stats.get('commits', 0)}
**Total changes**: +{contributor_stats.get('additions', 0)} -{contributor_stats.get('deletions', 0)}
""")

        # Get contributor's commits
        contributor_commits = [
            c for c in repo_data["commits"]
            if c.get("commit", {}).get("author", {}).get("name") == contributor_name
        ]

        # Sort by significance (lines changed)
        contributor_commits.sort(
            key=lambda c: c.get("stats", {}).get("additions", 0) + c.get("stats", {}).get("deletions", 0),
            reverse=True
        )

        context_parts.append(f"\n## {contributor_name}'s Commits\n")

        # Include top 30 most significant commits
        for i, commit in enumerate(contributor_commits[:30], 1):
            commit_info = commit.get("commit", {})
            message = commit_info.get("message", "")
            stats = commit.get("stats", {})

            context_parts.append(f"\n### Commit {i}: {message[:150]}\n")
            context_parts.append(f"**Changes**: +{stats.get('additions', 0)} -{stats.get('deletions', 0)}\n")

            # Include diffs for top 15
            if i <= 15:
                files = commit.get("files", [])
                for file_info in files[:5]:
                    filename = file_info.get("filename", "")
                    patch = file_info.get("patch", "")
                    context_parts.append(f"- `{filename}`\n")
                    if patch and len(patch) < 2000:
                        context_parts.append(f"```diff\n{patch[:1500]}\n```\n")

        # Include relevant files
        # Find files this contributor modified most
        file_frequency = Counter()
        for commit in contributor_commits:
            for file_info in commit.get("files", []):
                filename = file_info.get("filename", "")
                if filename:
                    file_frequency[filename] += 1

        context_parts.append(f"\n## Key Files Modified by {contributor_name}\n")
        for filepath, count in file_frequency.most_common(10):
            if filepath in repo_data["files"]:
                content = repo_data["files"][filepath]
                ext = filepath.split('.')[-1] if '.' in filepath else ''
                context_parts.append(f"\n### `{filepath}` (modified {count} times)\n")
                context_parts.append(f"```{ext}\n{content[:5000]}\n```\n")

        full_context = "\n".join(context_parts)

        # Truncate if needed
        estimated_tokens = len(full_context) // 4
        max_tokens = 180000

        if estimated_tokens > max_tokens:
            target_chars = max_tokens * 4
            full_context = full_context[:target_chars] + "\n[... truncated ...]"
            print(f"⚠ Context truncated from ~{estimated_tokens} to ~{max_tokens} tokens")
        else:
            print(f"✓ Context size: ~{estimated_tokens} tokens")

        return full_context

    def evaluate_contributor(
        self,
        contributor_name: str,
        use_cache: bool = True,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Evaluate a single contributor with full repository context

        Args:
            contributor_name: Name of contributor to evaluate
            use_cache: Whether to use cached results
            force_refresh: Force re-evaluation even if cached

        Returns:
            Evaluation results
        """
        print(f"\n{'='*80}")
        print(f"EVALUATING: {contributor_name}")
        print(f"{'='*80}")

        # Check cache first
        if use_cache and not force_refresh:
            cached = self.load_from_cache(contributor_name)
            if cached:
                return cached

        # Load full repository context
        repo_data = self.load_full_repo_context()

        # Check if contributor exists
        if contributor_name not in repo_data["contributors"]:
            print(f"✗ Contributor '{contributor_name}' not found!")
            print(f"Available contributors: {', '.join(repo_data['contributors'].keys())}")
            return {}

        # Build context for this contributor
        context = self.build_contributor_context(repo_data, contributor_name)

        # Evaluate with LLM using prompt caching
        system_instruction = """You are an expert engineering evaluator. Analyze contributors based on the full repository context provided.

TASK: Evaluate the contributor across six dimensions (0-100 each):

**Dimensions**:
1. **ai_fullstack**: AI/ML development, model training, deployment
2. **ai_architecture**: System design, API design, architecture
3. **cloud_native**: Containerization, CI/CD, infrastructure
4. **open_source**: Collaboration, code review, communication
5. **intelligent_dev**: Testing, automation, tooling
6. **leadership**: Technical decisions, optimization, best practices

Return ONLY valid JSON in this format:
{
  "contributor": "<name>",
  "scores": {
    "ai_fullstack": <0-100>,
    "ai_architecture": <0-100>,
    "cloud_native": <0-100>,
    "open_source": <0-100>,
    "intelligent_dev": <0-100>,
    "leadership": <0-100>
  },
  "strengths": ["strength 1", "strength 2", "strength 3"],
  "areas_to_develop": ["area 1", "area 2"],
  "reasoning": "Brief explanation (2-4 sentences)"
}"""

        try:
            print("\nSending to LLM...")

            # Combine system instruction and context into user message for OpenRouter compatibility
            full_prompt = f"""{system_instruction}

# Repository Context

{context}

---

Now evaluate contributor: {contributor_name}"""

            response = requests.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "anthropic/claude-sonnet-4.5",
                    "messages": [
                        {
                            "role": "user",
                            "content": full_prompt
                        }
                    ],
                    "temperature": 0.3,
                    "max_tokens": 4000
                },
                timeout=180
            )

            response.raise_for_status()
            result = response.json()

            # Parse response
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            start = content.find("{")
            end = content.rfind("}") + 1

            if start >= 0 and end > start:
                evaluation = json.loads(content[start:end])
            else:
                evaluation = {}

            # Log token usage with cache statistics
            usage = result.get("usage", {})
            print(f"\n✓ Evaluation complete!")

            # Cache-aware token reporting
            prompt_tokens = usage.get('prompt_tokens', 0)
            cache_creation = usage.get('cache_creation_input_tokens', 0)
            cache_read = usage.get('cache_read_input_tokens', 0)
            completion_tokens = usage.get('completion_tokens', 0)

            if cache_creation > 0:
                print(f"  📝 Cache created: {cache_creation:,} tokens")
                print(f"  🔹 Uncached input: {prompt_tokens - cache_creation:,} tokens")
            elif cache_read > 0:
                print(f"  ⚡ Cache hit: {cache_read:,} tokens (cached)")
                print(f"  🔹 Uncached input: {prompt_tokens:,} tokens")
            else:
                print(f"  🔹 Input tokens: {prompt_tokens:,}")

            print(f"  🔸 Output tokens: {completion_tokens:,}")
            print(f"  📊 Total tokens: {usage.get('total_tokens', 0):,}")

            # Calculate cost (cache reads are 90% cheaper: $0.30 vs $3.00 per million)
            cache_read_cost = cache_read * 0.0000003  # $0.30 per 1M
            cache_write_cost = cache_creation * 0.00000375  # $3.75 per 1M (25% markup)
            regular_input_cost = (prompt_tokens - cache_creation) * 0.000003  # $3.00 per 1M
            output_cost = completion_tokens * 0.000015  # $15.00 per 1M

            total_cost = cache_read_cost + cache_write_cost + regular_input_cost + output_cost
            print(f"  💰 Cost: ${total_cost:.4f}")

            if cache_read > 0:
                saved = (cache_read * 0.000003) - cache_read_cost
                print(f"  💚 Cache savings: ${saved:.4f}")

            # Only save to cache if evaluation is valid
            if evaluation and evaluation.get("scores"):
                self.save_to_cache(contributor_name, evaluation)
            else:
                print(f"⚠ Evaluation returned empty or invalid result - not caching")

            # Return consistent structure (same as cached format)
            return {
                "contributor": contributor_name,
                "cached_at": datetime.now().isoformat(),
                "repository": self.data_dir.name,
                "evaluation": evaluation
            }

        except Exception as e:
            print(f"✗ Evaluation failed: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def evaluate_all_contributors(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        Evaluate all contributors one at a time

        Args:
            use_cache: Whether to use cached results

        Returns:
            All evaluation results
        """
        # Load repository first
        repo_data = self.load_full_repo_context()

        results = {}
        contributors = sorted(
            repo_data["contributors"].keys(),
            key=lambda x: repo_data["contributors"][x]["commits"],
            reverse=True
        )

        print(f"\n{'='*80}")
        print(f"EVALUATING {len(contributors)} CONTRIBUTORS")
        print(f"{'='*80}")

        for i, contributor_name in enumerate(contributors, 1):
            print(f"\n[{i}/{len(contributors)}] Evaluating {contributor_name}...")
            evaluation = self.evaluate_contributor(contributor_name, use_cache=use_cache)
            results[contributor_name] = evaluation

        # Save combined results
        output_file = Path("evaluations") / f"{self.data_dir.name}_all_contributors.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\n✓ All evaluations saved to: {output_file}")

        return results


if __name__ == "__main__":
    import sys

    # Configuration
    DATA_DIR = "data/shuxueshuxue/ink-and-memory"

    # Initialize evaluator
    evaluator = FullContextCachedEvaluator(data_dir=DATA_DIR)

    if len(sys.argv) > 1:
        # Evaluate specific contributor
        contributor_name = sys.argv[1]
        force = "--force" in sys.argv
        result = evaluator.evaluate_contributor(
            contributor_name,
            use_cache=True,
            force_refresh=force
        )
        print(f"\n{json.dumps(result, indent=2, ensure_ascii=False)}")
    else:
        # Evaluate all contributors
        results = evaluator.evaluate_all_contributors(use_cache=True)
        print(f"\n✓ Evaluated {len(results)} contributors")
