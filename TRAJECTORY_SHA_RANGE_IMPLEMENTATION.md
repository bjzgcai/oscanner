# Trajectory SHA Range Implementation

## Summary

Enhanced the `/api/trajectory/analyze_one-off` endpoint to support filtering commits by SHA range with two new parameters:

- **`start_sha`** (optional): First commit to evaluate (INCLUDED)
- **`end_sha`** (optional): Last commit to evaluate (INCLUDED)

Both parameters are **inclusive**, meaning the commits at both boundaries will be included in the evaluation.

## API Changes

### Endpoint: `POST /api/trajectory/analyze_one-off`

#### New Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start_sha` | string | No | Commit SHA to start from (INCLUDED). If omitted, starts from first commit. |
| `end_sha` | string | No | Commit SHA to end at (INCLUDED). If omitted, ends at latest commit. |

#### Replaced Parameters

- ❌ `last_commit` (was NOT included) → ✅ `start_sha` (IS included)
- ✅ `to_commit` (was included) → ✅ `end_sha` (IS included)

## Corner Cases Handled

### 1. Both `start_sha` and `end_sha` are `None`
**Behavior**: Evaluate ALL commits authored by the specified user(s).

```bash
curl -X POST "http://localhost:8000/api/trajectory/analyze_one-off?checkpoint_strategy=none" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "CarterWu",
    "repo_urls": ["https://gitee.com/zgcai/oscanner"],
    "aliases": ["CarterWu"]
  }'
```

### 2. Only `start_sha` provided
**Behavior**: Evaluate from `start_sha` (inclusive) to the **latest/newest** commit.

```bash
curl -X POST "http://localhost:8000/api/trajectory/analyze_one-off?checkpoint_strategy=none&start_sha=abc123" \
  -H "Content-Type: application/json" \
  -d '{"username": "CarterWu", "repo_urls": ["..."], "aliases": ["..."]}'
```

**Use case**: "Show me my recent work starting from commit abc123"

### 3. Only `end_sha` provided
**Behavior**: Evaluate from the **first/oldest** commit to `end_sha` (inclusive).

```bash
curl -X POST "http://localhost:8000/api/trajectory/analyze_one-off?checkpoint_strategy=none&end_sha=xyz789" \
  -H "Content-Type: application/json" \
  -d '{"username": "CarterWu", "repo_urls": ["..."], "aliases": ["..."]}'
```

**Use case**: "Evaluate my work up to commit xyz789"

### 4. Both provided (valid range)
**Behavior**: Evaluate commits in range `[start_sha, end_sha]` (both inclusive).

```bash
curl -X POST "http://localhost:8000/api/trajectory/analyze_one-off?checkpoint_strategy=none&start_sha=abc123&end_sha=xyz789" \
  -H "Content-Type: application/json" \
  -d '{"username": "CarterWu", "repo_urls": ["..."], "aliases": ["..."]}'
```

**Use case**: "Evaluate a specific period of work between two commits"

### 5. `start_sha` not found
**Behavior**: Return error with clear message.

**Error Response**:
```json
{
  "success": false,
  "checkpoint": null,
  "message": "start_sha 'abc123' not found in commits. Please verify the commit hash exists in the repository and is authored by the specified user.",
  "commits_analyzed": 0
}
```

**Possible causes**:
- Commit SHA doesn't exist in repository
- Commit exists but is NOT authored by the specified user/aliases
- Typo in SHA

### 6. `end_sha` not found
**Behavior**: Return error with clear message.

**Error Response**:
```json
{
  "success": false,
  "checkpoint": null,
  "message": "end_sha 'xyz789' not found in commits. Please verify the commit hash exists in the repository and is authored by the specified user.",
  "commits_analyzed": 0
}
```

### 7. `start_sha` is newer than `end_sha` (invalid range)
**Behavior**: Return error - chronologically invalid.

**Error Response**:
```json
{
  "success": false,
  "checkpoint": null,
  "message": "Invalid commit range: start_sha 'xyz789' is newer than end_sha 'abc123'. Please ensure start_sha is chronologically before or equal to end_sha.",
  "commits_analyzed": 0
}
```

**Note**: Since `start_sha` should be the **older** commit (chronologically first) and `end_sha` should be the **newer** commit (chronologically last), this validation prevents logical errors.

### 8. `start_sha` == `end_sha` (single commit)
**Behavior**: Evaluate exactly ONE commit.

```bash
curl -X POST "http://localhost:8000/api/trajectory/analyze_one-off?checkpoint_strategy=none&start_sha=abc123&end_sha=abc123" \
  -H "Content-Type: application/json" \
  -d '{"username": "CarterWu", "repo_urls": ["..."], "aliases": ["..."]}'
```

**Success Response**:
```json
{
  "success": true,
  "checkpoint": { ... },
  "message": "Created checkpoint 1 with 1 commits.",
  "commits_analyzed": 1
}
```

**Use case**: "Evaluate a single specific commit"

### 9. No commits in filtered range
**Behavior**: Return success but with 0 commits analyzed.

**Response**:
```json
{
  "success": true,
  "checkpoint": null,
  "message": "Found 0 commits. Waiting for new commits to analyze.",
  "commits_analyzed": 0
}
```

**Possible causes**:
- The range is valid but contains no commits by the specified author
- All commits in range were filtered out

### 10. Empty commit list (no commits at all)
**Behavior**: Return success with empty result.

**Response**:
```json
{
  "success": false,
  "checkpoint": null,
  "message": "No repositories to analyze",
  "commits_analyzed": 0
}
```

**Possible causes**:
- Repository hasn't been synced/extracted yet
- No commits exist for the specified author(s) across all repos

## Implementation Details

### Files Modified

1. **`backend/evaluator/routes/trajectory.py`**
   - Updated `analyze_trajectory_one_off()` endpoint signature
   - Changed parameters from `last_commit`/`to_commit` to `start_sha`/`end_sha`
   - Updated documentation and comments

2. **`backend/evaluator/services/trajectory_service.py`**
   - Updated `analyze_growth_trajectory()` function signature
   - Completely rewrote `filter_commits_by_range()` with new semantics
   - Added comprehensive error handling and validation
   - Added error response dict return option

### Key Semantic Changes

#### Old Behavior (deprecated)
- `last_commit`: NOT included in range (exclusive start)
- `to_commit`: INCLUDED in range (inclusive end)
- Range: `(last_commit, to_commit]`

#### New Behavior
- `start_sha`: INCLUDED in range (inclusive start)
- `end_sha`: INCLUDED in range (inclusive end)
- Range: `[start_sha, end_sha]`

### Commit Ordering

Commits in the database are stored **newest first** (reverse chronological order). The filtering function accounts for this:

```
Index:  0         1         2         3         4
        newest    ...       ...       ...       oldest
        ↑                               ↑
        end_sha                         start_sha
        (newer)                         (older)
```

When filtering:
- `end_sha` should have a **lower** index (newer position)
- `start_sha` should have a **higher** index (older position)

## Testing

A comprehensive test script is provided: [`test_trajectory_sha_range.py`](test_trajectory_sha_range.py)

### Setup Before Testing

1. **Start the evaluator service**:
   ```bash
   cd backend/evaluator
   uvicorn main:app --reload --port 8000
   ```

2. **Configure LLM API key**:
   ```bash
   export OPENAI_API_KEY="your_key_here"
   # or
   export OPEN_ROUTER_KEY="your_key_here"
   ```

3. **Get actual commit SHAs**:
   ```bash
   # From your repository
   git log --oneline --author="CarterWu" | head -10
   ```

4. **Update the test script constants**:
   ```python
   EXAMPLE_OLDEST_SHA = "actual_oldest_commit_sha"
   EXAMPLE_MIDDLE_SHA = "actual_middle_commit_sha"
   EXAMPLE_NEWEST_SHA = "actual_newest_commit_sha"
   ```

5. **Run tests**:
   ```bash
   python test_trajectory_sha_range.py
   ```

## Usage Examples

### Example 1: Evaluate all commits
```bash
curl -X POST "http://localhost:8000/api/trajectory/analyze_one-off" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "CarterWu",
    "repo_urls": ["https://gitee.com/zgcai/oscanner"],
    "aliases": ["CarterWu", "wu-yanbiao"]
  }'
```

### Example 2: Evaluate recent work (from specific commit to now)
```bash
curl -X POST "http://localhost:8000/api/trajectory/analyze_one-off?start_sha=de592c4" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "CarterWu",
    "repo_urls": ["https://gitee.com/zgcai/oscanner"],
    "aliases": ["CarterWu"]
  }'
```

### Example 3: Evaluate historical period
```bash
curl -X POST "http://localhost:8000/api/trajectory/analyze_one-off?start_sha=f41552e&end_sha=24e6afc" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "CarterWu",
    "repo_urls": ["https://gitee.com/zgcai/oscanner"],
    "aliases": ["CarterWu"]
  }'
```

## Migration Notes

If you have existing code using the old parameters:

**Before**:
```python
params = {
    "last_commit": "abc123",  # NOT included
    "to_commit": "xyz789"     # included
}
# Range: (abc123, xyz789]
```

**After**:
```python
# To get the same range, you need to adjust:
# Old (abc123, xyz789] means: commits AFTER abc123 up to xyz789

# Find the commit AFTER abc123 (the next older commit)
next_commit = get_commit_after("abc123")

params = {
    "start_sha": next_commit,  # included (this is the first one after abc123)
    "end_sha": "xyz789"        # included
}
# Range: [next_commit, xyz789]
```

Or simply use the new inclusive semantics:
```python
params = {
    "start_sha": "abc123",  # NOW included
    "end_sha": "xyz789"     # still included
}
# Range: [abc123, xyz789] - cleaner!
```

## Compatibility

- ✅ **Backward compatible**: Existing calls without these parameters continue to work (evaluate all commits)
- ⚠️ **Breaking change**: If you were using `last_commit` parameter, you need to update to `start_sha` with adjusted semantics
- ✅ **Forward compatible**: New parameter names are clearer and more intuitive

## Error Handling

All error cases return a consistent response structure:

```json
{
  "success": false,
  "checkpoint": null,
  "message": "Detailed error message explaining what went wrong and how to fix it",
  "commits_analyzed": 0
}
```

Error messages are designed to be:
- **Actionable**: Tell the user what to check or fix
- **Specific**: Include the problematic SHA value
- **Educational**: Explain possible causes

## Performance Considerations

- Filtering is done in-memory after commits are loaded
- Time complexity: O(n) where n is the number of commits
- No additional database queries needed
- Suitable for repositories with hundreds or thousands of commits
- For very large repositories (100k+ commits), consider pagination or incremental sync

## Future Enhancements

Potential improvements for future versions:

1. **Date-based filtering**: Add `start_date` and `end_date` parameters
2. **Relative references**: Support `HEAD~10`, `branch_name`, etc.
3. **Batch SHA range**: Accept multiple ranges in a single request
4. **SHA prefix matching**: Allow short SHAs (7-8 chars) instead of full 40-char hashes
5. **Range validation before data extraction**: Check if SHAs exist before extracting full repo data

## Support

If you encounter issues:

1. Check that the evaluator service is running
2. Verify LLM API keys are configured
3. Ensure the repository has been extracted (call `/api/extract` first)
4. Confirm the commit SHAs exist and are authored by the specified user
5. Check the service logs for detailed error messages
