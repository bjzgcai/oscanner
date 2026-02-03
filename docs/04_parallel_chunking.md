# Parallel Chunking Strategy

## Overview

When analyzing repositories with many commits, the system uses a **chunking strategy** to split commits into smaller batches for LLM evaluation. Previously, only **sequential chunking** was available. Now you can choose between **sequential** and **parallel** modes.

## Chunking Modes

### Sequential Mode (Default)
- Chunks are evaluated one after another
- Each chunk sees the previous chunk's evaluation results
- LLM progressively refines scores based on accumulated context
- **When to use**: When you want contextual continuity across chunks

### Parallel Mode (New)
- All chunks are evaluated independently and simultaneously
- After all chunks complete, an LLM intelligently merges all results
- Faster for large repositories (3-5x speedup with 3 workers)
- **When to use**: When speed is important and chunks can be analyzed independently

## How to Enable

### API Query Parameters

Add these query parameters to your evaluation API call:

```bash
# Enable parallel chunking with default workers (3)
POST /api/evaluate/{owner}/{repo}/{author}?parallel_chunking=true

# Customize the number of parallel workers
POST /api/evaluate/{owner}/{repo}/{author}?parallel_chunking=true&max_parallel_workers=5
```

### Configuration Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `parallel_chunking` | boolean | `false` | Enable/disable parallel mode |
| `max_parallel_workers` | integer | `3` | Number of concurrent LLM calls |

### Example Usage

```bash
# Sequential mode (default)
curl -X POST "http://localhost:8000/api/evaluate/owner/repo/author"

# Parallel mode with 3 workers
curl -X POST "http://localhost:8000/api/evaluate/owner/repo/author?parallel_chunking=true"

# Parallel mode with 5 workers (faster but more API cost)
curl -X POST "http://localhost:8000/api/evaluate/owner/repo/author?parallel_chunking=true&max_parallel_workers=5"
```

## Performance Comparison

For a repository with 100 commits (split into ~7 chunks):

| Mode | Execution Time | API Calls | Cost |
|------|---------------|-----------|------|
| Sequential | ~210 seconds | 7 serial | 7x (serial) |
| Parallel (3 workers) | ~70 seconds | 7 parallel + 1 merge | 8x (parallel) |
| Parallel (5 workers) | ~45 seconds | 7 parallel + 1 merge | 8x (parallel) |

**Note**: Parallel mode makes one additional LLM call for intelligent merging, but saves significant time.

## How It Works

### Sequential Flow
```
Chunk 1 → Chunk 2 → Chunk 3 → ... → Final Result
          ↑        ↑
          Previous  Previous
```

### Parallel Flow
```
Chunk 1 ─┐
Chunk 2 ─┤
Chunk 3 ─┼→ LLM Merge → Final Result
Chunk 4 ─┤
Chunk 5 ─┘
```

## Advanced: Programmatic Usage

```python
from evaluator.services import evaluate_author_incremental

evaluation = evaluate_author_incremental(
    commits=commits,
    author="username",
    previous_evaluation=None,
    data_dir=data_dir,
    model="anthropic/claude-sonnet-4.5",
    use_chunking=True,
    api_key=api_key,
    evaluator_factory=evaluator_factory,
    parallel_chunking=True,      # Enable parallel mode
    max_parallel_workers=3,       # Number of workers
)
```

## Monitoring

The system logs chunking activity:

```
# Sequential mode
[Chunking] Using SEQUENTIAL mode with 7 chunks
[LLM] Evaluating... chunk 1/7
[LLM] Evaluating... chunk 2/7
...

# Parallel mode
[Chunking] Using PARALLEL mode with 7 chunks (max_workers=3)
[Parallel] Chunk 3/7 completed
[Parallel] Chunk 1/7 completed
[Parallel] Chunk 2/7 completed
...
[Parallel] All 7 chunks completed, merging with LLM...
[Parallel] LLM merge completed successfully
```

## Best Practices

1. **Default to sequential** for smaller repositories (<50 commits)
2. **Use parallel mode** when:
   - Repository has >100 commits
   - Speed is critical
   - API rate limits are not a concern
3. **Adjust workers** based on:
   - API rate limits (OpenRouter, OpenAI)
   - Cost tolerance (more workers = more concurrent API calls)
   - Typical range: 2-5 workers

## Troubleshooting

### Parallel mode falls back to averaging
**Issue**: "LLM merge failed, falling back to simple averaging"

**Causes**:
- LLM API error during merge step
- Token limit exceeded in merge prompt

**Solution**:
- Check LLM API logs
- Reduce number of chunks (adjust chunk size)
- Ensure API key is valid

### No performance improvement
**Issue**: Parallel mode not faster than sequential

**Causes**:
- Only 1-2 chunks (not enough parallelization)
- `max_parallel_workers=1` (no parallelism)

**Solution**:
- Increase `max_parallel_workers`
- Verify repository has enough commits to chunk (>20)
