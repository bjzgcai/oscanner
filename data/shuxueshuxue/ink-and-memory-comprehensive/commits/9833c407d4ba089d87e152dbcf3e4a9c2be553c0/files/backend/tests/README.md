# Test Suite

## Overview

Organized test suite for the Ink & Memory backend deck system.

## Test Structure

```
tests/
├── __init__.py                 # Test package init
├── test_database.py           # Database layer tests (CRUD operations)
└── test_api_endpoints.py      # API integration tests (HTTP endpoints)
```

## Running Tests

### Run All Tests
```bash
cd backend
chmod +x run_tests.sh
./run_tests.sh
```

### Run Individual Tests

**Database Layer Only:**
```bash
source .venv/bin/activate
python tests/test_database.py
```

**API Endpoints Only** (requires server running):
```bash
# Terminal 1: Start server
source .venv/bin/activate
python server.py

# Terminal 2: Run tests
source .venv/bin/activate
python tests/test_api_endpoints.py
```

## Test Coverage

### Database Layer (`test_database.py`)
- ✅ Get system decks
- ✅ Get deck with voices
- ✅ Fork deck (system → user)
- ✅ Update deck (user-owned)
- ✅ Create voice in user deck
- ✅ Update voice (user-owned)
- ✅ Fork voice to user deck
- ✅ Delete voice (user-owned)
- ✅ Delete deck with cascade (user-owned)

### API Endpoints (`test_api_endpoints.py`)
- ✅ Authentication (register/login)
- ✅ GET /api/decks (list all)
- ✅ GET /api/decks/{id} (get with voices)
- ✅ POST /api/decks/{id}/fork (fork deck)
- ✅ PUT /api/decks/{id} (update deck)
- ✅ DELETE /api/decks/{id} (delete deck)
- ✅ POST /api/voices (create voice)
- ✅ PUT /api/voices/{id} (update voice)
- ✅ DELETE /api/voices/{id} (delete voice)
- ✅ POST /api/voices/{id}/fork (fork voice)
- ✅ Permission checks (401/404 for unauthorized)

## Requirements

- Python virtual environment with dependencies
- SQLite database (auto-created if missing)
- Port 8765 available for test server

## Troubleshooting

**"Server failed to start"**
- Check if port 8765 is already in use: `lsof -i:8765`
- Kill existing process: `lsof -ti:8765 | xargs kill -9`
- Check `models.json` exists in backend directory

**"Database tests failed"**
- Ensure database is properly initialized: `python database.py`
- Check database file permissions

**"API tests return 502"**
- Server may have crashed - check `/tmp/test_server.log`
- Verify PolyCLI is installed: `pip show polycli`
