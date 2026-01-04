# Ink & Memory API Documentation

**Version:** 2.0.0
**Base URL:** `http://localhost:8765` (dev) | `https://lexicalmathical.com/ink-and-memory` (prod)

## Authentication

All endpoints except `/api/register`, `/api/login`, and `/api/default-voices` require authentication.

**Header:** `Authorization: Bearer <JWT_TOKEN>`

JWT tokens expire after 7 days.

---

## Auth Endpoints

### POST `/api/register`

Register a new user.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "password123",
  "display_name": "Optional Name"
}
```

**Response:**
```json
{
  "token": "eyJhbGciOiJIUzI1...",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "display_name": "Optional Name"
  }
}
```

**Errors:**
- `400` - Email/password missing or password < 6 chars
- `400` - Email already exists

---

### POST `/api/login`

Login with email and password.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response:**
```json
{
  "token": "eyJhbGciOiJIUzI1...",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "display_name": "Optional Name"
  }
}
```

**Errors:**
- `401` - Invalid email or password

---

### GET `/api/me`

Get current user info from token.

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "id": 1,
  "email": "user@example.com",
  "display_name": "Optional Name",
  "created_at": "2025-11-02 05:20:53"
}
```

**Errors:**
- `401` - Missing or invalid token
- `404` - User not found

---

## Migration Endpoint

### POST `/api/import-local-data`

One-time import of localStorage data to database on first login.

**Headers:** `Authorization: Bearer <token>`

**Request:**
```json
{
  "currentSession": "{\"cells\": [...]}",
  "calendarEntries": "{\"2025-11-01\": [...]}",
  "dailyPictures": "[{\"date\": \"2025-11-01\", \"base64\": \"...\"}]",
  "voiceCustomizations": "{\"Logic\": {...}}",
  "metaPrompt": "Be helpful",
  "stateConfig": "{\"states\": {...}}",
  "selectedState": "happy",
  "analysisReports": "[{\"type\": \"echoes\", \"data\": {...}}]",
  "oldDocument": "{\"document\": \"...\"}"
}
```

All fields are optional. Strings should be JSON-stringified.

**Response:**
```json
{
  "success": true,
  "imported": {
    "sessions": 6,
    "pictures": 2,
    "preferences": 4,
    "reports": 3
  }
}
```

**Errors:**
- `401` - Missing or invalid token

---

## Session Storage

### POST `/api/sessions`

Save or update a session.

**Headers:** `Authorization: Bearer <token>`

**Request:**
```json
{
  "session_id": "my-session-123",
  "name": "My Session Name",
  "editor_state": {
    "cells": [
      {"type": "text", "content": "Hello world"}
    ],
    "commentors": []
  }
}
```

**Response:**
```json
{
  "success": true
}
```

---

### GET `/api/sessions`

List all sessions for current user (metadata only, no editor_state).

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "sessions": [
    {
      "id": "session-123",
      "name": "My Session",
      "created_at": "2025-11-02 05:22:41",
      "updated_at": "2025-11-02 05:22:41"
    }
  ]
}
```

---

### GET `/api/sessions/{session_id}`

Get a specific session including full editor_state.

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "id": "session-123",
  "name": "My Session",
  "created_at": "2025-11-02 05:22:41",
  "updated_at": "2025-11-02 05:22:41",
  "editor_state": {
    "cells": [...],
    "commentors": []
  }
}
```

**Errors:**
- `404` - Session not found

---

### DELETE `/api/sessions/{session_id}`

Delete a session.

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "success": true
}
```

---

## Pictures

### GET `/api/pictures`

Get recent daily pictures.

**Headers:** `Authorization: Bearer <token>`

**Query params:**
- `limit` (optional, default 30) - Max number of pictures

**Response:**
```json
{
  "pictures": [
    {
      "date": "2025-11-02",
      "image_base64": "iVBORw0KGgoAAAANSUhEUg...",
      "prompt": "A serene landscape...",
      "created_at": "2025-11-02 05:22:41"
    }
  ]
}
```

---

### POST `/api/pictures`

Save a daily picture.

**Headers:** `Authorization: Bearer <token>`

**Request:**
```json
{
  "date": "2025-11-02",
  "image_base64": "iVBORw0KGgoAAAANSUhEUg...",
  "prompt": "A serene landscape..."
}
```

**Response:**
```json
{
  "success": true
}
```

**Errors:**
- `400` - date or image_base64 missing

---

## Preferences

### GET `/api/preferences`

Get user preferences.

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "voice_configs": {
    "Logic": {
      "name": "Logic",
      "tagline": "...",
      "icon": "brain",
      "color": "blue",
      "enabled": true
    }
  },
  "meta_prompt": "Be helpful",
  "state_config": {
    "states": {
      "happy": {"name": "Happy", "prompt": "..."}
    }
  },
  "selected_state": "happy",
  "updated_at": "2025-11-02 05:22:41"
}
```

Returns empty object `{}` if no preferences set.

---

### POST `/api/preferences`

Save user preferences (partial updates supported).

**Headers:** `Authorization: Bearer <token>`

**Request (any combination of fields):**
```json
{
  "voice_configs": {...},
  "meta_prompt": "Be creative",
  "state_config": {...},
  "selected_state": "happy"
}
```

**Response:**
```json
{
  "success": true
}
```

---

## Analysis Reports

### GET `/api/reports`

Get recent analysis reports.

**Headers:** `Authorization: Bearer <token>`

**Query params:**
- `limit` (optional, default 10) - Max number of reports

**Response:**
```json
{
  "reports": [
    {
      "id": 1,
      "report_type": "echoes",
      "report_data": {
        "echoes": [...]
      },
      "created_at": "2025-11-02 05:22:41"
    }
  ]
}
```

---

### POST `/api/reports`

Save an analysis report.

**Headers:** `Authorization: Bearer <token>`

**Request:**
```json
{
  "report_type": "echoes",
  "report_data": {
    "echoes": [
      {"title": "...", "description": "...", "examples": [...]}
    ]
  },
  "all_notes_text": "All the user's notes combined..."
}
```

**Response:**
```json
{
  "success": true
}
```

**Errors:**
- `400` - report_type or report_data missing

---

## Voice Analysis (PolyCLI)

### POST `/api/analyze`

Analyze text and return ONE new voice comment (sync API).

**Request:**
```json
{
  "text": "User's text to analyze",
  "session_id": "session-123",
  "voices": {...},
  "applied_comments": [],
  "meta_prompt": "",
  "state_prompt": "",
  "overlapped_phrases": []
}
```

**Response:**
```json
{
  "success": true,
  "result": {
    "voices": [
      {
        "phrase": "exact phrase",
        "voice": "Logic",
        "comment": "What the voice says",
        "icon": "brain",
        "color": "blue"
      }
    ],
    "new_voices_added": 1
  }
}
```

---

### POST `/api/chat`

Chat with a voice persona (sync API).

**Request:**
```json
{
  "voice_name": "Logic",
  "voice_config": {...},
  "conversation_history": [
    {"role": "user", "content": "Hi"},
    {"role": "assistant", "content": "Hello"}
  ],
  "user_message": "What do you think?",
  "original_text": "User's writing context",
  "meta_prompt": "",
  "state_prompt": ""
}
```

**Response:**
```json
{
  "success": true,
  "result": {
    "response": "Voice's response to the user"
  }
}
```

---

### POST `/api/generate-image`

Generate artistic image from notes (sync API, 60s timeout).

**Request:**
```json
{
  "all_notes": "All user's notes combined..."
}
```

**Response:**
```json
{
  "success": true,
  "result": {
    "image_base64": "iVBORw0KGgoAAAANSUhEUg...",
    "prompt": "Creative image description"
  }
}
```

---

### POST `/api/analyze-echoes`

Find recurring themes in notes (sync API).

**Request:**
```json
{
  "all_notes": "All user's notes combined..."
}
```

**Response:**
```json
{
  "success": true,
  "result": {
    "echoes": [
      {
        "title": "Theme title",
        "description": "Pattern description",
        "examples": ["quote1", "quote2"]
      }
    ]
  }
}
```

---

### POST `/api/analyze-traits`

Identify personality traits from notes (sync API).

**Request:**
```json
{
  "all_notes": "All user's notes combined..."
}
```

**Response:**
```json
{
  "success": true,
  "result": {
    "traits": [
      {
        "trait": "Curious",
        "strength": 4,
        "evidence": "Examples from text..."
      }
    ]
  }
}
```

---

### POST `/api/analyze-patterns`

Identify behavioral patterns from notes (sync API).

**Request:**
```json
{
  "all_notes": "All user's notes combined..."
}
```

**Response:**
```json
{
  "success": true,
  "result": {
    "patterns": [
      {
        "pattern": "Pattern name",
        "description": "Pattern description",
        "frequency": "Often/Sometimes/Rarely"
      }
    ]
  }
}
```

---

### GET `/api/default-voices`

Get default voice configurations (no auth required).

**Response:**
```json
{
  "Logic": {
    "tagline": "Wield raw intellectual power...",
    "icon": "brain",
    "color": "blue"
  },
  "Rhetoric": {...},
  ...
}
```

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message"
}
```

Common status codes:
- `400` - Bad request (missing/invalid params)
- `401` - Unauthorized (missing/invalid token)
- `404` - Not found
- `500` - Internal server error

---

## Development

**Start server:**
```bash
cd backend
source .venv/bin/activate
python server.py
```

**Run tests:**
```bash
python test_migration.py           # Test migration logic
python test_real_migration.py      # Test with real data
```

**API Docs:**
- Interactive docs: http://localhost:8765/docs
- PolyCLI control panel: http://localhost:8765/polycli

---

## Database

SQLite database at `backend/data/ink-and-memory.db`

**Initialize/reset:**
```python
from database import init_db
init_db()
```

**Tables:**
- `users` - User accounts
- `user_sessions` - Editor sessions
- `daily_pictures` - Generated images
- `user_preferences` - User settings
- `analysis_reports` - Analysis results
- `auth_sessions` - Session tokens (optional)
- `schema_version` - Migration tracking
