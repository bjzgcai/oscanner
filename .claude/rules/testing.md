# Testing Conventions

## Current Testing Approach
- **Integration testing** through CLI and API endpoints
- **Manual verification** via dashboard UI
- **Example scripts**: `example_moderate_evaluation.py`

## Testing Strategy

### API Endpoint Testing
Test each endpoint with:
- Valid inputs (happy path)
- Missing data scenarios (auto-extraction)
- Invalid repo URLs
- Non-existent authors

### Data Extraction Testing
- Test both GitHub and Gitee collectors
- Verify incremental sync accuracy
- Check atomic write operations
- Validate cache invalidation

### Evaluation Testing
- Test single author evaluation
- Test multi-alias evaluation & merge
- Verify weighted averaging logic
- Check LLM response parsing

### Frontend Testing
- Test all three analysis modes (single, multi, comparison)
- Verify PDF export functionality
- Test LLM configuration flow
- Check localStorage persistence

## Test Data
- Use public repositories for testing
- Test with real commit data (no mocking)
- Verify cache directories created correctly

## Error Scenarios
- API rate limiting
- Network failures
- Invalid LLM responses
- Corrupted cache files
