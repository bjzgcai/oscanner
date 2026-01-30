# Evaluation API Schemas

This module provides Pydantic schemas for the evaluation API endpoints, enabling automatic request/response validation and OpenAPI documentation generation.

## Schema Hierarchy

```
EvaluationResponseSchema
├── success: bool
├── evaluation: EvaluationSchema
│   ├── username: str
│   ├── total_commits_analyzed: int
│   ├── files_loaded: int
│   ├── mode: str
│   ├── scores: ScoresSchema
│   │   ├── spec_quality: int (0-100)
│   │   ├── cloud_architecture: int (0-100)
│   │   ├── ai_engineering: int (0-100)
│   │   ├── mastery_professionalism: int (0-100)
│   │   ├── ai_fullstack: int (0-100)
│   │   ├── ai_architecture: int (0-100)
│   │   ├── cloud_native: int (0-100)
│   │   ├── open_source: int (0-100)
│   │   ├── intelligent_dev: int (0-100)
│   │   ├── leadership: int (0-100)
│   │   └── reasoning: str (markdown)
│   ├── commits_summary: CommitsSummarySchema
│   │   ├── total_additions: int
│   │   ├── total_deletions: int
│   │   ├── files_changed: int
│   │   └── languages: List[str]
│   ├── chunked: bool
│   ├── chunks_processed: int
│   ├── chunking_strategy: str
│   ├── last_commit_sha: str
│   ├── total_commits_evaluated: int
│   ├── new_commits_count: int
│   ├── evaluated_at: str (ISO 8601)
│   ├── incremental: bool
│   ├── plugin: str
│   ├── plugin_version: str
│   └── commit_ids: List[str] (optional)
└── metadata: EvaluationMetadata
    ├── cached: bool
    ├── timestamp: str (ISO 8601)
    └── source: str (optional)
```

## Usage

### In FastAPI Routes

```python
from evaluator.schemas import EvaluationResponseSchema

@router.post("/api/evaluate/{owner}/{repo}/{author}", response_model=EvaluationResponseSchema)
async def evaluate_author(...):
    return {
        "success": True,
        "evaluation": evaluation_data,
        "metadata": {"cached": False, "timestamp": datetime.now().isoformat()}
    }
```

### Validation Example

```python
from evaluator.schemas import EvaluationResponseSchema

# Parse and validate response
response = EvaluationResponseSchema(**response_data)

# Access validated data
print(response.evaluation.username)
print(response.evaluation.scores.reasoning)

# Serialize to JSON
json_str = response.model_dump_json(indent=2)
```

## Field Descriptions

### ScoresSchema

Supports both legacy field names (for backward compatibility) and new standardized names:

**Legacy fields:**
- `spec_quality`: AI Model Full-Stack & Trade-off
- `cloud_architecture`: AI Native Architecture & Communication
- `ai_engineering`: Cloud Native Engineering
- `mastery_professionalism`: Open Source Collaboration

**New standardized fields (2026):**
- `ai_fullstack`: AI Model Full-Stack & Trade-off
- `ai_architecture`: AI Native Architecture & Communication
- `cloud_native`: Cloud Native Engineering
- `open_source`: Open Source Collaboration
- `intelligent_dev`: Intelligent Development
- `leadership`: Engineering Leadership

All score fields are optional and range from 0-100. The `reasoning` field contains detailed analysis in markdown format.

### Incremental Evaluation

The schema tracks incremental evaluation state through:
- `last_commit_sha`: Last commit evaluated (for resumption)
- `total_commits_evaluated`: Cumulative total across all runs
- `new_commits_count`: New commits in this run
- `incremental`: Whether this was an incremental update

### Chunking Metadata

For large evaluations that use parallel processing:
- `chunked`: Whether chunking was used
- `chunks_processed`: Number of chunks processed
- `chunking_strategy`: Strategy used (e.g., "parallel", "sequential")

## Benefits

1. **Auto-validation**: FastAPI validates request/response data automatically
2. **OpenAPI docs**: Schemas generate interactive API documentation at `/docs`
3. **Type safety**: IDEs provide autocomplete and type checking
4. **Extensibility**: Uses `extra="allow"` to support plugin-specific fields
5. **Backward compatibility**: Supports both legacy and new field names

## Testing

Run the example validation script:

```bash
PYTHONPATH=/path/to/project python evaluator/example_schema_validation.py
```

## OpenAPI Documentation

Once the server is running, view auto-generated API docs at:
- Swagger UI: `http://localhost:8009/docs`
- ReDoc: `http://localhost:8009/redoc`
