## Repository Runner

This service provides automated repository cloning, exploration, and testing using opencode.

## Features

- **Clone Repository**: Shallow clone of GitHub/Gitee repositories
- **Explore & Document**: Generate REPO_OVERVIEW.md using opencode, with messages API fallback
- **Run Tests**: Automatically identify and run test suites
- **Real-time Streaming**: Progress updates via Server-Sent Events (SSE)

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Install opencode for agentic repository exploration:
```bash
npm install -g opencode-ai
```

3. Set up environment variables:
```bash
# Required: direct Anthropic API key
export ANTHROPIC_API_KEY="your-api-key"
# Or use an Anthropic-compatible gateway
export ANTHROPIC_BASE_URL="https://openrouter.ai/api"
export ANTHROPIC_AUTH_TOKEN="sk-or-v1-..."

# Optional legacy/provider shortcut: OpenRouter
export OPEN_ROUTER_KEY="sk-or-v1-..."
# Optional override (default is https://openrouter.ai/api)
export OPEN_ROUTER_BASE_URL="https://openrouter.ai/api"
# Optional model routing (recommended for Anthropic-compatible endpoint)
export OPEN_ROUTER_PRIMARY_MODEL="anthropic/claude-sonnet-4.6"
export OPEN_ROUTER_FALLBACK_MODEL="anthropic/claude-sonnet-4.6"
export OPEN_ROUTER_FALLBACK_MODELS="anthropic/claude-sonnet-4.6"
# Optional override for repos_runner task prompts (if unset, uses provider defaults above)
export REPOS_RUNNER_LLM_MODEL="claude-sonnet-4-6"
# Optional opencode model override in provider/model format
# Defaults to OpenRouter DeepSeek V4 Pro when unset
export REPOS_RUNNER_OPENCODE_MODEL="openrouter/deepseek/deepseek-v4-pro"
# Optional timeout for opencode exploration (seconds, default: 600)
export REPOS_RUNNER_OPENCODE_TIMEOUT=600
# Optional: also try direct Anthropic credential if OpenRouter attempts fail
export OPEN_ROUTER_FALLBACK_TO_ANTHROPIC=true

# Optional: Custom port (default: 8001)
export RUNNER_PORT=8001

# Optional: isolate repo setup/tests/runtime checks in Docker
# auto = use Docker when the daemon is available, host = current host sandbox,
# docker = require Docker and fail if it cannot start.
export REPOS_RUNNER_EXECUTOR=auto
export REPOS_RUNNER_DOCKER_IMAGE=oscanner-repos-runner:py3.12-node

# Optional: ask an LLM to suggest Linux/Docker-compatible startup commands
# when README instructions are inconsistent or incomplete. Suggestions are
# validated against the same safe command allowlist before execution.
export REPOS_RUNNER_RUNTIME_COMPAT_LLM=false
export REPOS_RUNNER_RUNTIME_COMPAT_MODEL="deepseek/deepseek-v4-pro"
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

### Quick Start: Run All Steps (Recommended)

**POST** `/api/runner/run-all`

This is the **simplest way** to analyze a repository. It runs all four steps (clone, explore, test) in a single API call.

**Request:**
```json
{
  "repo_url": "https://github.com/owner/repo",
  "clone_timeout": 300,
  "setup_timeout": 300,
  "test_timeout": 600,
  "pipeline_timeout": 1800
}
```

**Response:**
```json
{
  "passed": 8,
  "failed": 2,
  "total": 10,
  "score": 80,
  "repo_name": "repo",
  "report_path": "/home/user/.local/share/oscanner/repos/repo/TEST_REPORT.md"
}
```

**Error Handling:**
- Returns HTTP 503 if repos_runner service is unavailable
- Returns HTTP 500 with detailed error message if any step fails
- Includes which step failed (clone/explore/test) in error details

**Example Usage:**
```python
import requests

response = requests.post(
    "http://localhost:8000/api/runner/run-all",
    json={"repo_url": "https://gitee.com/zgcai/eval_test_1"},
    timeout=600
)

if response.status_code == 200:
    result = response.json()
    print(f"Tests: {result['passed']}/{result['total']} passed")
    print(f"Score: {result['score']}/100")
```

See [example_run_all_tests.py](../evaluator/example_run_all_tests.py) for a complete working example.

---

### Individual Steps (Advanced)

For more control or real-time progress updates, use the individual endpoints:

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

### 2. Explore Repository (SSE Streaming)

**POST** `/api/runner/explore?clone_path=/path/to/repo`

**Returns:** Server-Sent Events (SSE) stream with real-time progress updates.

**How SSE Streaming Works:**
- Connection stays open during exploration process
- Events are sent as they occur (not buffered until completion)
- Frontend receives and displays progress messages in real-time
- Each event is prefixed with `data: ` followed by JSON

**Event Format:**
```
data: {"event":"progress","data":{"message":"Starting repository exploration..."}}
data: {"event":"progress","data":{"message":"Starting repository exploration with opencode..."}}
data: {"event":"progress","data":{"message":"opencode is exploring the repository structure..."}}
data: {"event":"progress","data":{"message":"Writing REPO_OVERVIEW.md..."}}
data: {"event":"status","data":{"status":"completed","overview_path":"/path/to/REPO_OVERVIEW.md"}}
```

**Event Types:**
- `progress`: Incremental update messages during processing
- `status`: Final completion or failure event
  - `{"status": "completed", "overview_path": "..."}` - Success
  - `{"status": "failed", "error": "..."}` - Failure

### 3. Run Tests (Streaming)

**POST** `/api/runner/run-tests?clone_path=/path/to/repo&overview_path=/path/to/REPO_OVERVIEW.md`

Returns Server-Sent Events stream with test results:
```
data: {"event":"progress","data":{"message":"Running test 1/3: npm test"}}
data: {"event":"status","data":{"status":"completed","results":{...},"report_path":"/path/to/TEST_REPORT.md"}}
```

Automatically generates `TEST_REPORT.md` in the repository directory with:
- Summary (total, passed, failed, score)
- Code test results from executed unit/integration/test commands
- Functionality test results from tag-derived feature coverage and runtime evidence
- Score breakdown and recommendations

When a tag is provided, the report file is named `TEST_REPORT_{tag}.md`.

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
- Uses opencode to generate a concise test-focused overview
- Includes: purpose, components, features, setup instructions

### Test Running
- Uses static detection first, then configured messages API fallback to identify test commands from REPO_OVERVIEW.md
- Creates isolated virtual environment per repository at `{repo_path}/.venv`
- Executes setup commands if needed (installs dependencies in repo's venv)
- Runs all identified test commands in isolated environment
- Calculates score from relevance-gated code tests and functional acceptance when tag requirements are available
- Captures full test output for debugging
- Each repository has its own dependency isolation
- Generates TEST_REPORT.md in each repository directory

### Runtime Evidence From README

When tag requirements are available, repos_runner also reads `README.md`, `README.en.md`,
`AGENT.md`, `AGENTS.md`, and up to 20 Markdown files under `docs/` to collect runtime
evidence. It tracks simple `cd <relative-dir>` lines inside shell blocks and starts
safe local services that match one of these patterns:

- `python scripts/dev-*.py`
- `python scripts/start.py start`
- `python scripts/check.py`
- `python scripts/tasks.py check`
- `uvicorn <module>:<app> --port <probed-port>`
- `python -m uvicorn <module>:<app> --port <probed-port>`
- `npm run dev`

For `uvicorn` and `npm run dev`, the runner normalizes host binding to
`127.0.0.1` so checks can probe local ports inside the execution session.
When README instructions contain Windows virtualenv activation such as
`.venv\Scripts\activate`, the runner converts the service startup to the Linux/Docker
equivalent (`. .venv/bin/activate`) and prefixes the command with documented
`python -m venv` / `pip install -r ...` setup where safe.
Arbitrary README shell commands are not executed.

When the Docker executor is used, the runner image includes Chromium and CJK
fonts. Runtime evidence uses that browser to capture screenshots and rendered DOM
for UI checks such as homepage loading and scene placeholder text. These UI
checks are evidence for functional acceptance; they are not a third scoring
bucket.

If `REPOS_RUNNER_RUNTIME_COMPAT_LLM=true`, repos_runner asks the configured
compatibility model, default `deepseek/deepseek-v4-pro`, to suggest missing
Linux/Docker-compatible startup commands from README-like files and repository
paths. The model output is treated as untrusted: only JSON suggestions that
normalize back into the allowlisted command families above are executed.

### Feature Directory Checks

Directory checks are performed against the cloned Git tree. Git does not preserve
empty directories, so required directories such as `.harness/datasets/`,
`.harness/eval/`, and `.harness/logs/` need a committed placeholder file such as
`.gitkeep` to exist after clone.

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

### Manual SSE Streaming Test

To verify SSE streaming is working correctly:

```bash
# Ensure the server is running
./start_server.sh

# In another terminal, run the test script
python test_sse_streaming.py
```

This script will:
1. Clone a test repository via `/api/runner/clone`
2. Test SSE streaming for `/api/runner/explore`
3. Display all progress events as they arrive in real-time
4. Report timing and event statistics

**Expected output:**
```
📡 Receiving SSE stream (events shown as they arrive):

[0.45s] 📝 Progress: Starting repository exploration...
[0.67s] 📝 Progress: Starting repository exploration with opencode...
[0.89s] 📝 Progress: opencode is exploring the repository structure...
[2.34s] 📝 Progress: Writing REPO_OVERVIEW.md...
[2.45s] ✅ Completed!

✅ SSE streaming is working correctly!
   Multiple progress events were received in real-time.
```

### Test Scoring Methodology

Tests are scored based on the following metrics:

- **Without tag requirements**: score is the code test pass rate, `(Passed / Total) × 100`.
- **With tag requirements**: score is split into two dynamic parts:
  - **Code tests: 30-40%** — unit/integration/test commands, gated by how much the tests relate to required features.
  - **Functional acceptance: 60-70%** — required feature coverage from static checks, service/API runtime evidence, and UI evidence.
- **Formula with tag requirements**:
  `final_score = code_pass_rate × code_relevance_ratio × code_weight + functionality_coverage_ratio × functionality_weight`.

The dynamic distribution starts at `code_weight=30` and `functionality_weight=70`
when no relevant code tests are found. As code tests cover more required features,
`code_weight` rises toward 40 and `functionality_weight` falls toward 60. This
avoids both old all-or-nothing scoring and the opposite problem where unrelated
passing tests make a missing feature set look healthy.

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
Ensure `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_API_KEY`, or `OPEN_ROUTER_KEY` is set in your environment.

### Port Already in Use
Change the port:
```bash
export RUNNER_PORT=8002
./start_server.sh
```

To avoid conflicts between your local apps and repositories under test, run repo
setup, tests, and runtime checks in Docker:
```bash
export REPOS_RUNNER_EXECUTOR=docker
./start_server.sh
```

The cloned repo is mounted at `/workspace` inside a disposable container, so
`TEST_REPORT_{tag}.md`, `.test_report.json`, `test_config.json`, and
`TEST_ARTIFACTS_{tag}/` remain saved in the repo directory on the host. Student
services can bind ports such as `8000` inside the container without occupying
host ports.

### Clone Failures
- Verify repository URL format
- Check network connectivity
- Ensure sufficient disk space

### Runner Timeouts
`run-all` accepts timeout fields to keep stuck repositories from occupying the runner indefinitely:

- `clone_timeout`: seconds allowed per git clone/checkout operation, default `300`.
- `setup_timeout`: seconds allowed per dependency/setup command, default `300`.
- `test_timeout`: seconds allowed per test command, default `600`.
- `pipeline_timeout`: seconds allowed for the whole active clone/explore/test pipeline, default `1800`.
