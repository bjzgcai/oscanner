"""Multi-evaluation merging service."""

import os
import requests
from typing import Dict, Any, List, Optional
from fastapi import HTTPException

from evaluator.config import get_llm_api_key, DEFAULT_LLM_MODEL


NON_NUMERIC_SCORE_KEYS = {"reasoning", "summary", "analysis", "evidence", "recommendations"}


def _numeric_score(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _score_keys_for_evaluations(evaluations: List[Dict[str, Any]]) -> List[str]:
    keys: List[str] = []
    seen = set()
    for eval_data in evaluations:
        scores = eval_data.get("scores", {})
        if not isinstance(scores, dict):
            continue
        for key, value in scores.items():
            if key in NON_NUMERIC_SCORE_KEYS or _numeric_score(value) is None:
                continue
            if key not in seen:
                seen.add(key)
                keys.append(key)
    return keys


def _chat_completions_url() -> str:
    configured_url = (os.getenv("OSCANNER_LLM_CHAT_COMPLETIONS_URL") or "").strip()
    if configured_url:
        return configured_url
    base_url = (
        os.getenv("OSCANNER_LLM_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or "https://openrouter.ai/api/v1"
    ).strip()
    return f"{base_url.rstrip('/')}/chat/completions"


def merge_evaluations_logic(evaluations_data: List[Dict[str, Any]], model: str = DEFAULT_LLM_MODEL) -> Dict[str, Any]:
    """
    Merge multiple evaluations into one using LLM-based weighted combination.

    Args:
        evaluations_data: List of evaluation items with author, weight, and evaluation
        model: LLM model to use for merging summaries

    Returns:
        Merged evaluation dictionary

    Raises:
        HTTPException: If validation fails or merging errors occur
    """
    if not evaluations_data or len(evaluations_data) < 2:
        raise HTTPException(status_code=400, detail="At least 2 evaluations required for merging")

    try:
        # Extract evaluations and weights
        evaluations = []
        weights = []
        authors = []

        for item in evaluations_data:
            author = item.get("author", "Unknown")
            weight = item.get("weight", 0)
            evaluation = item.get("evaluation", {})

            authors.append(author)
            weights.append(weight)
            evaluations.append(evaluation)

        total_weight = sum(weights)
        if total_weight == 0:
            raise HTTPException(status_code=400, detail="Total weight cannot be zero")

        print(f"[Merge] Merging {len(evaluations)} evaluations with weights: {weights}")

        # Step 1: Calculate weighted average scores from the plugin's numeric score keys.
        merged_scores = {}
        dimension_keys = _score_keys_for_evaluations(evaluations)

        for key in dimension_keys:
            weighted_sum = 0
            for eval_data, weight in zip(evaluations, weights):
                scores = eval_data.get("scores", {})
                score_value = _numeric_score(scores.get(key, 0)) or 0.0
                weighted_sum += score_value * weight

            merged_scores[key] = round(weighted_sum / total_weight, 1)

        # Step 2: Merge commit summaries
        total_commits = sum(
            eval_data.get("total_commits_analyzed", eval_data.get("total_commits_evaluated", 0))
            for eval_data in evaluations
        )

        merged_commits_summary = {
            "total_additions": sum(eval_data.get("commits_summary", {}).get("total_additions", 0) for eval_data in evaluations),
            "total_deletions": sum(eval_data.get("commits_summary", {}).get("total_deletions", 0) for eval_data in evaluations),
            "files_changed": sum(eval_data.get("commits_summary", {}).get("files_changed", 0) for eval_data in evaluations),
            "languages": list(set(
                lang
                for eval_data in evaluations
                for lang in eval_data.get("commits_summary", {}).get("languages", [])
            ))
        }

        # Step 3: Use LLM to merge reasoning/analysis summaries
        print(f"[Merge] Using LLM to merge analysis summaries...")

        # Build prompt for LLM
        summaries_text = ""
        for author, weight, eval_data in zip(authors, weights, evaluations):
            reasoning = eval_data.get("scores", {}).get("reasoning", "")
            percentage = round((weight / total_weight) * 100, 1)
            summaries_text += f"\n### {author} ({weight} commits, {percentage}% weight):\n{reasoning}\n"

        score_lines = "\n".join(
            f"- {key.replace('_', ' ').title()}: {merged_scores[key]}/100"
            for key in dimension_keys
        ) or "- No numeric plugin scores were available."

        merge_prompt = f"""You are analyzing a software engineer who uses multiple email identities in their commits. You have separate evaluations for each identity, and you need to create a unified, comprehensive analysis.

Below are the individual analyses with their weights (based on commit count):

{summaries_text}

Total commits: {total_commits}
Weighted average scores:
{score_lines}

Create a unified analysis that:
1. Synthesizes insights from all identities
2. Gives more weight to analyses with higher commit counts
3. Identifies common patterns and themes across all identities
4. Presents a coherent narrative about this engineer's capabilities
5. Maintains a professional, objective tone

Write the unified analysis (3-5 paragraphs):"""

        # Call LLM to merge summaries
        api_key = get_llm_api_key()
        if not api_key:
            # Fallback: simple concatenation
            merged_reasoning = f"Combined analysis from {len(authors)} identities ({', '.join(authors)}):\n\n"
            merged_reasoning += summaries_text
        else:
            try:
                llm_response = requests.post(
                    _chat_completions_url(),
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "user", "content": merge_prompt}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 1500
                    },
                    timeout=60
                )

                if llm_response.ok:
                    response_data = llm_response.json()
                    merged_reasoning = response_data["choices"][0]["message"]["content"]
                    print(f"[Merge] ✓ LLM successfully merged summaries ({len(merged_reasoning)} chars)")
                else:
                    print(f"[Merge] ⚠ LLM request failed, using concatenation fallback")
                    merged_reasoning = f"Combined analysis from {len(authors)} identities:\n\n" + summaries_text

            except Exception as e:
                print(f"[Merge] ⚠ LLM merge failed: {e}, using concatenation fallback")
                merged_reasoning = f"Combined analysis from {len(authors)} identities:\n\n" + summaries_text

        # Add merged reasoning to scores
        merged_scores["reasoning"] = merged_reasoning

        # Build final merged evaluation
        merged_evaluation = {
            "username": " + ".join(authors),
            "mode": "merged",
            "total_commits_analyzed": total_commits,
            "merged_from": len(evaluations),
            "authors": authors,
            "weights": weights,
            "scores": merged_scores,
            "commits_summary": merged_commits_summary,
            "files_loaded": sum(eval_data.get("files_loaded", 0) for eval_data in evaluations)
        }

        return merged_evaluation

    except HTTPException:
        raise
    except Exception as e:
        print(f"✗ Merge failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Merge failed: {str(e)}")
