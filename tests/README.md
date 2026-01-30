# Tests

This directory contains test cases for the oscanner project.

## Structure

- `gitee_api/` - Tests for Gitee API extraction and DNS handling

## Running Tests

### Install Dependencies

**Important**: You must install the project dependencies before running tests.

#### Using uv (Recommended)

If you're using `uv` to manage dependencies (as indicated by `uv.lock` file), you should use `uv run` to run pytest:

```bash
# Install project in editable mode with dev dependencies
uv pip install -e ".[dev]"

# Run tests using uv run (this ensures the correct virtual environment is used)
uv run pytest tests/gitee_api/test_extraction.py -v

# Or run all tests
uv run pytest -v
```

**Why use `uv run`?**
- `uv run` automatically uses the virtual environment managed by uv
- Direct `pytest` command may use a different Python environment (system Python or conda base)
- This ensures the same environment as `uv run oscanner dev` is used

#### Using pip/virtualenv

If you're using traditional pip/virtualenv:

```bash
# Activate your virtual environment first
source .venv/bin/activate  # or your venv path

# Install project in editable mode with dev dependencies
pip install -e ".[dev]"

# Then run tests
pytest tests/gitee_api/test_extraction.py -v
```

**Note**: The tests import `evaluator.services.extraction_service` which requires `fastapi` and other dependencies. Make sure all dependencies are installed in the same environment.

### Run All Tests

```bash
# Using uv (recommended if using uv for dependency management)
uv run pytest

# Or with traditional pip/virtualenv (after activating venv)
pytest
```

### Run Specific Test File

```bash
uv run pytest tests/gitee_api/test_extraction.py
# or
pytest tests/gitee_api/test_extraction.py  # if venv is activated
```

### Run Specific Test Class

```bash
uv run pytest tests/gitee_api/test_extraction.py::TestDNSResolution
```

### Run Specific Test

```bash
uv run pytest tests/gitee_api/test_extraction.py::TestDNSResolution::test_dns_resolution_success
```

### Run with Verbose Output

```bash
uv run pytest -v
```

### Run with Coverage

```bash
uv run pytest --cov=evaluator --cov-report=html
```

## Test Coverage

The `gitee_api/test_extraction.py` file tests:

1. **DNS Resolution** (`TestDNSResolution`)
   - Successful DNS resolution
   - DNS resolution failure
   - DNS hijacking detection (baiduads.com)
   - Normal DNS resolution without hijacking

2. **Gitee Extraction** (`TestGiteeExtraction`)
   - DNS failure handling
   - DNS hijacking detection
   - Ad server response detection
   - Network error handling
   - Timeout error handling
   - API error handling (non-200 status codes)
   - Verification that Gitee API host gitee.com is used (API rejects www.gitee.com with 403 Invalid Hostname)

## Notes

- Tests use mocking to avoid actual network calls
- Tests verify error messages and exception handling
