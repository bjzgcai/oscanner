# Trajectory Evaluation Enhancements

## Overview
Enhanced the plugin evaluator to support period-based trajectory tracking with context-aware scoring. This ensures that evaluation scores maintain continuity and reflect genuine growth patterns over time.

## Key Enhancements

### 1. Enhanced Rubric Summary (zgc_ai_native_2026)
**File**: `plugins/zgc_ai_native_2026/scan/__init__.py`

Added trajectory evaluation context to the rubric summary:
```
TRAJECTORY EVALUATION CONTEXT:
- This evaluation is part of a growth trajectory tracking system
- Commits are grouped into evaluation nodes (minimum 10 commits per node from 2-week periods)
- Scores should generally show INCREASING trend over time as engineers learn and improve
- ONLY decrease scores if there is CLEAR NEGATIVE EVIDENCE (regression in quality, bugs introduced, anti-patterns)
- When previous checkpoint scores are provided, use them as baseline for comparison
- If current work maintains similar quality to previous, scores should be equal or slightly higher
- Significant score increases require clear evidence of new capabilities or improved practices
```

### 2. Previous Checkpoint Score Context
**Files**: Both plugin scan modules

Added support for passing previous checkpoint scores to the evaluator:
- New parameter: `previous_checkpoint_scores: Optional[Dict[str, Any]]`
- Scores are extracted (excluding reasoning) and included in the evaluation prompt
- LLM receives baseline scores to maintain continuity

**Prompt enhancement example (English)**:
```
PREVIOUS CHECKPOINT SCORES (baseline reference):
{
  "spec_quality": 65,
  "cloud_architecture": 50,
  ...
}
NOTE: Current evaluation should build on previous scores. Maintain or gradually
increase scores unless clear negative evidence exists.
```

**Prompt enhancement example (Chinese)**:
```
上一个评估节点的分数（基线参考）:
{
  "spec_quality": 65,
  "cloud_architecture": 50,
  ...
}
注意：当前评估应该基于上一个节点的分数，除非有明确的负面证据，否则分数应该保持稳定或略有增长。
```

### 3. Trajectory Service Integration
**File**: `evaluator/services/trajectory_service.py`

Updated `create_checkpoint_evaluation()` to:
1. Extract previous checkpoint scores when available
2. Pass them to the plugin evaluator via `create_commit_evaluator()`
3. Log the score keys being passed for debugging

```python
# Extract previous scores if available
previous_scores = None
if previous_checkpoint:
    previous_scores = previous_checkpoint.evaluation.scores.model_dump()
    print(f"[Trajectory] Passing previous checkpoint scores to evaluator: {list(previous_scores.keys())}")

# Create evaluator with previous checkpoint scores support
evaluator = scan_mod.create_commit_evaluator(
    data_dir=str(get_platform_data_dir(platform, owner, repo)),
    api_key=get_llm_api_key(),
    model=model,
    mode="moderate",
    parallel_chunking=parallel_chunking,
    max_parallel_workers=max_parallel_workers,
    previous_checkpoint_scores=previous_scores,
)
```

### 4. Updated Documentation
**Files**: Both plugin scan modules

Added trajectory evaluation notes to plugin docstrings:
- zgc_simple: Traditional six-dimensional with trajectory support
- zgc_ai_native_2026: AI-Native 2026 rubric with trajectory support

## Implementation Details

### Score Continuity Logic
The LLM is guided to:
1. **First checkpoint**: Evaluate based on evidence alone (no baseline)
2. **Subsequent checkpoints**:
   - Use previous scores as baseline reference
   - Maintain or gradually increase scores by default
   - Only decrease if clear negative evidence exists (bugs, regressions, anti-patterns)
   - Significant increases require clear evidence of new capabilities

### Evaluation Node Requirements
According to `docs/refactor_eval.md`:
- **Period**: 2-week cycles starting from repository start date
- **Minimum commits**: 10 commits per evaluation node
- **Accumulation**: If a period has < 10 commits, accumulate to next period
- **Example**:
  - Jan 1-14: 8 commits → skip, accumulate
  - Jan 15-28: 1 commit → 9 total, skip, accumulate
  - Jan 29-Feb 11: 5 commits → 14 total → **evaluate**

### Language Support
Both English and Chinese prompts are enhanced with trajectory context:
- **English**: "PREVIOUS CHECKPOINT SCORES (baseline reference)"
- **Chinese**: "上一个评估节点的分数（基线参考）"

## Benefits

1. **Score Continuity**: Prevents erratic score fluctuations between checkpoints
2. **Growth Tracking**: Scores naturally increase as engineers improve
3. **Evidence-Based**: Decreases require clear negative evidence
4. **Context-Aware**: LLM understands it's evaluating trajectory, not isolated commits
5. **Fairness**: Similar work quality produces similar scores across checkpoints

## Testing Recommendations

1. **First checkpoint**: Verify evaluation works without previous scores
2. **Second checkpoint**: Verify previous scores are passed and influence evaluation
3. **Score trends**: Check that similar quality work maintains scores
4. **Score decreases**: Verify decreases only occur with negative evidence
5. **Multi-repo**: Test with multiple repositories and author aliases

## Plugin Compatibility

Both plugins now support trajectory evaluation:
- **zgc_simple**: Traditional six-dimensional framework
- **zgc_ai_native_2026**: AI-Native 2026 rubric (L1-L5 behavioral profiles)

Both accept `previous_checkpoint_scores` parameter and include trajectory context in prompts.
