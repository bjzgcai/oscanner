"""
Enhanced LLM-based commit evaluator with file context support (Moderate approach)

This evaluator supports both:
- Conservative: Diffs only (original behavior)
- Moderate: Diffs + File contents + Repository structure
"""

import os
import json
from typing import Dict, List, Any, Optional
from pathlib import Path
import requests


class CommitEvaluatorModerate:
    """
    Evaluates engineer skill based on commit history and code changes

    Supports loading file contents and repository structure for better context.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        max_input_tokens: int = 190000,
        data_dir: Optional[str] = None,
        mode: str = "moderate"
    ):
        """
        Initialize the commit evaluator

        Args:
            api_key: OpenRouter API key for LLM calls
            max_input_tokens: Maximum tokens to send to LLM (default: 190k)
            data_dir: Directory containing extracted data (e.g., 'data/owner/repo')
            mode: 'conservative' (diffs only) or 'moderate' (diffs + files)
        """
        self.api_key = api_key or os.getenv("OPEN_ROUTER_KEY")
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.max_input_tokens = max_input_tokens
        self.data_dir = Path(data_dir) if data_dir else None
        self.mode = mode

        # Six dimensions of engineering capability
        self.dimensions = {
            "ai_fullstack": "AI Model Full-Stack Development",
            "ai_architecture": "AI Native Architecture Design",
            "cloud_native": "Cloud Native Engineering",
            "open_source": "Open Source Collaboration",
            "intelligent_dev": "Intelligent Development",
            "leadership": "Engineering Leadership"
        }

        # Cache for loaded file contents
        self._file_cache: Dict[str, str] = {}
        self._repo_structure: Optional[Dict[str, Any]] = None

    def evaluate_engineer(
        self,
        commits: List[Dict[str, Any]],
        username: str,
        max_commits: int = None,
        load_files: bool = True,
        use_chunking: bool = True
    ) -> Dict[str, Any]:
        """
        Evaluate an engineer based on their commits

        Args:
            commits: List of commit data (can be from API or local JSON files)
            username: GitHub username of the engineer
            max_commits: Maximum number of commits to analyze (None = all commits)
            load_files: Whether to load file contents (moderate mode)
            use_chunking: Whether to use chunked evaluation for large commit sets

        Returns:
            Dictionary containing scores for each dimension and analysis
        """
        if not commits:
            return self._get_empty_evaluation(username)

        # Use all commits if max_commits is None
        if max_commits is None:
            analyzed_commits = commits
        else:
            analyzed_commits = commits[:max_commits]

        # Filter commits by author
        author_commits = [c for c in analyzed_commits if self._is_commit_by_author(c, username)]

        if not author_commits:
            return self._get_empty_evaluation(username)

        # Decide whether to use chunked evaluation
        if use_chunking and len(author_commits) > 20:
            return self._evaluate_engineer_chunked(
                author_commits,
                username,
                load_files
            )

        # Standard evaluation for smaller commit sets
        return self._evaluate_engineer_standard(
            author_commits,
            username,
            load_files
        )

    def _is_commit_by_author(self, commit: Dict[str, Any], username: str) -> bool:
        """Check if commit is by the specified author"""
        # Try custom extraction format first
        if "author" in commit and isinstance(commit["author"], str):
            return commit["author"].lower() == username.lower()

        # Try GitHub API format
        if "commit" in commit:
            author = commit.get("commit", {}).get("author", {}).get("name", "")
            if author:
                return author.lower() == username.lower()

        return False

    def _evaluate_engineer_standard(
        self,
        commits: List[Dict[str, Any]],
        username: str,
        load_files: bool
    ) -> Dict[str, Any]:
        """Standard evaluation for smaller commit sets"""
        # Load additional context if in moderate mode
        file_contents = {}
        repo_structure = None

        if self.mode == "moderate" and load_files and self.data_dir:
            file_contents = self._load_relevant_files(commits)
            repo_structure = self._load_repo_structure()

        # Build analysis context from commits + files
        context = self._build_commit_context(
            commits,
            username,
            file_contents=file_contents,
            repo_structure=repo_structure
        )

        # Call LLM for evaluation
        scores = self._evaluate_with_llm(context, username)

        return {
            "username": username,
            "total_commits_analyzed": len(commits),
            "files_loaded": len(file_contents),
            "mode": self.mode,
            "scores": scores,
            "commits_summary": self._summarize_commits(commits)
        }

    def _evaluate_engineer_chunked(
        self,
        commits: List[Dict[str, Any]],
        username: str,
        load_files: bool
    ) -> Dict[str, Any]:
        """
        Evaluate engineer using chunked approach with accumulative context

        This method:
        1. Divides commits into chunks based on token limits
        2. Evaluates each chunk with context from previous chunks
        3. Returns final accumulated evaluation
        """
        print(f"\n[Chunked Evaluation] Processing {len(commits)} commits in chunks...")

        # Determine chunk size based on token limits
        # Reserve space for file contents and previous evaluations
        commits_per_chunk = 15 if self.mode == "moderate" else 20

        # Split commits into chunks
        chunks = [
            commits[i:i + commits_per_chunk]
            for i in range(0, len(commits), commits_per_chunk)
        ]

        print(f"[Chunked Evaluation] Split into {len(chunks)} chunks")

        # Load repository structure once
        repo_structure = None
        if self.mode == "moderate" and load_files and self.data_dir:
            repo_structure = self._load_repo_structure()

        # Process chunks with accumulative context
        accumulated_evaluation = None
        all_file_contents = {}

        for chunk_idx, chunk in enumerate(chunks, 1):
            print(f"\n[Chunk {chunk_idx}/{len(chunks)}] Evaluating {len(chunk)} commits...")

            # Load file contents for this chunk
            file_contents = {}
            if self.mode == "moderate" and load_files and self.data_dir:
                file_contents = self._load_relevant_files(chunk)
                all_file_contents.update(file_contents)

            # Build context with previous evaluation
            context = self._build_chunked_context(
                chunk,
                username,
                chunk_idx,
                len(chunks),
                file_contents=file_contents,
                repo_structure=repo_structure if chunk_idx == 1 else None,
                previous_evaluation=accumulated_evaluation
            )

            # Evaluate this chunk
            chunk_scores = self._evaluate_with_llm(context, username, chunk_idx)

            # Update accumulated evaluation
            if accumulated_evaluation is None:
                accumulated_evaluation = chunk_scores
            else:
                # Merge scores (weighted average based on commits processed)
                accumulated_evaluation = self._merge_evaluations(
                    accumulated_evaluation,
                    chunk_scores,
                    chunk_idx
                )

            print(f"[Chunk {chunk_idx}/{len(chunks)}] Completed")

        # Return final evaluation
        return {
            "username": username,
            "total_commits_analyzed": len(commits),
            "files_loaded": len(all_file_contents),
            "mode": self.mode,
            "chunked": True,
            "chunks_processed": len(chunks),
            "scores": accumulated_evaluation,
            "commits_summary": self._summarize_commits(commits)
        }

    def _build_chunked_context(
        self,
        commits: List[Dict[str, Any]],
        username: str,
        chunk_idx: int,
        total_chunks: int,
        file_contents: Optional[Dict[str, str]] = None,
        repo_structure: Optional[Dict[str, Any]] = None,
        previous_evaluation: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build context for chunked evaluation"""
        context_parts = []

        # Add chunk information
        context_parts.append(f"## Evaluation Progress: Chunk {chunk_idx}/{total_chunks}\n")

        # Add previous evaluation context if available
        if previous_evaluation:
            context_parts.append("## Previous Evaluation Summary\n")
            context_parts.append("Based on previous commits, here are the current scores:\n")
            for dim, score in previous_evaluation.items():
                if dim != "reasoning" and isinstance(score, (int, float)):
                    context_parts.append(f"- {dim}: {score}/100\n")
            if "reasoning" in previous_evaluation:
                context_parts.append(f"\nPrevious reasoning: {previous_evaluation['reasoning']}\n")
            context_parts.append("\nNow analyze the following additional commits and UPDATE the scores accordingly.\n\n")

        # Add repository structure only in first chunk
        if repo_structure:
            context_parts.append("## Repository Structure\n")
            structure_summary = self._summarize_repo_structure(repo_structure)
            context_parts.append(structure_summary)
            context_parts.append("\n")

        # Add current chunk commits
        context_parts.append(f"## Commits in Current Chunk ({len(commits)} commits)\n")

        for i, commit in enumerate(commits[:15], 1):
            commit_info = commit.get("commit", {})
            message = commit_info.get("message", "")
            author = commit_info.get("author", {})
            stats = commit.get("stats", {})
            files = commit.get("files", [])

            commit_summary = f"""
### Commit #{i}
**Message**: {message[:300]}
**Author**: {author.get('name', 'Unknown')}
**Date**: {author.get('date', 'Unknown')}
**Changes**: +{stats.get('additions', 0)} -{stats.get('deletions', 0)} lines
**Files**: {len(files)} files changed
"""

            if files:
                commit_summary += "\n**Modified files**:\n"
                for file_info in files[:8]:
                    filename = file_info.get("filename", "")
                    status = file_info.get("status", "")
                    additions = file_info.get("additions", 0)
                    deletions = file_info.get("deletions", 0)
                    commit_summary += f"  - `{filename}` ({status}) +{additions} -{deletions}\n"

                    patch = file_info.get("patch", "")
                    if patch:
                        max_patch_len = 2000 if self.mode == "moderate" else 800
                        if len(patch) < max_patch_len:
                            commit_summary += f"\n```diff\n{patch[:max_patch_len]}\n```\n"

            context_parts.append(commit_summary)

        # Add file contents if available
        if file_contents:
            context_parts.append("\n## Relevant File Contents\n")
            for filepath, content in list(file_contents.items())[:8]:
                context_parts.append(f"\n### File: `{filepath}`\n")
                ext = filepath.split('.')[-1] if '.' in filepath else ''
                context_parts.append(f"```{ext}\n{content[:10000]}\n```\n")

        return "\n".join(context_parts)

    def _merge_evaluations(
        self,
        eval1: Dict[str, Any],
        eval2: Dict[str, Any],
        chunk_idx: int
    ) -> Dict[str, Any]:
        """Merge two evaluations with weighted average"""
        merged = {}

        # Weight: previous chunks have accumulated weight, new chunk gets weight 1
        weight1 = chunk_idx - 1
        weight2 = 1
        total_weight = weight1 + weight2

        for key in self.dimensions.keys():
            if key in eval1 and key in eval2:
                score1 = eval1.get(key, 0)
                score2 = eval2.get(key, 0)

                if isinstance(score1, (int, float)) and isinstance(score2, (int, float)):
                    # Weighted average
                    merged[key] = int((score1 * weight1 + score2 * weight2) / total_weight)
                else:
                    merged[key] = eval2.get(key, eval1.get(key, 0))
            else:
                merged[key] = eval2.get(key, eval1.get(key, 0))

        # Merge reasoning
        reasoning_parts = []
        if "reasoning" in eval1 and eval1["reasoning"]:
            reasoning_parts.append(f"Previous: {eval1['reasoning']}")
        if "reasoning" in eval2 and eval2["reasoning"]:
            reasoning_parts.append(f"Update: {eval2['reasoning']}")

        merged["reasoning"] = " | ".join(reasoning_parts) if reasoning_parts else ""

        return merged

    def _load_relevant_files(
        self,
        commits: List[Dict[str, Any]],
        max_files: int = 10
    ) -> Dict[str, str]:
        """
        Load file contents for files most frequently modified in commits

        Args:
            commits: List of commit data
            max_files: Maximum number of files to load

        Returns:
            Dictionary mapping file paths to their contents
        """
        if not self.data_dir:
            return {}

        files_dir = self.data_dir / "files"
        if not files_dir.exists():
            return {}

        # Count file modifications
        file_frequency = {}
        for commit in commits:
            for file_info in commit.get("files", []):
                filename = file_info.get("filename", "")
                if filename:
                    file_frequency[filename] = file_frequency.get(filename, 0) + 1

        # Sort by frequency and get top files
        top_files = sorted(
            file_frequency.items(),
            key=lambda x: x[1],
            reverse=True
        )[:max_files]

        # Load file contents
        file_contents = {}
        for filepath, _ in top_files:
            # Try to load from files/ directory
            file_path = files_dir / filepath

            # Also try with .json extension (metadata file)
            json_path = files_dir / f"{filepath}.json"

            content = None

            # Try direct file first
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except Exception as e:
                    print(f"[Warning] Failed to load {filepath}: {e}")

            # Try JSON metadata file
            elif json_path.exists():
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                        content = metadata.get("content", "")
                except Exception as e:
                    print(f"[Warning] Failed to load {filepath} metadata: {e}")

            if content:
                # Truncate very large files
                if len(content) > 20000:
                    content = content[:20000] + "\n\n[... file truncated ...]"
                file_contents[filepath] = content

        return file_contents

    def _load_repo_structure(self) -> Optional[Dict[str, Any]]:
        """Load repository structure if available"""
        if not self.data_dir:
            return None

        if self._repo_structure:
            return self._repo_structure

        # Try multiple possible structure file names
        structure_files = [
            "repo_structure.json",
            "repo_tree.json",
            "structure.json"
        ]

        for filename in structure_files:
            structure_path = self.data_dir / filename
            if structure_path.exists():
                try:
                    with open(structure_path, 'r', encoding='utf-8') as f:
                        self._repo_structure = json.load(f)
                        return self._repo_structure
                except Exception as e:
                    print(f"[Warning] Failed to load {filename}: {e}")

        return None

    def _build_commit_context(
        self,
        commits: List[Dict[str, Any]],
        username: str,
        file_contents: Optional[Dict[str, str]] = None,
        repo_structure: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build context from commits for LLM analysis

        Args:
            commits: List of commit data
            username: GitHub username
            file_contents: Optional file contents to include
            repo_structure: Optional repository structure

        Returns:
            Formatted context string
        """
        context_parts = []

        # Add repository structure overview if available
        if repo_structure:
            context_parts.append("## Repository Structure\n")
            structure_summary = self._summarize_repo_structure(repo_structure)
            context_parts.append(structure_summary)
            context_parts.append("\n")

        # Add commit analysis
        context_parts.append("## Commit Analysis\n")

        for i, commit in enumerate(commits[:15], 1):  # Analyze top 15 commits
            commit_info = commit.get("commit", {})
            message = commit_info.get("message", "")
            author = commit_info.get("author", {})
            stats = commit.get("stats", {})
            files = commit.get("files", [])

            # Build commit summary
            commit_summary = f"""
### Commit #{i}
**Message**: {message[:300]}
**Author**: {author.get('name', 'Unknown')}
**Date**: {author.get('date', 'Unknown')}
**Changes**: +{stats.get('additions', 0)} -{stats.get('deletions', 0)} lines
**Files**: {len(files)} files changed
"""

            # Add file changes
            if files:
                commit_summary += "\n**Modified files**:\n"
                for file_info in files[:8]:  # Top 8 files per commit
                    filename = file_info.get("filename", "")
                    status = file_info.get("status", "")
                    additions = file_info.get("additions", 0)
                    deletions = file_info.get("deletions", 0)
                    commit_summary += f"  - `{filename}` ({status}) +{additions} -{deletions}\n"

                    # Include patch/diff
                    patch = file_info.get("patch", "")
                    if patch:
                        # Increase diff context for moderate mode
                        max_patch_len = 3000 if self.mode == "moderate" else 1000
                        if len(patch) < max_patch_len:
                            commit_summary += f"\n```diff\n{patch[:max_patch_len]}\n```\n"

            context_parts.append(commit_summary)

        # Add file contents if available (moderate mode)
        if file_contents:
            context_parts.append("\n## Relevant File Contents\n")
            for filepath, content in list(file_contents.items())[:10]:
                context_parts.append(f"\n### File: `{filepath}`\n")
                # Determine language from extension
                ext = filepath.split('.')[-1] if '.' in filepath else ''
                context_parts.append(f"```{ext}\n{content[:15000]}\n```\n")

        return "\n".join(context_parts)

    def _summarize_repo_structure(self, structure: Dict[str, Any]) -> str:
        """Create a brief summary of repository structure"""
        summary_parts = []

        # Count files by type
        if "tree" in structure or isinstance(structure, list):
            tree = structure.get("tree", structure) if isinstance(structure, dict) else structure

            file_types = {}
            directories = set()

            for item in tree[:100]:  # Limit to avoid huge structures
                path = item.get("path", "")
                item_type = item.get("type", "")

                if item_type == "tree":
                    # Extract directory
                    dir_path = path.split('/')[0] if '/' in path else path
                    directories.add(dir_path)
                elif item_type == "blob":
                    # Extract file extension
                    ext = path.split('.')[-1] if '.' in path else 'no_ext'
                    file_types[ext] = file_types.get(ext, 0) + 1

            summary_parts.append(f"**Directories**: {', '.join(sorted(directories)[:10])}")
            summary_parts.append(f"**File types**: {dict(sorted(file_types.items(), key=lambda x: x[1], reverse=True)[:10])}")

        return '\n'.join(summary_parts)

    def _evaluate_with_llm(
        self,
        context: str,
        username: str,
        chunk_idx: int = None
    ) -> Dict[str, int]:
        """
        Use LLM to evaluate commits and return scores

        Args:
            context: Commit context for analysis
            username: GitHub username
            chunk_idx: Optional chunk index for chunked evaluation

        Returns:
            Dictionary of scores (0-100) for each dimension
        """
        if not self.api_key:
            print("[Warning] No API key configured, using fallback evaluation")
            return self._fallback_evaluation(context)

        # Build evaluation prompt
        prompt = self._build_evaluation_prompt(context, username, chunk_idx)

        try:
            # Call OpenRouter API
            response = requests.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "anthropic/claude-sonnet-4.5",  # Using better model for moderate mode
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.3,
                    "max_tokens": 4000
                },
                timeout=120
            )

            response.raise_for_status()
            result = response.json()

            # Parse LLM response
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            scores = self._parse_llm_response(content)

            # Log token usage
            usage = result.get("usage", {})
            chunk_info = f" [Chunk {chunk_idx}]" if chunk_idx else ""
            print(f"[Token Usage{chunk_info}] Input: {usage.get('prompt_tokens', 0)}, "
                  f"Output: {usage.get('completion_tokens', 0)}, "
                  f"Total: {usage.get('total_tokens', 0)}")

            return scores

        except Exception as e:
            print(f"[Error] LLM evaluation failed: {e}")
            return self._fallback_evaluation(context)

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text (rough approximation)"""
        return len(text) // 4

    def _truncate_context(self, context: str, max_tokens: int) -> str:
        """Truncate context to fit within token limit"""
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

    def _build_evaluation_prompt(self, context: str, username: str, chunk_idx: int = None) -> str:
        """Build the evaluation prompt for the LLM"""
        # Reserve tokens for the prompt template
        prompt_template_tokens = 800
        max_context_tokens = self.max_input_tokens - prompt_template_tokens

        # Truncate context if needed
        context = self._truncate_context(context, max_context_tokens)

        mode_note = ""
        if self.mode == "moderate":
            mode_note = "\nNOTE: You have access to both commit diffs AND relevant file contents. Use the file contents to better understand the code quality, architecture, and engineering practices."

        chunked_instruction = ""
        if chunk_idx:
            chunked_instruction = """

CHUNKED EVALUATION INSTRUCTIONS:
This is a chunked evaluation. You will see:
1. Previous evaluation scores (if this is not the first chunk)
2. New commits to analyze in the current chunk

Your task is to:
- Analyze the new commits carefully
- UPDATE the scores based on the new evidence
- If you see improvement or new capabilities, INCREASE the relevant scores
- If you see issues or concerns, DECREASE the relevant scores
- Provide reasoning that explains how the new commits affected your evaluation"""

        return f"""You are an expert engineering evaluator. Analyze the following data from user "{username}" and evaluate their engineering capabilities across six dimensions. Each score should be 0-100.
{mode_note}{chunked_instruction}

DATA TO ANALYZE:
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
  "reasoning": "Brief explanation focusing on key strengths and areas for improvement (2-4 sentences)"
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
        """Fallback evaluation using keyword analysis when LLM is unavailable"""
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
            "languages": list(languages)[:10]
        }

    def _get_empty_evaluation(self, username: str) -> Dict[str, Any]:
        """Return empty evaluation when no commits available"""
        return {
            "username": username,
            "total_commits_analyzed": 0,
            "total_commits": 0,
            "files_loaded": 0,
            "mode": self.mode,
            "scores": {key: 0 for key in self.dimensions.keys()},
            "commits_summary": {
                "total_additions": 0,
                "total_deletions": 0,
                "files_changed": 0,
                "languages": []
            }
        }
