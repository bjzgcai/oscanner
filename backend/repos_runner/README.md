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
data: {"event":"status","data":{"status":"completed","results":{...},"report_path":"/path/to/TEST_REPORT.md"}}
```

Automatically generates `TEST_REPORT.md` in the repository directory with:
- Summary (total, passed, failed, score)
- Detailed test results (pass/fail status, duration, output)
- Score breakdown and recommendations

## Web Interface

Access the web interface at: `http://localhost:3000/runner`

The web interface provides:
- Input form for repository URL
- Real-time progress updates
- Repository metadata display
- Test results with detailed output
- Score calculation (0-100)

## Data Storage

Cloned repositories and test environments are stored in:
```
~/.local/share/oscanner/repos/
├── repo1/                        # Analyzed repository
│   ├── REPO_OVERVIEW.md         # Generated documentation
│   ├── TEST_REPORT.md           # Test results and metrics
│   ├── .venv/                   # Dedicated virtual environment
│   │   ├── bin/python          # Isolated Python interpreter
│   │   └── lib/python3.x/      # Repository-specific packages
│   └── ... (repository files)
├── repo2/                        # Another repository
│   ├── REPO_OVERVIEW.md
│   ├── TEST_REPORT.md
│   ├── .venv/                   # Separate environment
│   └── ...
└── .pip_cache/                  # Shared package cache (optional)
```

This isolated structure ensures:
- Your main codebase stays clean
- Test dependencies don't pollute project dependencies
- **Each repository has its own isolated virtual environment**
- **Dependency conflicts are prevented** (repo A's packages won't affect repo B)
- **Python version flexibility** (different repos can use different Python versions)
- **Security isolation** (potentially malicious packages are contained)
- Each repository has its own test report
- Easy cleanup (just delete `~/.local/share/oscanner/repos/`)

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
- Creates isolated virtual environment per repository at `{repo_path}/.venv`
- Executes setup commands if needed (installs dependencies in repo's venv)
- Runs all identified test commands in isolated environment
- Calculates score based on pass/fail ratio
- Captures full test output for debugging
- Each repository has its own dependency isolation
- Generates TEST_REPORT.md in each repository directory

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

## Testing

### Testing Metrics

The repos_runner service can be tested using the following approach.

**Important**: See [TESTING_SUMMARY.md](TESTING_SUMMARY.md) for complete testing documentation structure.

**Current Test Status (repos_runner service):**
- Total Tests: 0 (no tests implemented yet)
- Passed: 0
- Failed: 0
- Coverage: 0%
- Test Score: 0/100

See [REPOS_RUNNER_TEST_REPORT.md](REPOS_RUNNER_TEST_REPORT.md) for detailed test plan.

**For Analyzed Repositories:**
- Test reports auto-generated at `~/.local/share/oscanner/repos/{repo_name}/TEST_REPORT.md`
- See [TEST_REPORT_EXAMPLE.md](TEST_REPORT_EXAMPLE.md) for sample output

**Testing Focus Areas:**

1. **Service Layer Tests** ([repo_service.py](repos_runner/services/repo_service.py))
   - URL parsing: GitHub/Gitee formats
   - Repository cloning: shallow clone verification
   - Context building: README extraction, directory tree
   - Test identification: Claude-based command extraction
   - Score calculation: pass/fail ratio accuracy

2. **API Endpoint Tests** ([runner.py](repos_runner/routes/runner.py))
   - `/api/runner/clone`: Valid/invalid URLs
   - `/api/runner/explore`: SSE streaming
   - `/api/runner/run-tests`: Test execution flow

3. **Integration Tests**
   - End-to-end: Clone → Explore → Test
   - Real repository testing
   - Error handling scenarios

### Running Tests

Once tests are implemented, run them with:

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest repos_runner/tests/ -v

# Run with coverage
pytest repos_runner/tests/ --cov=repos_runner --cov-report=term-missing

# Run specific test file
pytest repos_runner/tests/test_repo_service.py -v
```

### Test Scoring Methodology

Tests are scored based on the following metrics:

- **Pass Rate**: (Passed / Total) × 100
- **Coverage**: Percentage of code covered by tests
- **Critical Path**: Clone, explore, and test execution paths must pass
- **Error Handling**: Graceful handling of network failures, invalid inputs

**Grade Scale:**
- 90-100: Excellent (all critical paths covered)
- 70-89: Good (most functionality tested)
- 50-69: Fair (basic tests only)
- 0-49: Poor (insufficient testing)

### Automated Test Exploration

Use the `/test-explore` Claude Code skill to automatically:
1. Explore the codebase structure
2. Plan a comprehensive test suite
3. Run tests and calculate scores
4. Generate test coverage reports

```bash
# Usage in Claude Code CLI
/test-explore
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
