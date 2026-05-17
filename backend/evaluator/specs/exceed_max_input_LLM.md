How the 1M guard works now:

The evaluator builds the final LLM prompt including instructions plus repo commit messages, diffs, and file contents.

It uses a conservative token estimate: 1 char = 1 estimated token.

If estimated input exceeds max_input_tokens, DeepSeek defaults to 900_000, commits are split into sequential chunks.
Each LLM call re-checks the final prompt before sending.
If a single commit is too large to fit as its own chunk, the evaluator records the input-budget error, truncates that commit/repo input enough to stay within the LLM budget, continues evaluation, and returns the evaluation together with `input_truncated`, `warnings`, and `input_budget_errors` metadata.
