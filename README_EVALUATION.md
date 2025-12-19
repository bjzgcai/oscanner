# GitHub Engineer Skill Evaluator

LLM-powered system for evaluating engineering capabilities by analyzing GitHub commits, diffs, and code changes.

## Features

- **AI-Powered Analysis**: Uses Claude 4.5 Haiku via OpenRouter to analyze commits
- **Six Dimensions**: Evaluates engineers across six key capability dimensions
- **Real Commit Analysis**: Analyzes actual code changes, diffs, and commit patterns
- **Caching System**: Efficiently caches GitHub API data to reduce API calls
- **Modern Dashboard**: Clean, responsive UI with radar charts and detailed breakdowns

## Six Evaluation Dimensions

1. **AI Model Full-Stack**: AI/ML model development, training, optimization, deployment
2. **AI Native Architecture**: AI-first system design, API architecture, microservices
3. **Cloud Native Engineering**: Containerization, IaC, CI/CD, cloud platforms
4. **Open Source Collaboration**: Code review, issue management, communication quality
5. **Intelligent Development**: AI-assisted development, automation, testing
6. **Engineering Leadership**: Technical decisions, optimization, security, best practices

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env.local` file with your API keys:

```bash
# OpenRouter API key for LLM evaluation
OPEN_ROUTER_KEY=sk-or-v1-your-key-here

# Optional: GitHub token for higher rate limits
GITHUB_TOKEN=ghp_your-token-here
```

### 3. Start the Server

```bash
# Using the start script
./start_server.sh

# Or manually
python server.py
```

The server will auto-detect an available port (8000, 8001, etc.).

### 4. Open the Dashboard

Open [dashboard.html](dashboard.html) in your browser, or navigate to:
```
http://localhost:8000/dashboard.html
```

## Usage

### Via Dashboard

1. Enter a GitHub repository URL (e.g., `https://github.com/octocat/Hello-World`)
2. Click "Analyze Repository"
3. Select a contributor to evaluate
4. View AI-powered evaluation results with scores, charts, and analysis

### Via API

#### Fetch Commits
```bash
# Get commits list
curl http://localhost:8000/api/commits/octocat/Hello-World

# Get specific commit details
curl http://localhost:8000/api/commits/octocat/Hello-World/{commit_sha}

# Fetch all commits with details
curl -X POST http://localhost:8000/api/commits/octocat/Hello-World/fetch-all?limit=50
```

#### Evaluate Engineer
```bash
# Evaluate a specific contributor
curl -X POST "http://localhost:8000/api/evaluate/octocat/Hello-World/octocat?limit=30"
```

Response:
```json
{
  "success": true,
  "evaluation": {
    "username": "octocat",
    "total_commits_analyzed": 30,
    "total_commits": 100,
    "scores": {
      "ai_fullstack": 75,
      "ai_architecture": 82,
      "cloud_native": 68,
      "open_source": 90,
      "intelligent_dev": 73,
      "leadership": 85,
      "reasoning": "Strong architecture and collaboration skills..."
    },
    "commits_summary": {
      "total_additions": 2547,
      "total_deletions": 1823,
      "files_changed": 156,
      "languages": ["py", "js", "ts", "md"]
    }
  }
}
```

## How It Works

### 1. Commit Collection
- Fetches commits from GitHub API using REST endpoints
- Retrieves detailed commit data including files changed and diffs
- Caches data locally in `./data/{owner}/{repo}/commits/`

### 2. LLM Analysis
The system sends commit data to Claude 4.5 Haiku with:
- Commit messages
- File changes (additions/deletions)
- Code diffs (patches)
- Commit statistics

### 3. Evaluation Criteria

The LLM evaluates based on:

**AI Full-Stack**
- ML framework usage (TensorFlow, PyTorch, etc.)
- Model architecture implementations
- Training and optimization code
- Model deployment patterns

**AI Architecture**
- API design quality
- Service architecture
- Documentation quality
- Integration patterns

**Cloud Native**
- Docker/Kubernetes configurations
- CI/CD pipeline definitions
- Infrastructure as Code
- Cloud platform usage

**Open Source Collaboration**
- Commit message clarity
- Issue/PR references
- Code review participation
- Refactoring quality

**Intelligent Development**
- Test coverage and quality
- Automation scripts
- Development tooling
- Build configurations

**Engineering Leadership**
- Performance optimizations
- Security considerations
- Best practice adoption
- Architectural decisions

### 4. Scoring
- Each dimension scored 0-100
- Scores based on actual code analysis, not keywords
- LLM provides reasoning for evaluation

## Data Storage

Commit data is cached in structured directories:

```
data/
├── owner/
│   ├── repo/
│   │   ├── commits/
│   │   │   ├── {sha1}.json
│   │   │   ├── {sha2}.json
│   │   │   └── ...
│   │   └── commits_list.json
│   └── repo.json
```

Each commit file contains:
- Full commit metadata
- Author information
- Changed files
- Diff patches
- Statistics

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API information |
| `/health` | GET | Health check |
| `/api/commits/{owner}/{repo}` | GET | Get commits list |
| `/api/commits/{owner}/{repo}/{sha}` | GET | Get commit details |
| `/api/commits/{owner}/{repo}/fetch-all` | POST | Fetch all commits |
| `/api/evaluate/{owner}/{repo}/{username}` | POST | Evaluate engineer |
| `/api/cache/stats` | GET | Cache statistics |
| `/api/cache/clear` | DELETE | Clear all cache |

## Limitations

- **API Rate Limits**: GitHub API has rate limits (60/hour without token, 5000/hour with token)
- **LLM Costs**: Each evaluation costs ~$0.02-0.05 depending on commit volume
- **Analysis Depth**: Analyzes up to 30 commits per evaluation (configurable)
- **Public Repos Only**: GitHub API restrictions

## Troubleshooting

**Server won't start**
- Check if port 8000-8005 are available
- Ensure all dependencies are installed

**API key errors**
- Verify `.env.local` exists and contains valid keys
- Check OpenRouter API key is active

**No commits found**
- Verify repository URL is correct
- Check GitHub token permissions
- Ensure commits exist for the specified user

**Evaluation fails**
- Check OpenRouter API key balance
- Verify internet connectivity
- Review server logs for detailed errors

## Architecture

```
Frontend (dashboard.html)
    ↓
FastAPI Server (server.py)
    ↓
┌─────────────────┴─────────────────┐
│                                    │
GitHubCollector          CommitEvaluator
(github.py)              (commit_evaluator.py)
    ↓                            ↓
GitHub API              OpenRouter API
    ↓                            ↓
Cache (data/)            Claude 4.5 Haiku
```

## Future Enhancements

- [ ] Batch evaluation of all contributors
- [ ] Historical trend analysis
- [ ] Team-level aggregation
- [ ] Custom evaluation criteria
- [ ] Export reports (PDF, JSON)
- [ ] Comparison between contributors
- [ ] Time-series skill evolution
- [ ] Integration with CI/CD pipelines

## License

This project uses the OpenRouter API and requires an active API key.
