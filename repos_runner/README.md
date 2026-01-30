## Repository Runner

This service provides automated repository cloning, exploration, and testing using Claude Code SDK.

## Features

- **Clone Repository**: Shallow clone of GitHub/Gitee repositories
- **Explore & Document**: Generate REPO_OVERVIEW.md using Claude AI
- **Run Tests**: Automatically identify and run test suites
- **Real-time Streaming**: Progress updates via Server-Sent Events (SSE)

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
# Required: Claude API key
export ANTHROPIC_API_KEY="your-api-key"
# OR
export OSCANNER_LLM_API_KEY="your-api-key"

# Optional: Custom port (default: 8001)
export RUNNER_PORT=8001
```

## Usage

### Start the server

```bash
./start_server.sh
```

The server will start on `http://localhost:8001`

API documentation available at: `http://localhost:8001/docs`

### Stop the server

```bash
./stop_server.sh
```

## API Endpoints

### 1. Clone Repository

**POST** `/api/runner/clone`

```json
{
  "repo_url": "https://github.com/owner/repo"
}
```

**Response:**
```json
{
  "repo_name": "repo",
  "default_branch": "main",
  "latest_commit_id": "abc123...",
  "clone_path": "/home/user/.local/share/oscanner/repos/repo",
  "platform": "github",
  "owner": "owner"
}
```

### 2. Explore Repository (Streaming)

**POST** `/api/runner/explore?clone_path=/path/to/repo`

Returns Server-Sent Events stream:
```
data: {"event":"progress","data":{"message":"Starting repository exploration..."}}
data: {"event":"progress","data":{"message":"Analyzing repository structure..."}}
data: {"event":"status","data":{"status":"completed","overview_path":"/path/to/REPO_OVERVIEW.md"}}
```

### 3. Run Tests (Streaming)

**POST** `/api/runner/run-tests?clone_path=/path/to/repo&overview_path=/path/to/REPO_OVERVIEW.md`

Returns Server-Sent Events stream with test results:
```
data: {"event":"progress","data":{"message":"Running test 1/3: npm test"}}
data: {"event":"status","data":{"status":"completed","results":{...}}}
```

## Web Interface

Access the web interface at: `http://localhost:3000/runner`

The web interface provides:
- Input form for repository URL
- Real-time progress updates
- Repository metadata display
- Test results with detailed output
- Score calculation (0-100)

## Data Storage

Cloned repositories are stored in:
```
~/.local/share/oscanner/repos/{repo_name}
```

Generated REPO_OVERVIEW.md files are saved in each repository's root directory.

## Implementation Details

### Repository Cloning
- Uses `git clone --depth 1` for efficient shallow cloning
- Supports GitHub and Gitee repositories
- Extracts metadata: name, branch, latest commit

### Repository Exploration
- Analyzes repository structure and files
- Reads README, package files, and directory tree
- Uses Claude Sonnet 4.5 to generate comprehensive overview
- Includes: purpose, components, features, setup instructions

### Test Running
- Uses Claude to identify test commands from REPO_OVERVIEW.md
- Executes setup commands if needed
- Runs all identified test commands
- Calculates score based on pass/fail ratio
- Captures full test output for debugging

## Architecture

```
repos_runner/
├── server.py              # FastAPI application
├── routes/
│   └── runner.py          # API endpoints with SSE streaming
├── services/
│   └── repo_service.py    # Business logic for clone/explore/test
├── schemas/
│   └── __init__.py        # Pydantic models
├── requirements.txt       # Python dependencies
├── start_server.sh        # Startup script
└── stop_server.sh         # Shutdown script
```

## Troubleshooting

### API Key Not Found
Ensure `ANTHROPIC_API_KEY` or `OSCANNER_LLM_API_KEY` is set in your environment.

### Port Already in Use
Change the port:
```bash
export RUNNER_PORT=8002
./start_server.sh
```

### Clone Failures
- Verify repository URL format
- Check network connectivity
- Ensure sufficient disk space

### Test Execution Timeouts
Tests are limited to 5 minutes per command. For longer tests, consider adjusting the timeout in `repo_service.py`.
