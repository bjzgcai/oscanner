
Constraint	                Limit
Rate limit (authenticated)	5,000 requests/hour
## todo Contents API file size	    < 1MB (base64 encoded)

## todo Tree recursion	100,000 entries



## Repo Size Constraints
the 10M-token evaluator guardrail.
The check lives in evaluation_service.py and stops evaluation with HTTP 413 and exact detail:
the repo is too big exceeding 10M tokens!
It now runs before evaluator/LLM work in the main incremental evaluator path, Gitee contributor route, and trajectory/group evaluation paths.
