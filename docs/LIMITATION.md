
Constraint	                Limit
Rate limit (authenticated)	5,000 requests/hour
## todo Contents API file size	    < 1MB (base64 encoded)

## todo Tree recursion	100,000 entries



## Repo Size Constraints
the 10M-token evaluator guardrail.
The check lives in evaluation_service.py and stops evaluation with HTTP 413 and exact detail:
the repo is too big exceeding 10M tokens!
It now runs before evaluator/LLM work in the main incremental evaluator path, Gitee contributor route, and trajectory/group evaluation paths.

## PR and Cooperation with others

## forks and stars are not considered in the evaluation, as they can be easily manipulated and do not necessarily reflect the quality of the code or the contribution.

## vercel how to set up and deploy

## use the user's email to get all the footprints of the user, including the repos they have contributed to, the PRs they have made, and the issues they have opened. This can be done by using the GitHub API to fetch the user's activity data based on their email address. However, this approach may raise privacy concerns and may not be allowed by GitHub's terms of service. It is important to ensure that any data collection and usage complies with relevant privacy laws and regulations.