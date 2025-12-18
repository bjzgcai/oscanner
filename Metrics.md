Here's how each of the six dimensions is calculated:

  Scoring Formula

  Each dimension score (0-100) is calculated using:

  Total Score = Commit Score (0-50) + Keyword Score (0-50)

  1. Commit Score (0-50 points)

  commitScore = Math.min(50, (commitCount / 100) * 50)
  - Based on the total number of commits
  - 100+ commits = maximum 50 points
  - Scales linearly: 50 commits = 25 points, 10 commits = 5 points

  2. Keyword Score (0-50 points)

  keywordScore = Math.min(50, keywordMatches * 5)
  - Each keyword match in commit messages = 5 points
  - 10+ keyword matches = maximum 50 points
  - Searches are case-insensitive

  Six Dimensions & Keywords

  Here's what keywords are analyzed for each dimension (lines 538-560):

  1. AI Model Full-Stack (ai_fullstack)
  - Keywords: model, training, tensorflow, pytorch, neural, deep learning, ml, ai, inference, optimization

  2. AI Native Architecture (ai_architecture)
  - Keywords: api, architecture, design, interface, endpoint, service, microservice, docs, documentation

  3. Cloud Native Engineering (cloud_native)
  - Keywords: docker, kubernetes, k8s, ci/cd, pipeline, deploy, container, cloud, aws, gcp, azure, terraform

  4. Open Source Collaboration (open_source)
  - Keywords: fix, issue, pr, pull request, review, merge, refactor, improve

  5. Intelligent Development (intelligent_dev)
  - Keywords: auto, script, tool, generator, automation, test, lint, format, cli

  6. Engineering Leadership (leadership)
  - Keywords: architecture, refactor, optimize, performance, security, best practice, pattern, design

  Example Calculation

  If a contributor has:
  - 80 commits → Commit Score = (80/100) * 50 = 40 points
  - 6 keyword matches in commit messages → Keyword Score = 6 * 5 = 30 points
  - Total Score = 70/100

  Current Limitations

  The current implementation is a simple heuristic approach. For a more accurate evaluation, you might want to
  consider:

  1. Analyzing actual code changes (lines added/deleted, file types)
  2. Checking for specific file patterns (Dockerfile, k8s manifests, etc.)
  3. Analyzing PR reviews and issues opened/resolved
  4. Code complexity metrics
  5. Language detection in changed files