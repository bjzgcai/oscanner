"""Multi-evaluation merging service."""

import requests
from typing import Dict, Any, List
from fastapi import HTTPException

from evaluator.config import get_llm_api_key, DEFAULT_LLM_MODEL


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

        # Step 1: Calculate weighted average scores
        merged_scores = {}
        dimension_keys = ['ai_fullstack', 'ai_architecture', 'cloud_native', 'open_source', 'intelligent_dev', 'leadership']

        for key in dimension_keys:
            weighted_sum = 0
            for eval_data, weight in zip(evaluations, weights):
                scores = eval_data.get("scores", {})
                score_value = scores.get(key, 0)
                # Handle both numeric and string scores
                if isinstance(score_value, str):
                    try:
                        score_value = float(score_value)
                    except:
                        score_value = 0
                weighted_sum += score_value * weight

            merged_scores[key] = round(weighted_sum / total_weight, 1)

        # Step 2: Merge commit summaries
        total_commits = sum(eval_data.get("total_commits_analyzed", 0) for eval_data in evaluations)

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

        merge_prompt = f"""You are analyzing a software engineer who uses multiple names/identities in their commits. You have separate evaluations for each identity, and you need to create a unified, comprehensive analysis.

Below are the individual analyses with their weights (based on commit count):

{summaries_text}

Total commits: {total_commits}
Weighted average scores:
- AI Model Full-Stack: {merged_scores['ai_fullstack']}/100
- AI Native Architecture: {merged_scores['ai_architecture']}/100
- Cloud Native Engineering: {merged_scores['cloud_native']}/100
- Open Source Collaboration: {merged_scores['open_source']}/100
- Intelligent Development: {merged_scores['intelligent_dev']}/100
- Engineering Leadership: {merged_scores['leadership']}/100

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
                    "https://openrouter.ai/api/v1/chat/completions",
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
