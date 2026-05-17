backend/evaluator provides the main Oscanner evaluator API: it collects repository activity, discovers contributors, runs plugin-based LLM evaluations, and exposes those workflows through FastAPI. Oscanner does not own consumer-facing cache strategy; callers that want reuse should cache above this layer.
Main features:
FastAPI service shell: health/version/root endpoints, CORS, trailing-slash handling, optional bundled dashboard serving, and router wiring in server.py (line 81).
Plugin management: discovers local evaluator plugins, returns plugin metadata/default plugin, and loads plugin scan modules. See routes/plugins.py (line 10).
LLM/platform config: reads/writes masked LLM config, GitHub/Gitee tokens, provider mode, base URL, model, fallback models, and token readiness checks. See routes/config.py (line 24).
Repository data extraction and author discovery: extracts GitHub/Gitee commit data into local storage, fetches Gitee commits, and lists authors with commit counts. See routes/data.py (line 170).
Single contributor evaluation: evaluates a GitHub or Gitee author using selected plugin/model/language, supports chunking, parallel chunking, and aliases. See routes/evaluation.py (line 28).
Evaluation merging: merges multiple weighted evaluations, used especially for multi-alias identity aggregation. See routes/evaluation.py (line 251).
Batch workflows: batch extract 2-5 repos, find common contributors across repos, and compare one contributor across multiple repos. See routes/batch.py (line 16).
Growth trajectory analysis: analyzes engineer growth over time across repos, supports aliases, commit ranges, forced checkers, checkpoint strategies, and SSE streaming. See routes/trajectory.py (line 258).
Course/group code analysis: course-compatible full repository group evaluation endpoint, including streaming mode and expected-feature evaluation baseline. See routes/trajectory.py (line 586).
One-off external evaluation: one-off trajectory/checkpoint judgment without saving cache, optional start_sha/end_sha, username inference, and streaming variant. See routes/trajectory.py (line 783).
Benchmark validation: exposes benchmark dataset metadata, paginated benchmark repos, validation runs, and stored benchmark evaluations. See routes/benchmark.py (line 151).
Checker integration: discovers external checkers and runs them against a specific commit in an isolated git worktree. See routes/checkers.py (line 168).
Repos runner proxy: forwards /api/runner/* calls to the separate repo runner service on port 8001, including streaming run-all. See routes/runner_proxy.py (line 50).
Under the API layer it also provides collectors, extraction services, plugin/checker registries, XDG storage path helpers, commit loading/filtering utilities, and trajectory/evaluation services.
