# Remove Oscanner Cache Strategy

Oscanner is the basic evaluation layer. It should compute from current repository
inputs and return the result; consumer applications own any cache, reuse, or
checkpoint strategy above that layer. The only known consumer app is the sibling
`courses` repository.

## Scope

- Remove `use_cache`, `save_to_cache`, cache status, and clear-cache controls
  from Oscanner evaluator APIs.
- Stop reading or writing evaluation result JSON as cache.
- Stop reading or writing trajectory checkpoint cache in Oscanner.
- Stop validation result reuse inside Oscanner validation runs.
- Remove cache toggles and cache request parameters from the Oscanner frontend.
- Update `courses` so evaluation calls no longer pass `use_cache` to Oscanner.

HTTP streaming headers such as `Cache-Control: no-cache` are not evaluator cache
strategy and may remain. Package-manager or framework implementation caches are
also out of scope.

## Compatibility

This is a strict breaking removal. Existing callers must stop sending
`use_cache` to Oscanner evaluation and trajectory endpoints.
