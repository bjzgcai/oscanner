"""
LLM-based commit evaluator for assessing engineer skill levels

Analyzes commits, diffs, and code changes to evaluate engineering capabilities
across six key dimensions.
"""

import os
import json
from typing import Dict, List, Any, Optional
import requests


class CommitEvaluator:
    """Evaluates engineer skill based on commit history and code changes"""

    def __init__(self, api_key: Optional[str] = None, max_input_tokens: int = 190000):
        """
        Initialize the commit evaluator

        Args:
            api_key: OpenRouter API key for LLM calls
            max_input_tokens: Maximum tokens to send to LLM (default: 100k)
        """
        self.api_key = api_key or os.getenv("OPEN_ROUTER_KEY")
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.max_input_tokens = max_input_tokens

        # Six dimensions of engineering capability
        self.dimensions = {
            "ai_fullstack": "AI Model Full-Stack Development",
            "ai_architecture": "AI Native Architecture Design",
            "cloud_native": "Cloud Native Engineering",
            "open_source": "Open Source Collaboration",
            "intelligent_dev": "Intelligent Development",
            "leadership": "Engineering Leadership"
        }

    def evaluate_engineer(
        self,
        commits: List[Dict[str, Any]],
        username: str,
        max_commits: int = 20
    ) -> Dict[str, Any]:
        """
        Evaluate an engineer based on their commits

        Args:
            commits: List of commit data from GitHub API
            username: GitHub username of the engineer
            max_commits: Maximum number of commits to analyze

        Returns:
            Dictionary containing scores for each dimension and analysis
        """
        if not commits:
            return self._get_empty_evaluation(username)

        # Sample commits if there are too many
        analyzed_commits = commits[:max_commits]

        # Build analysis context from commits
        context = self._build_commit_context(analyzed_commits, username)

        # Call LLM for evaluation
        scores = self._evaluate_with_llm(context, username)

        return {
            "username": username,
            "total_commits_analyzed": len(analyzed_commits),
            "total_commits": len(commits),
            "scores": scores,
            "commits_summary": self._summarize_commits(analyzed_commits)
        }

    def _build_commit_context(
        self,
        commits: List[Dict[str, Any]],
        username: str
    ) -> str:
        """
        Build context from commits for LLM analysis

        Args:
            commits: List of commit data
            username: GitHub username

        Returns:
            Formatted context string
        """
        context_parts = []

        for i, commit in enumerate(commits[:10], 1):  # Detailed analysis of top 10
            commit_info = commit.get("commit", {})
            message = commit_info.get("message", "")
            author = commit_info.get("author", {})
            stats = commit.get("stats", {})
            files = commit.get("files", [])

            # Build commit summary
            commit_summary = f"""
Commit #{i}:
Message: {message[:200]}
Author: {author.get('name', 'Unknown')}
Date: {author.get('date', 'Unknown')}
Changes: +{stats.get('additions', 0)} -{stats.get('deletions', 0)} lines
Files changed: {len(files)}
"""

            # Add file changes (limit to important files)
            if files:
                commit_summary += "\nKey files modified:\n"
                for file_info in files[:5]:  # Top 5 files
                    filename = file_info.get("filename", "")
                    status = file_info.get("status", "")
                    additions = file_info.get("additions", 0)
                    deletions = file_info.get("deletions", 0)
                    commit_summary += f"  - {filename} ({status}) +{additions} -{deletions}\n"

                    # Include patch/diff for significant changes
                    patch = file_info.get("patch", "")
                    if patch and len(patch) < 1000:  # Include small diffs
                        commit_summary += f"\n```diff\n{patch[:500]}\n```\n"

            context_parts.append(commit_summary)

        return "\n\n".join(context_parts)

    def _evaluate_with_llm(
        self,
        context: str,
        username: str
    ) -> Dict[str, int]:
        """
        Use LLM to evaluate commits and return scores

        Args:
            context: Commit context for analysis
            username: GitHub username

        Returns:
            Dictionary of scores (0-100) for each dimension
        """
        if not self.api_key:
            print("[Warning] No API key configured, using fallback evaluation")
            return self._fallback_evaluation(context)

        # Build evaluation prompt
        prompt = self._build_evaluation_prompt(context, username)

        try:
            # Call OpenRouter API
            response = requests.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "anthropic/claude-haiku-4.5",
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2000
                },
                timeout=60
            )

            response.raise_for_status()
            result = response.json()

            # Parse LLM response
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            scores = self._parse_llm_response(content)

            return scores

        except Exception as e:
            print(f"[Error] LLM evaluation failed: {e}")
            return self._fallback_evaluation(context)

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text (rough approximation)

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count (1 token ≈ 4 characters)
        """
        return len(text) // 4

    def _truncate_context(self, context: str, max_tokens: int) -> str:
        """
        Truncate context to fit within token limit

        Args:
            context: Context string to truncate
            max_tokens: Maximum allowed tokens

        Returns:
            Truncated context
        """
        current_tokens = self._estimate_tokens(context)

        if current_tokens <= max_tokens:
            return context

        # Calculate target character count
        target_chars = max_tokens * 4

        # Truncate and add notice
        truncated = context[:target_chars]
        truncated += "\n\n[... Context truncated to fit token limit ...]"

        print(f"[Info] Context truncated from ~{current_tokens} to ~{max_tokens} tokens")

        return truncated

    def _build_evaluation_prompt(self, context: str, username: str) -> str:
        """Build the evaluation prompt for the LLM"""
        # Reserve tokens for the prompt template (approximately 500 tokens)
        prompt_template_tokens = 500
        max_context_tokens = self.max_input_tokens - prompt_template_tokens

        # Truncate context if needed
        context = self._truncate_context(context, max_context_tokens)

        return f"""You are an expert engineering evaluator. Analyze the following GitHub commits from user "{username}" and evaluate their engineering capabilities across six dimensions. Each score should be 0-100.

COMMITS TO ANALYZE:
{context}

EVALUATION DIMENSIONS:

1. **AI Model Full-Stack (ai_fullstack)**: Assess AI/ML model development, training, optimization, deployment. Look for: ML frameworks usage, model architecture, training pipelines, inference optimization, model serving.

2. **AI Native Architecture (ai_architecture)**: Evaluate AI-first system design, API design, microservices. Look for: API design, service architecture, documentation, integration patterns, scalable design.

3. **Cloud Native Engineering (cloud_native)**: Assess containerization, IaC, CI/CD. Look for: Docker/Kubernetes, deployment automation, infrastructure code, cloud services, DevOps practices.

4. **Open Source Collaboration (open_source)**: Evaluate collaboration quality, communication. Look for: Clear commit messages, issue references, code review participation, refactoring, bug fixes.

5. **Intelligent Development (intelligent_dev)**: Assess automation, tooling, testing. Look for: Test coverage, automation scripts, build tools, linting/formatting, development efficiency.

6. **Engineering Leadership (leadership)**: Evaluate technical decision-making, optimization. Look for: Architecture decisions, performance optimization, security considerations, best practices, code quality.

IMPORTANT: Return ONLY a valid JSON object with scores. No explanatory text before or after.

Format:
{{
  "ai_fullstack": <0-100>,
  "ai_architecture": <0-100>,
  "cloud_native": <0-100>,
  "open_source": <0-100>,
  "intelligent_dev": <0-100>,
  "leadership": <0-100>,
  "reasoning": "Brief explanation of the evaluation (2-3 sentences)"
}}"""

    def _parse_llm_response(self, content: str) -> Dict[str, int]:
        """Parse LLM response and extract scores"""
        try:
            # Try to find JSON in response
            start = content.find("{")
            end = content.rfind("}") + 1

            if start >= 0 and end > start:
                json_str = content[start:end]
                data = json.loads(json_str)

                # Extract scores
                scores = {}
                for key in self.dimensions.keys():
                    scores[key] = min(100, max(0, int(data.get(key, 0))))

                # Add reasoning if available
                if "reasoning" in data:
                    scores["reasoning"] = data["reasoning"]

                return scores

        except Exception as e:
            print(f"[Error] Failed to parse LLM response: {e}")

        # Fallback to default scores
        return {key: 50 for key in self.dimensions.keys()}

    def _fallback_evaluation(self, context: str) -> Dict[str, int]:
        """
        Fallback evaluation using keyword analysis when LLM is unavailable
        """
        context_lower = context.lower()

        scores = {}

        # AI Full-Stack
        ai_keywords = ['model', 'training', 'tensorflow', 'pytorch', 'neural', 'ml', 'ai', 'inference']
        scores['ai_fullstack'] = self._count_keywords(context_lower, ai_keywords)

        # AI Architecture
        arch_keywords = ['api', 'architecture', 'design', 'service', 'endpoint', 'microservice']
        scores['ai_architecture'] = self._count_keywords(context_lower, arch_keywords)

        # Cloud Native
        cloud_keywords = ['docker', 'kubernetes', 'k8s', 'ci/cd', 'deploy', 'container', 'cloud']
        scores['cloud_native'] = self._count_keywords(context_lower, cloud_keywords)

        # Open Source
        collab_keywords = ['fix', 'issue', 'pr', 'review', 'merge', 'refactor', 'improve']
        scores['open_source'] = self._count_keywords(context_lower, collab_keywords)

        # Intelligent Development
        dev_keywords = ['test', 'auto', 'script', 'tool', 'lint', 'format', 'cli']
        scores['intelligent_dev'] = self._count_keywords(context_lower, dev_keywords)

        # Leadership
        lead_keywords = ['optimize', 'performance', 'security', 'best practice', 'pattern']
        scores['leadership'] = self._count_keywords(context_lower, lead_keywords)

        scores['reasoning'] = "Evaluation based on keyword analysis (LLM unavailable)"

        return scores

    def _count_keywords(self, text: str, keywords: List[str]) -> int:
        """Count keyword occurrences and return normalized score"""
        count = sum(1 for keyword in keywords if keyword in text)
        # Normalize to 0-100 scale
        max_expected = len(keywords)
        return min(100, int((count / max_expected) * 100))

    def _summarize_commits(self, commits: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary statistics from commits"""
        total_additions = 0
        total_deletions = 0
        files_changed = set()
        languages = set()

        for commit in commits:
            stats = commit.get("stats", {})
            total_additions += stats.get("additions", 0)
            total_deletions += stats.get("deletions", 0)

            for file_info in commit.get("files", []):
                filename = file_info.get("filename", "")
                files_changed.add(filename)

                # Detect language from file extension
                if "." in filename:
                    ext = filename.split(".")[-1]
                    languages.add(ext)

        return {
            "total_additions": total_additions,
            "total_deletions": total_deletions,
            "files_changed": len(files_changed),
            "languages": list(languages)[:10]  # Top 10 languages
        }

    def _get_empty_evaluation(self, username: str) -> Dict[str, Any]:
        """Return empty evaluation when no commits available"""
        return {
            "username": username,
            "total_commits_analyzed": 0,
            "total_commits": 0,
            "scores": {key: 0 for key in self.dimensions.keys()},
            "commits_summary": {
                "total_additions": 0,
                "total_deletions": 0,
                "files_changed": 0,
                "languages": []
            }
        }
