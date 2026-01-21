# Engineer Capability Assessment System

A comprehensive evaluation system that analyzes engineer capabilities based on GitHub and Gitee activity. The system uses LLM-powered analysis to evaluate software engineers across six key dimensions of engineering excellence.

## Overview

The Engineer Capability Assessment System collects data from GitHub/Gitee repositories and commits, then uses AI-powered analysis to evaluate engineering skills across multiple dimensions. It provides both a programmatic API and a FastAPI web service for evaluation.

## Quick Start (uv + CLI)

From repository root:

```bash
# Install dependencies
# First-time setup (if `uv.lock` is not present in the repo)
uv lock

# Then sync dependencies (creates/updates .venv)
uv sync

# Quick start without lock (not reproducible):
# uv sync --no-lock

# Start backend API
uv run oscanner serve --reload
```

Dashboard (optional):

```bash
cd webapp && npm install && npm run dev
```

## Key Features

- **Six-Dimensional Evaluation Framework**: Comprehensive assessment across AI/ML, architecture, cloud native, collaboration, intelligent development, and leadership
- **Multi-Platform Support**: Works with both GitHub and Gitee repositories
- **Smart Caching**: Caches API responses and evaluation results to save time and API tokens
- **LLM-Powered Analysis**: Uses Claude Sonnet 4.5 via OpenRouter with automatic fallback to Z.AI GLM 4.7 for intelligent commit analysis
- **Automatic Model Fallback**: Seamlessly switches from Claude to Z.AI GLM 4.7 if the primary model fails
- **FastAPI Web Service**: RESTful API for integration with dashboards and applications
- **Local & Remote Data**: Supports both API-based and local file-based data analysis

## Directory Structure

```
evaluator/
├── __init__.py                          # Package initialization
├── core.py                              # Core evaluation engine
├── dimensions.py                        # Six-dimensional evaluation framework
├── server.py                            # FastAPI web service
├── commit_evaluator_moderate.py         # Moderate commit analyzer variant
├── contributtor.py                      # Contributor analysis
├── collectors/                          # Data collection modules
│   ├── __init__.py
│   ├── github.py                        # GitHub API collector
│   └── gitee.py                         # Gitee API collector
├── analyzers/                           # Code analysis modules
│   ├── __init__.py
│   ├── code_analyzer.py                 # Code quality analyzer
│   ├── commit_analyzer.py               # Commit pattern analyzer
│   └── collaboration_analyzer.py        # Collaboration analyzer
├── tools/                               # Data extraction tools
│   ├── __init__.py
│   └── extract_repo_data_moderate.py
└── requirements.txt                     # (legacy) Python dependencies; prefer pyproject.toml + uv
```

## Six Evaluation Dimensions

### 1. AI Model Full-Stack & Trade-off Capability
Evaluates AI/ML model development, training, optimization, and deployment capabilities.
- ML framework usage (TensorFlow, PyTorch, etc.)
- Model architecture and design
- Training pipelines and optimization
- Model serving and inference optimization
- End-to-end ML pipeline implementation

### 2. AI Native Architecture & Communication Design
Assesses AI-first system design, API design, and microservices architecture.
- AI service API design
- Microservices and distributed systems
- Architecture documentation
- Communication patterns and design
- Integration patterns and scalability

### 3. Cloud Native & Constraint Engineering
Measures containerization, infrastructure as code, and DevOps practices.
- Docker and containerization
- Kubernetes and orchestration
- CI/CD pipelines
- Infrastructure as Code (Terraform, CloudFormation)
- Resource optimization

### 4. Open Source Collaboration & Requirements Translation
Evaluates collaboration quality, communication, and community engagement.
- Contribution frequency and quality
- Code review participation
- Issue management
- Cross-repository collaboration
- Requirements-to-code translation

### 5. Intelligent Development & Human-Machine Collaboration
Assesses automation, tooling, testing, and AI-assisted development.
- Automation scripts and tools
- AI-assisted development practices
- Test automation
- Custom tooling development
- Development efficiency

### 6. Engineering Leadership & System Trade-offs
Measures technical decision-making, mentorship, and architectural leadership.
- Mentorship and code review quality
- Architectural decisions
- Technical decision documentation
- Project ownership
- Team collaboration and leadership

## Installation

### Prerequisites
- Python 3.8+
- pip

### Setup

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Configure environment variables:**
```bash
cp .env.example .env.local
```

Edit `.env.local` and add your API keys:
```env
# OpenRouter API key for LLM evaluation
OPEN_ROUTER_KEY=sk-or-v1-your-key-here

# GitHub token (optional, for higher API rate limits)
GITHUB_TOKEN=your_github_token

# Gitee tokens (optional)
GITEE_TOKEN=your_enterprise_gitee_token
```

## Complete Workflow

### System Architecture

The evaluation system follows this intelligent workflow to minimize API calls and maximize caching:

```
┌─────────────────────────────────────────────────────────────────┐
│  User enters GitHub URL (e.g., github.com/owner/repo)          │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  Frontend: GET /api/local/authors/{owner}/{repo}                │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  Backend: Check evaluation cache at                             │
│  evaluations/cache/{owner}/{repo}/evaluations.json              │
└────────────────────┬────────────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
    Cache Hit               Cache Miss
         │                       │
         ▼                       ▼
    Return cached     ┌──────────────────────────┐
    author list       │ Check local data at      │
    instantly ⚡      │ data/{owner}/{repo}/     │
                      └──────────┬───────────────┘
                                 │
                     ┌───────────┴───────────┐
                     │                       │
                Data Exists            Data Missing
                     │                       │
                     │                       ▼
                     │          ┌─────────────────────────────┐
                     │          │ Extract from GitHub using   │
                     │          │ extract_repo_data_moderate  │
                     │          │ (1-2 minutes, once per repo)│
                     │          └──────────┬──────────────────┘
                     │                     │
                     └──────────┬──────────┘
                                │
                                ▼
                   ┌────────────────────────────┐
                   │ Load all authors from      │
                   │ commit data                │
                   └────────────┬───────────────┘
                                │
                                ▼
                   ┌────────────────────────────┐
                   │ Auto-evaluate first author │
                   │ with AI (Claude Sonnet 4.5)│
                   └────────────┬───────────────┘
                                │
                                ▼
                   ┌────────────────────────────┐
                   │ Cache evaluation result    │
                   │ in evaluations.json        │
                   └────────────┬───────────────┘
                                │
                                ▼
                   ┌────────────────────────────┐
                   │ Return all authors list    │
                   └────────────────────────────┘
```

### Evaluation Flow (Per Author)

```
┌─────────────────────────────────────────────────────────────────┐
│  User clicks on author                                          │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  Frontend: POST /api/evaluate/{owner}/{repo}/{author}           │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  Backend: Check if author exists in evaluation cache            │
└────────────────────┬────────────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
    Cache Hit               Cache Miss
         │                       │
         ▼                       ▼
    Return cached     ┌──────────────────────────┐
    evaluation        │ Load commits from local  │
    instantly ⚡      │ data (up to 30 commits)  │
                      └──────────┬───────────────┘
                                 │
                                 ▼
                      ┌──────────────────────────┐
                      │ Create evaluator with    │
                      │ repository context       │
                      └──────────┬───────────────┘
                                 │
                                 ▼
                      ┌──────────────────────────┐
                      │ Evaluate author with AI  │
                      │ - Analyze commit diffs   │
                      │ - Read relevant files    │
                      │ - Score 6 dimensions     │
                      └──────────┬───────────────┘
                                 │
                                 ▼
                      ┌──────────────────────────┐
                      │ Cache evaluation result  │
                      └──────────┬───────────────┘
                                 │
                                 ▼
                      ┌──────────────────────────┐
                      │ Return evaluation        │
                      └──────────────────────────┘
```

### Batch Repository Comparison (/repos Page)

The system supports comparing multiple repositories to find common contributors, useful for:
- Identifying developers with experience across multiple projects
- Finding potential collaborators
- Analyzing cross-project contributions
- Team composition analysis

#### Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│  User enters 2-5 GitHub repository URLs                         │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  Frontend: POST /api/batch/extract                              │
│  Extracts data for all repositories                             │
└────────────────────┬────────────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
    Data Exists             Data Missing
         │                       │
         ▼                       ▼
    Skip extraction    ┌──────────────────────────┐
                       │ Extract from GitHub      │
                       │ (1-2 min per repo)       │
                       └──────────┬───────────────┘
                                  │
                     ┌────────────┴────────────┐
                     │                         │
                     ▼                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Frontend: POST /api/batch/common-contributors                  │
│  Analyzes all repositories for common contributors              │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  Backend: Intelligent Contributor Matching (3-pass algorithm)   │
│                                                                  │
│  Pass 1: Group by GitHub ID/login (strong identity signals)     │
│  Pass 2: Fuzzy name matching for orphaned authors               │
│  Pass 3: Exact name matching for remaining authors              │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  Return common contributors with:                               │
│  - Author name (most complete version)                          │
│  - GitHub login                                                 │
│  - Email address                                                │
│  - Commit counts per repository                                 │
│  - Total commits across all repos                               │
│  - Matching method used (github_id, github_login, or name)      │
└─────────────────────────────────────────────────────────────────┘
```

#### Intelligent Contributor Matching

The system uses a sophisticated three-pass matching algorithm to identify the same person across repositories, even when they use different names or email addresses:

**Pass 1: GitHub ID/Login Matching**
- Groups contributors by GitHub user ID (strongest signal)
- Falls back to GitHub login if ID unavailable
- Creates identity anchors for fuzzy matching

**Pass 2: Fuzzy Name Matching**
- Matches orphaned authors (no GitHub ID) to existing groups
- Compares first names: "Sebastian" matches "Sebastian Markbage"
- Handles common name variations and shortened names
- Useful for old SVN-converted repositories

**Pass 3: Exact Name Matching**
- Groups remaining unmatched authors by exact normalized name
- Fallback for completely unique contributors

**Example Matching Cases:**
```json
{
  "matched_by": "github_id",
  "author": "Sebastian Markbage",
  "github_login": "sebmarkbage",
  "repos": [
    {
      "repo": "animation-timelines",
      "commits": 15,
      "email": "sebastian@calyptus.eu"
    },
    {
      "repo": "calyptus.mvc",
      "commits": 68,
      "email": "Sebastian@8f9bea60-9d31-4c44-a11a-6657d2e7921d"
    }
  ]
}
```

In this example, even though the emails are different and one repo has "Sebastian" while the other has "Sebastian Markbage", the system correctly identifies them as the same person through GitHub ID matching and fuzzy name matching.

### Directory Structure After Processing

```
evaluator/
├── data/                                    # Repository data (extracted once)
│   └── {owner}/
│       └── {repo}/
│           ├── repo_info.json              # Repository metadata
│           ├── repo_tree.json              # File tree structure
│           ├── commits_index.json          # Index of all commits
│           ├── commits_list.json           # API commit list
│           ├── commits/
│           │   ├── {sha}.json              # Commit metadata + diff
│           │   └── {sha}.diff              # Commit diff (separate)
│           └── files/
│               └── {filepath}              # Current file contents
│
└── evaluations/                             # Cached evaluations
    └── cache/
        └── {owner}/
            └── {repo}/
                └── evaluations.json        # All author evaluations
                                            # {
                                            #   "author1": {
                                            #     "evaluation": {...},
                                            #     "timestamp": "...",
                                            #     "cached": true
                                            #   },
                                            #   "author2": {...}
                                            # }
```

### Performance Benefits

**First Repository Access (New):**
- 1-2 minutes to extract data from GitHub
- AI evaluation for first author (~10-20 seconds)
- Total: ~2 minutes

**Second+ Repository Access (Cached):**
- Authors list: **Instant** (from cache)
- First author evaluation: **Instant** (from cache)
- Other authors: First click ~10-20 seconds, then instant
- Total: **< 1 second**

**Batch Repository Comparison (2-5 repos):**
- First extraction: 1-2 minutes per repo (parallel processing)
- Already extracted: **Instant** skip
- Common contributors analysis: **< 2 seconds** (pure computation)
- Total first-time: ~2-5 minutes for all repos
- Total cached: **< 2 seconds**

**Token Usage:**
- Without caching: ~50-100k tokens per evaluation × N authors = expensive
- With caching: ~50-100k tokens × N unique evaluations = efficient
- Cache hit rate: Typically 80-90% after initial use
- Batch comparison: **0 tokens** (no LLM calls, pure data analysis)

## Usage

### 1. Programmatic Usage

```python
from evaluator import EngineerEvaluator

# Initialize evaluator
config = {
    "github_token": "your_github_token",
    "gitee_token": "your_gitee_token"
}
evaluator = EngineerEvaluator(config)

# Evaluate a GitHub user
result = evaluator.evaluate(
    github_username="octocat",
    repos=["https://github.com/octocat/Hello-World"]
)

# Print text report
print(result.get_report(format="text"))

# Get JSON output
print(result.get_report(format="json"))

# Access specific information
print(f"Overall Score: {result.overall_score}")
print(f"Top Strengths: {result.get_top_dimensions(3)}")
print(f"Areas to Develop: {result.get_bottom_dimensions(3)}")
```

### 2. FastAPI Web Service

Start the server:

```bash
python server.py
# or
./start_server.sh
```

The server will start on `http://localhost:8000` with the following endpoints:

#### API Endpoints

**Health Check:**
```
GET /health
```

**Get Gitee Commits:**
```
GET /api/gitee/commits/{owner}/{repo}?limit=100&use_cache=true&is_enterprise=false
```

**Evaluate Gitee Contributor:**
```
POST /api/gitee/evaluate/{owner}/{repo}/{contributor}?limit=30&use_cache=true
```

**Get Authors List (Smart Cache):**
```
GET /api/local/authors/{owner}/{repo}
```
Returns all authors with intelligent caching:
- Checks evaluation cache first
- If missing, checks local data
- If missing, extracts from GitHub automatically
- Auto-evaluates first author

**Evaluate Author (Primary Endpoint):**
```
POST /api/evaluate/{owner}/{repo}/{author}?limit=30&use_cache=true
```
Evaluates a specific author with caching:
- Returns cached result if available
- Otherwise performs AI evaluation and caches it

**Batch Extract Repositories:**
```
POST /api/batch/extract
```
Extract data from multiple GitHub repositories in one request (2-5 repos):
```json
{
  "urls": [
    "https://github.com/owner1/repo1",
    "https://github.com/owner2/repo2"
  ]
}
```
Returns extraction status for each repository.

**Find Common Contributors:**
```
POST /api/batch/common-contributors
```
Find developers who contributed to multiple repositories:
```json
{
  "repos": [
    {"owner": "owner1", "repo": "repo1"},
    {"owner": "owner2", "repo": "repo2"}
  ]
}
```
Returns list of common contributors with intelligent matching.

**Compare Contributor Across Repositories:**
```
POST /api/batch/compare-contributor
```
Compare a contributor's six-dimensional capability scores across multiple repositories:
```json
{
  "contributor": "John Doe",
  "repos": [
    {"owner": "facebook", "repo": "react"},
    {"owner": "vercel", "repo": "next.js"}
  ]
}
```
Returns evaluation data for visualization:
- Six-dimensional scores for each repository
- Aggregate statistics (average scores, total commits)
- Cached status for performance
- Support for up to 10 repositories per comparison

This endpoint enables:
- **Cross-repo capability analysis**: See how a contributor's skills vary across different projects
- **Specialization insights**: Identify which dimensions are consistently strong or weak
- **Context-aware evaluation**: Understand how different project types showcase different capabilities
- **Visual comparison**: Data formatted for radar, bar, heatmap, and line charts

#### Example API Call

```bash
# Get authors (will auto-fetch and cache if needed)
curl "http://localhost:8000/api/local/authors/anthropics/anthropic-sdk-python"

# Evaluate a specific author
curl -X POST "http://localhost:8000/api/evaluate/anthropics/anthropic-sdk-python/octocat?limit=30"

# Force fresh evaluation (ignore cache)
curl -X POST "http://localhost:8000/api/evaluate/anthropics/anthropic-sdk-python/octocat?limit=30&use_cache=false"

# Batch extract multiple repositories
curl -X POST "http://localhost:8000/api/batch/extract" \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://github.com/owner/repo1", "https://github.com/owner/repo2"]}'

# Find common contributors across repositories
curl -X POST "http://localhost:8000/api/batch/common-contributors" \
  -H "Content-Type: application/json" \
  -d '{"repos": [{"owner": "owner1", "repo": "repo1"}, {"owner": "owner2", "repo": "repo2"}]}'

# Compare a contributor across multiple repositories
curl -X POST "http://localhost:8000/api/batch/compare-contributor" \
  -H "Content-Type: application/json" \
  -d '{"contributor": "John Doe", "repos": [{"owner": "facebook", "repo": "react"}, {"owner": "vercel", "repo": "next.js"}]}'
```

### 3. LLM-Based Commit Evaluation

```python
from evaluator.commit_evaluator import CommitEvaluator
from evaluator.collectors.github import GitHubCollector

# Initialize
collector = GitHubCollector(token="your_github_token")
evaluator = CommitEvaluator(api_key="your_openrouter_key")

# Fetch commits
commits = collector.fetch_commits_list("owner", "repo", limit=100)

# Filter commits by author
author_commits = [
    c for c in commits
    if c.get("commit", {}).get("author", {}).get("name") == "Author Name"
]

# Evaluate engineer
result = evaluator.evaluate_engineer(
    commits=author_commits,
    username="Author Name",
    max_commits=20
)

print(f"Scores: {result['scores']}")
print(f"Summary: {result['commits_summary']}")
```

## Caching Strategy

The system implements intelligent caching to optimize performance and reduce costs:

### 1. API Response Caching
- GitHub/Gitee API responses are cached locally in `data/` directory
- Commits are cached per repository
- Cache is automatically checked before making API calls

### 2. Evaluation Result Caching
- LLM evaluation results are cached to avoid redundant API calls
- Cache is stored in `evaluations/` subdirectories
- Use `use_cache=false` to force fresh evaluation

### 3. Repository Context Caching
- Full repository context is cached in-memory during server runtime
- Evaluating multiple contributors from the same repo reuses cached context
- Significantly reduces token usage and response time

## Data Storage

### Local Data Structure

```
data/
├── {owner}/
│   └── {repo}/
│       ├── repo_info.json              # Repository metadata
│       ├── commits_index.json          # List of commit hashes
│       ├── commits/
│       │   ├── {sha}.json              # Individual commit data
│       │   └── {sha}/
│       │       ├── {sha}.json          # Commit metadata
│       │       ├── {sha}.diff          # Commit diff
│       │       └── files/              # Modified files
│       └── evaluations/
│           └── {author}.json           # Cached evaluations
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPEN_ROUTER_KEY` | OpenRouter API key for LLM calls | Yes |
| `GITHUB_TOKEN` | GitHub personal access token | No |
| `GITEE_TOKEN` | Enterprise Gitee access token | No |
| `PORT` | Server port (default: 8000) | No |

### Evaluation Parameters

- `max_commits`: Maximum commits to analyze (default varies by evaluator)
- `max_input_tokens`: Maximum tokens for LLM input (default: 190,000)
- `use_cache`: Enable/disable caching (default: true)
- `force_refresh`: Force re-evaluation ignoring cache (default: false)

### LLM Model Fallback Mechanism

The system implements automatic model fallback for maximum reliability:

**Fallback Chain:**
1. **Primary**: `anthropic/claude-sonnet-4.5` - High-quality, context-aware evaluation
2. **Fallback**: `z-ai/glm-4.7` - Enhanced programming and reasoning capabilities if Claude fails
3. **Emergency**: Keyword-based evaluation - Simple heuristic if both LLMs fail

**How it works:**
- The evaluator automatically tries Claude Sonnet 4.5 first
- If Claude fails (API error, timeout, rate limit, etc.), it immediately retries with Z.AI GLM 4.7
- If both LLM models fail, it falls back to a keyword-based heuristic evaluation
- All transitions are logged with clear messages indicating which model was used
- No manual intervention required - the system handles failures gracefully

**Example output:**
```
[LLM] Trying Claude Sonnet 4.5...
[Warning] Claude Sonnet 4.5 failed: Rate limit exceeded
[Fallback] Trying next model...
[LLM] Trying Z.AI GLM 4.7...
[Success] Used Z.AI GLM 4.7
[Token Usage] Input: 45234, Output: 892, Total: 46126
```

This ensures evaluations always complete, even during API outages or rate limiting.

## Advanced Features

### Full Context Evaluation

The `FullContextCachedEvaluator` provides the most comprehensive evaluation:

```python
from evaluator.full_context_cached_evaluator import FullContextCachedEvaluator

evaluator = FullContextCachedEvaluator(
    data_dir="data/owner/repo",
    api_key="your_openrouter_key"
)

result = evaluator.evaluate_contributor(
    contributor_name="Author Name",
    use_cache=True
)
```

### Repository-Wide Evaluation

```python
from evaluator.full_repo_evaluator import FullRepoEvaluator

evaluator = FullRepoEvaluator(api_key="your_openrouter_key")
result = evaluator.evaluate_repository("owner/repo")
```

## Development

### Running Tests

```bash
# Example evaluation with local data
python example_moderate_evaluation.py
```

### Starting Development Server

```bash
# With auto-reload
uvicorn server:app --reload --port 8000

# Or use the startup script
./start_server.sh
```

## API Documentation

When the server is running, access interactive API documentation at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Performance Considerations

### Token Usage Optimization

1. **Commit Sampling**: Analyzes top N commits (default 20-30) instead of all commits
2. **Context Truncation**: Automatically truncates context to fit token limits
3. **Smart Caching**: Caches both API responses and LLM evaluations
4. **Repository Context Reuse**: Shares repository context across multiple contributor evaluations

### Rate Limiting

- GitHub API: 5,000 requests/hour (authenticated), 60/hour (unauthenticated)
- Gitee API: Varies by plan
- OpenRouter: Depends on your plan and selected model

Use tokens and caching to stay within rate limits.

## Troubleshooting

### Common Issues

**Issue: "No API key configured"**
- Solution: Set `OPEN_ROUTER_KEY` in `.env.local`

**Issue: "Failed to fetch GitHub commits"**
- Solution: Check your `GITHUB_TOKEN` and repository access permissions

**Issue: "Context truncated to fit token limit"**
- Solution: This is normal behavior. Adjust `max_input_tokens` if needed

**Issue: "No local data found"**
- Solution: First fetch data using API endpoints or manually populate `data/` directory

**Issue: "No Common Contributors Found" despite same author**
- Cause: Different author names across repositories (e.g., "John" vs "John Doe")
- Solution: The system automatically handles this with fuzzy matching
- Check the `matched_by` field in the response to see how matching was performed
- If still not matching, the names may be too different (e.g., completely different names)

**Issue: Batch extraction fails for some repositories**
- Solution: Check repository access permissions and GitHub token
- Private repositories require a token with appropriate permissions
- Some repositories may have unusual structures or no commit history

**Issue: Common contributors showing duplicate entries**
- Cause: Edge case in fuzzy matching algorithm
- Solution: Check if authors have significantly different emails or no GitHub ID
- The system prioritizes GitHub ID > Login > Name for matching

### Debug Mode

Enable verbose logging:

```bash
export LOG_LEVEL=DEBUG
python server.py
```

## Use Cases

### 1. Identifying Cross-Project Contributors
Find developers who contributed to multiple related projects:
```bash
# Example: Find contributors across React ecosystem projects
curl -X POST "http://localhost:8000/api/batch/common-contributors" \
  -H "Content-Type: application/json" \
  -d '{
    "repos": [
      {"owner": "facebook", "repo": "react"},
      {"owner": "vercel", "repo": "next.js"},
      {"owner": "remix-run", "repo": "remix"}
    ]
  }'
```

### 2. Hiring and Recruitment
Identify candidates with diverse experience:
- Look for contributors across your tech stack
- Find developers familiar with similar domains
- Assess breadth of open source contributions

### 3. Team Composition Analysis
Understand contributor overlap in your organization:
- Find developers working across multiple internal projects
- Identify potential knowledge silos
- Plan cross-team collaboration

### 4. Open Source Community Analysis
Study contribution patterns:
- Track contributor mobility across projects
- Identify core community members
- Understand ecosystem dynamics

### Best Practices

**Repository Selection:**
- Choose 2-5 repositories for optimal performance
- Select related projects for meaningful results
- Mix of sizes (small + large) works well

**Matching Confidence:**
- `matched_by: "github_id"` - Highest confidence (same GitHub account)
- `matched_by: "github_login"` - High confidence (same username)
- `matched_by: "name"` - Medium confidence (fuzzy name match)

**Handling Old Repositories:**
- SVN-converted repos may lack GitHub IDs
- System automatically uses fuzzy matching for these
- Check email addresses for additional verification

## Contributing

This is part of a larger evaluation system. For contributions:
1. Follow the existing code structure
2. Add tests for new features
3. Update documentation
4. Ensure caching works correctly with your changes

## License

See the main project LICENSE file.

## Related Documentation

- [Main Project README](../README.md)
- [Webapp Documentation](../webapp/README.md)
- [Audit Tools](../audit/README.md)
