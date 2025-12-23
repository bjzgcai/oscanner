# Engineer Capability Assessment System

AI-powered system for evaluating engineering capabilities by analyzing GitHub and Gitee commits, code changes, and collaboration patterns using a six-dimensional evaluation framework.

## Overview

This system uses LLM-powered analysis (Claude 4.5 Haiku) to evaluate software engineers based on actual code commits, diffs, and collaboration patterns from GitHub and Gitee repositories. Features a modern React + Antd dashboard and FastAPI backend with intelligent caching.

## Six-Dimensional Evaluation Framework

### 1. AI Model Full-Stack & Trade-off Capability (AI模型全栈与权衡能力)
**Focus Areas:** Research-production mutual promotion innovation, system optimization
- Deep learning framework usage and optimization
- Model selection and trade-off decisions
- End-to-end AI system implementation

### 2. AI Native Architecture & Communication Design (AI原生架构与沟通设计)
**Focus Areas:** Production-level platform, research-production mutual promotion innovation
- AI-first architecture design
- API and interface design for AI systems
- Documentation and communication patterns

### 3. Cloud Native & Constraint Engineering (云原生与约束工程化)
**Focus Areas:** Production-level platform, system optimization
- Containerization and orchestration
- Infrastructure as code
- CI/CD pipeline implementation
- Resource optimization and constraints

### 4. Open Source Collaboration & Requirements Translation (开源协作与需求转化)
**Focus Areas:** Open source co-construction, research-production mutual promotion innovation
- Open source contribution quality and frequency
- Issue management and PR reviews
- Requirements analysis and implementation

### 5. Intelligent Development & Human-Machine Collaboration (智能开发与人机协同)
**Focus Areas:** All specialties
- AI-assisted development practices
- Code generation and review
- Automation and tooling

### 6. Engineering Leadership & System Trade-offs (工程领导与系统权衡)
**Focus Areas:** System optimization, production-level platform, research-production mutual promotion innovation
- Technical decision making
- System architecture trade-offs
- Team collaboration and mentorship

## Features

- **AI-Powered Analysis**: Uses Claude 4.5 Haiku to analyze actual code changes and commit patterns
- **Dual Platform Support**: Analyzes both GitHub and Gitee repositories
- **Smart Caching**: Local storage system to minimize API calls and LLM token usage
- **Modern UI**: React + Antd + Antd-x dashboard with radar charts and detailed breakdowns
- **Real Commit Analysis**: Evaluates actual diffs, file changes, and code quality (not just keywords)

## Input & Output

**Input:**
- Repository URLs (GitHub/Gitee)
- Contributor username

**Output:**
- Six-dimensional scores (0-100 scale)
- AI-generated reasoning and analysis
- Commit statistics and code metrics
- Visual radar chart and detailed breakdowns

## Installation

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

# Optional: Gitee token
GITEE_TOKEN=your-gitee-token-here
```

See `.env.example` for reference.

## Usage

### 1. Start the Server

```bash
python server.py
```

The server will auto-detect an available port (8000, 8001, etc.).

### 2. Open the Dashboard

Open `dashboard.html` in your browser, or navigate to:
```
http://localhost:8000/dashboard.html
```

### 3. Analyze Engineers

**Via Dashboard:**
1. Enter a GitHub/Gitee repository URL
2. Click "Analyze Repository"
3. Select a contributor to evaluate
4. View AI-powered evaluation results with scores and charts

**Via API:**

```bash
# Fetch commits
curl http://localhost:8000/api/commits/octocat/Hello-World

# Evaluate a contributor
curl -X POST "http://localhost:8000/api/evaluate/octocat/Hello-World/octocat?limit=30"
```

## Project Structure

```
.
├── README.md                   # This file
├── README_EVALUATION.md        # Detailed technical documentation
├── requirements.txt            # Python dependencies
├── .env.example               # Environment variables template
├── server.py                  # FastAPI backend server
├── dashboard.html             # Frontend UI (React + Antd)
├── evaluator/
│   ├── __init__.py
│   ├── core.py                # Main evaluation engine
│   ├── dimensions.py          # Six dimension evaluators
│   ├── commit_evaluator.py    # LLM-powered commit analysis
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── github.py          # GitHub API integration
│   │   └── gitee.py           # Gitee API integration
│   ├── analyzers/             # (Reserved for future use)
│   └── reporters/             # (Reserved for future use)
└── data/                      # Cached commit data
    └── {owner}/{repo}/
        ├── commits/           # Individual commit files
        └── commits_list.json
```

## How It Works

### 1. Commit Collection
- Fetches commits from GitHub/Gitee API
- Retrieves detailed commit data including files changed and diffs
- Caches data locally in `./data/{owner}/{repo}/commits/` to reduce API calls

### 2. LLM-Powered Analysis
The system sends commit data to Claude 4.5 Haiku with:
- Commit messages and descriptions
- File changes (additions/deletions by language)
- Code diffs (patches)
- Commit statistics and patterns

### 3. Evaluation Criteria

The LLM evaluates based on actual code evidence:

**AI Full-Stack**
- ML framework usage (TensorFlow, PyTorch, etc.)
- Model architecture implementations
- Training and optimization code
- Model deployment patterns

**AI Architecture**
- API design quality
- Service architecture patterns
- Documentation quality
- Integration and interface design

**Cloud Native**
- Docker/Kubernetes configurations
- CI/CD pipeline definitions
- Infrastructure as Code
- Cloud platform integration

**Open Source Collaboration**
- Commit message clarity
- Issue/PR references and linking
- Code review participation
- Refactoring and improvement quality

**Intelligent Development**
- Test coverage and automation
- Development tooling and scripts
- Build configurations
- AI-assisted development practices

**Engineering Leadership**
- Performance optimizations
- Security considerations
- Best practice adoption
- Architectural decision making

### 4. Scoring
- Each dimension scored 0-100
- Scores based on actual code analysis (not keywords)
- LLM provides detailed reasoning for each evaluation
- Caching ensures efficient token usage

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API information |
| `/health` | GET | Health check |
| `/api/commits/{owner}/{repo}` | GET | Get commits list |
| `/api/commits/{owner}/{repo}/{sha}` | GET | Get commit details |
| `/api/commits/{owner}/{repo}/fetch-all` | POST | Fetch all commits with details |
| `/api/evaluate/{owner}/{repo}/{username}` | POST | Evaluate engineer capabilities |
| `/api/cache/stats` | GET | View cache statistics |
| `/api/cache/clear` | DELETE | Clear all cached data |

## Architecture

```
Frontend (dashboard.html - React + Antd)
    ↓
FastAPI Server (server.py)
    ↓
┌─────────────────┴─────────────────┐
│                                    │
GitHubCollector/GiteeCollector   CommitEvaluator
(collectors/*.py)                (commit_evaluator.py)
    ↓                                 ↓
GitHub/Gitee API              OpenRouter API
    ↓                                 ↓
Local Cache (data/)           Claude 4.5 Haiku
```

## Limitations & Considerations

- **API Rate Limits**: GitHub API has rate limits (60/hour without token, 5000/hour with token)
- **LLM Costs**: Each evaluation costs ~$0.02-0.05 depending on commit volume
- **Analysis Depth**: Analyzes up to 30 commits per evaluation by default (configurable)
- **Caching**: Smart local caching minimizes API calls and LLM token usage

## Roadmap

- [ ] Complete Gitee integration
- [ ] Batch evaluation of all contributors
- [ ] Historical trend analysis
- [ ] Team-level aggregation
- [ ] Export reports (PDF, JSON)
- [ ] Comparison between contributors
- [ ] Time-series skill evolution
- [ ] Integration with CI/CD pipelines
- [ ] Enhanced UI with more visualizations

## License

MIT License

## Documentation

For detailed technical documentation, see [README_EVALUATION.md](README_EVALUATION.md)
