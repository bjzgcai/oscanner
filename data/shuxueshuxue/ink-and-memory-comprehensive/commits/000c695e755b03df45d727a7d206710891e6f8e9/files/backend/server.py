#!/usr/bin/env python3
"""FastAPI-based voice analysis server with sync API support."""

import httpx
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from polycli.orchestration.session_registry import session_def, get_registry
from polycli.integrations.fastapi import mount_control_panel
from polycli import PolyAgent
from stateless_analyzer import analyze_stateless
import config
from proxy_config import get_image_api_proxies
from typing import Optional
from pydantic import BaseModel

# Import database and auth modules
import database
import auth

# ========== Session Definitions (PolyCLI) ==========

@session_def(
    name="Chat with Voice",
    description="Have a conversation with a specific inner voice persona",
    params={
        "voice_name": {"type": "str"},
        "voice_config": {"type": "dict"},
        "conversation_history": {"type": "list"},
        "user_message": {"type": "str"},
        "original_text": {"type": "str"},
        "meta_prompt": {"type": "str"},
        "state_prompt": {"type": "str"}
    },
    category="Chat"
)
def chat_with_voice(voice_name: str, voice_config: dict, conversation_history: list, user_message: str, original_text: str = "", meta_prompt: str = "", state_prompt: str = ""):
    """Chat with a specific voice persona."""
    print(f"\n{'='*60}")
    print(f"💬 chat_with_voice() called")
    print(f"   Voice: {voice_name}")
    print(f"   User message: {user_message}")
    print(f"   History length: {len(conversation_history)}")
    print(f"   Meta prompt: {repr(meta_prompt)[:100]}")
    print(f"   State prompt: {repr(state_prompt)[:100]}")
    print(f"{'='*60}\n")

    agent = PolyAgent(id=f"voice-chat-{voice_name.lower()}")

    # Ensure voice_config is a dict
    if not isinstance(voice_config, dict):
        print(f"⚠️  voice_config is not a dict: {type(voice_config)}, using default")
        voice_config = {"tagline": f"{voice_name} voice from Disco Elysium"}

    # Build system prompt for this voice
    system_prompt = f"""You are {voice_name}, an inner voice archetype from Disco Elysium.

Your character: {voice_config.get('tagline', '')}

Respond in character as {voice_name}. Be concise (1-3 sentences). Stay true to your archetype.
Use the conversation context but focus on your unique perspective."""

    # Add original writing area text if available
    if original_text and original_text.strip():
        system_prompt += f"""

Context: The user is writing this text:
---
{original_text.strip()}
---

Your initial comment was about this text. Keep this context in mind when responding to the user's questions."""

    # Add meta prompt if available
    if meta_prompt and meta_prompt.strip():
        system_prompt += f"""

Additional instructions:
{meta_prompt.strip()}"""

    # Add state prompt if available
    if state_prompt and state_prompt.strip():
        system_prompt += f"""

User's current state:
{state_prompt.strip()}"""

    # Build full prompt with conversation history
    prompt = system_prompt + "\n\nConversation history:\n"

    # Add conversation history
    for msg in conversation_history:
        role_label = "User" if msg["role"] == "user" else voice_name
        prompt += f"\n{role_label}: {msg['content']}"

    # Add user's new message
    prompt += f"\n\nUser: {user_message}\n\n{voice_name}:"

    # Get response from LLM
    result = agent.run(prompt, model="gpt-4o-dou", cli="no-tools", tracked=True)

    if not result.is_success or not result.content:
        response = "..."
    else:
        response = result.content

    print(f"✅ Got response: {response[:100]}...")

    return {
        "response": response,
        "voice_name": voice_name
    }

@session_def(
    name="Analyze Voices",
    description="Get one new voice comment for text",
    params={
        "text": {"type": "str"},
        "session_id": {"type": "str"},
        "voices": {"type": "dict"},
        "applied_comments": {"type": "list"},
        "meta_prompt": {"type": "str"},
        "state_prompt": {"type": "str"}
    },
    category="Analysis"
)
def analyze_text(text: str, session_id: str, voices: dict = None, applied_comments: list = None, meta_prompt: str = "", state_prompt: str = "", overlapped_phrases: list = None):
    """Stateless analysis - returns ONE new comment based on text and applied comments."""
    print(f"\n{'='*60}")
    print(f"🎯 Stateless analyze_text() called")
    print(f"   Text: {text[:100]}...")
    print(f"   Applied comments: {len(applied_comments or [])}")
    print(f"   Overlapped phrases: {len(overlapped_phrases or [])}")
    print(f"   Meta prompt: {repr(meta_prompt)[:100]}")
    print(f"   State prompt: {repr(state_prompt)[:100]}")
    print(f"{'='*60}\n")

    agent = PolyAgent(id="voice-analyzer")

    # Get voices from stateless analyzer
    result = analyze_stateless(agent, text, applied_comments or [], voices, meta_prompt, state_prompt, overlapped_phrases or [])

    print(f"✅ Returning {result['new_voices_added']} new voice(s)")

    return {
        "voices": result["voices"],
        "new_voices_added": result["new_voices_added"],
        "status": "completed"
    }

@session_def(
    name="Analyze Echoes",
    description="Find recurring themes and topics in all user notes",
    params={
        "all_notes": {"type": "str"}
    },
    category="Analysis"
)
def analyze_echoes(all_notes: str):
    """Analyze recurring themes and topics across all notes."""
    print(f"\n{'='*60}")
    print(f"🔄 analyze_echoes() called")
    print(f"   Notes length: {len(all_notes)} chars")
    print(f"{'='*60}\n")

    agent = PolyAgent(id="echoes-analyzer")

    prompt = f"""Analyze these personal notes and identify recurring themes, topics, or concerns that keep appearing.

Notes:
---
{all_notes}
---

Find 3-5 echoes (recurring themes) that appear across different entries. For each echo:
- Give it a short title (2-4 words)
- Explain what pattern you see
- Quote 2-3 specific examples from the notes

Format as a JSON array:
[
  {{"title": "...", "description": "...", "examples": ["quote1", "quote2", "quote3"]}},
  ...
]

Return ONLY the JSON array, no other text."""

    result = agent.run(prompt, model="gpt-4o-dou", cli="no-tools", tracked=True)

    if not result.is_success or not result.content:
        return {"echoes": []}

    try:
        import json
        echoes = json.loads(result.content.strip())
        return {"echoes": echoes}
    except:
        return {"echoes": []}

@session_def(
    name="Analyze Traits",
    description="Identify personality traits and characteristics from user notes",
    params={
        "all_notes": {"type": "str"}
    },
    category="Analysis"
)
def analyze_traits(all_notes: str):
    """Analyze personality traits from all notes."""
    print(f"\n{'='*60}")
    print(f"👤 analyze_traits() called")
    print(f"   Notes length: {len(all_notes)} chars")
    print(f"{'='*60}\n")

    agent = PolyAgent(id="traits-analyzer")

    prompt = f"""Analyze these personal notes and identify personality traits and characteristics.

Notes:
---
{all_notes}
---

Identify 4-6 personality traits that are evident from the writing. For each trait:
- Give it a name (1-2 words)
- Rate the strength (1-5)
- Explain why you see this trait with specific examples

Format as a JSON array:
[
  {{"trait": "...", "strength": 4, "evidence": "..."}},
  ...
]

Return ONLY the JSON array, no other text."""

    result = agent.run(prompt, model="gpt-4o-dou", cli="no-tools", tracked=True)

    if not result.is_success or not result.content:
        return {"traits": []}

    try:
        import json
        traits = json.loads(result.content.strip())
        return {"traits": traits}
    except:
        return {"traits": []}

@session_def(
    name="Analyze Patterns",
    description="Identify behavioral patterns and habits from user notes",
    params={
        "all_notes": {"type": "str"}
    },
    category="Analysis"
)
def analyze_patterns(all_notes: str):
    """Analyze behavioral patterns from all notes."""
    print(f"\n{'='*60}")
    print(f"🔍 analyze_patterns() called")
    print(f"   Notes length: {len(all_notes)} chars")
    print(f"{'='*60}\n")

    agent = PolyAgent(id="patterns-analyzer")

    prompt = f"""Analyze these personal notes and identify behavioral patterns or habits.

Notes:
---
{all_notes}
---

Identify 3-5 behavioral patterns or habits. For each pattern:
- Give it a descriptive name
- Describe the pattern
- Note the frequency/context when it appears

Format as a JSON array:
[
  {{"pattern": "...", "description": "...", "frequency": "..."}},
  ...
]

Return ONLY the JSON array, no other text."""

    result = agent.run(prompt, model="gpt-4o-dou", cli="no-tools", tracked=True)

    if not result.is_success or not result.content:
        return {"patterns": []}

    try:
        import json
        patterns = json.loads(result.content.strip())
        return {"patterns": patterns}
    except:
        return {"patterns": []}

@session_def(
    name="Generate Daily Picture",
    description="Generate an artistic image based on user's daily notes",
    params={
        "all_notes": {"type": "str"}
    },
    category="Creative"
)
def generate_daily_picture(all_notes: str):
    """Generate an image based on the essence of user's daily notes."""
    print(f"\n{'='*60}")
    print(f"🎨 generate_daily_picture() called")
    print(f"   Notes length: {len(all_notes)} chars")
    print(f"{'='*60}\n")

    import requests

    # Step 1: Convert notes to artistic image description using Claude Haiku
    description_prompt = f"""Read these personal notes and create a vivid, artistic image description that captures the essence, mood, and themes.

Notes:
---
{all_notes}
---

Create a detailed image description (2-3 sentences) that:
- Captures the emotional tone and atmosphere
- Uses visual metaphors for abstract concepts
- Specifies artistic style (e.g., watercolor, impressionist, minimalist)
- Describes colors, lighting, composition

Be creative and interpretive. Focus on mood and feeling, not literal representation.

Return ONLY the image description, no other text."""

    print("🧠 Creating image description from notes with Claude Haiku...")

    # Use proxy for GFW bypass (if configured)
    proxies = get_image_api_proxies()

    claude_response = requests.post(
        f"{config.IMAGE_API_ENDPOINT}/chat/completions",
        headers={
            "Authorization": f"Bearer {config.IMAGE_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": config.IMAGE_DESCRIPTION_MODEL,
            "messages": [{"role": "user", "content": description_prompt}],
            "max_tokens": config.IMAGE_DESCRIPTION_MAX_TOKENS
        },
        proxies=proxies,
        timeout=config.IMAGE_DESCRIPTION_TIMEOUT
    )

    if claude_response.status_code != 200:
        return {"image_base64": None, "error": "Failed to create image description"}

    claude_data = claude_response.json()
    image_description = claude_data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()

    if not image_description:
        return {"image_base64": None, "error": "Failed to create image description"}

    print(f"📝 Image description: {image_description}")

    # Step 2: Generate image from description with retry logic
    url = f"{config.IMAGE_API_ENDPOINT}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.IMAGE_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": config.IMAGE_GENERATION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": image_description
            }
        ],
        "max_tokens": config.IMAGE_MAX_TOKENS
    }

    # Retry logic with increasing timeouts
    for attempt in range(1, config.IMAGE_RETRY_MAX_ATTEMPTS + 1):
        try:
            timeout_seconds = config.IMAGE_RETRY_BASE_TIMEOUT + (attempt - 1) * config.IMAGE_RETRY_TIMEOUT_INCREMENT
            print(f"🎨 Generating image (attempt {attempt}/{config.IMAGE_RETRY_MAX_ATTEMPTS}, timeout={timeout_seconds}s)...")
            response = requests.post(url, headers=headers, json=payload, proxies=proxies, timeout=timeout_seconds)

            if response.status_code != 200:
                print(f"❌ Error: {response.status_code}")
                if attempt < config.IMAGE_RETRY_MAX_ATTEMPTS:
                    print(f"⏳ Retrying in 2 seconds...")
                    import time
                    time.sleep(2)
                    continue
                return {"image_base64": None, "error": "Image generation failed"}

            data = response.json()

            # Extract image from response
            if 'choices' in data and len(data['choices']) > 0:
                message = data['choices'][0].get('message', {})
                images = message.get('images', [])

                if images:
                    image_data = images[0].get('image_url', {}).get('url', '')

                    if image_data.startswith('data:image/png;base64,'):
                        # Extract base64 data (without the data URI prefix)
                        base64_data = image_data.split(',', 1)[1]

                        print(f"✅ Image generated successfully")
                        print(f"   Size: {len(base64_data)} chars")

                        return {
                            "image_base64": base64_data,
                            "prompt": image_description  # Return the creative description
                        }

            if attempt < config.IMAGE_RETRY_MAX_ATTEMPTS:
                print(f"⚠️ No image in response, retrying...")
                import time
                time.sleep(2)
                continue
            return {"image_base64": None, "error": "No image in response"}

        except Exception as e:
            print(f"❌ Exception on attempt {attempt}: {e}")
            if attempt < config.IMAGE_RETRY_MAX_ATTEMPTS:
                print(f"⏳ Retrying in 2 seconds...")
                import time
                time.sleep(2)
                continue
            return {"image_base64": None, "error": str(e)}

    return {"image_base64": None, "error": "All retry attempts failed"}

# ========== FastAPI Application ==========

app = FastAPI(
    title="Ink & Memory API",
    description="Voice analysis and creative generation API",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== Request/Response Models ==========

class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    token: str
    user: dict

class ImportDataRequest(BaseModel):
    currentSession: Optional[str] = None
    calendarEntries: Optional[str] = None
    dailyPictures: Optional[str] = None
    voiceCustomizations: Optional[str] = None
    metaPrompt: Optional[str] = None
    stateConfig: Optional[str] = None
    selectedState: Optional[str] = None
    analysisReports: Optional[str] = None
    oldDocument: Optional[str] = None

# ========== Auth Dependency ==========

def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """
    Dependency to extract and verify JWT token from Authorization header.

    Raises:
        HTTPException 401 if token is missing or invalid
    """
    token = auth.extract_token_from_header(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing authorization token")

    user_data = auth.verify_access_token(token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return user_data

# ========== Custom API Endpoints (Clean Interface) ==========

@app.get("/")
def root():
    """Root endpoint"""
    return {
        "service": "Ink & Memory API",
        "version": "2.0.0",
        "docs": "/docs",
        "control_panel": "/polycli"
    }

# ========== Auth Endpoints ==========

@app.post("/api/register", response_model=TokenResponse)
def register(request: RegisterRequest):
    """
    Register a new user.

    Returns JWT token and user info.
    """
    # Validate input
    if not request.email or not request.password:
        raise HTTPException(status_code=400, detail="Email and password required")

    if len(request.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    # Hash password
    password_hash = auth.hash_password(request.password)

    # Create user
    try:
        user_id = database.create_user(request.email, password_hash, request.display_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Generate token
    token = auth.create_access_token(user_id, request.email)

    return {
        "token": token,
        "user": {
            "id": user_id,
            "email": request.email,
            "display_name": request.display_name
        }
    }

@app.post("/api/login", response_model=TokenResponse)
def login(request: LoginRequest):
    """
    Login with email and password.

    Returns JWT token and user info.
    """
    # Get user by email
    user = database.get_user_by_email(request.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Verify password
    if not auth.verify_password(request.password, user['password_hash']):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Generate token
    token = auth.create_access_token(user['id'], user['email'])

    return {
        "token": token,
        "user": {
            "id": user['id'],
            "email": user['email'],
            "display_name": user['display_name']
        }
    }

@app.get("/api/me")
def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """
    Get current user info from token.

    Requires Authorization header with Bearer token.
    """
    user = database.get_user_by_id(current_user['user_id'])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": user['id'],
        "email": user['email'],
        "display_name": user['display_name'],
        "created_at": user['created_at']
    }

@app.post("/api/import-local-data")
def import_local_data(request: ImportDataRequest, current_user: dict = Depends(get_current_user)):
    """
    Import localStorage data to database on first login.

    Extracts sessions, pictures, preferences, and reports from localStorage export.
    """
    import json

    user_id = current_user['user_id']

    print(f"\n🔍 Migration request for user {user_id}:")
    print(f"  - currentSession: {len(request.currentSession) if request.currentSession else 0} chars")
    print(f"  - calendarEntries: {len(request.calendarEntries) if request.calendarEntries else 0} chars")
    print(f"  - dailyPictures: {len(request.dailyPictures) if request.dailyPictures else 0} chars")
    print(f"  - oldDocument: {len(request.oldDocument) if request.oldDocument else 0} chars")

    # Extract sessions
    sessions = []

    # 1. Current session
    if request.currentSession:
        try:
            current = json.loads(request.currentSession)
            sessions.append({
                'id': 'current-session',
                'name': 'Current Session',
                'editor_state': current
            })
            print(f"✅ Imported current session ({len(str(current))} chars)")
        except Exception as e:
            print(f"❌ Failed to parse current session: {e}")
            # Don't silently fail - this is critical data!

    # 2. Calendar entries
    if request.calendarEntries:
        try:
            calendar = json.loads(request.calendarEntries)
            print(f"📅 Parsed calendar with {len(calendar)} dates")
            for date, entries in calendar.items():
                print(f"  - {date}: {len(entries)} entries")
                for entry in entries:
                    sessions.append({
                        'id': entry['id'],
                        'name': f"{date} - {entry.get('firstLine', 'Untitled')}",
                        'editor_state': entry['state']
                    })
        except Exception as e:
            print(f"❌ Failed to parse calendar entries: {e}")
            import traceback
            traceback.print_exc()

    # 3. Old document (if exists)
    if request.oldDocument:
        try:
            old_doc = json.loads(request.oldDocument)
            if old_doc and old_doc.get('document'):
                sessions.append({
                    'id': 'old-document',
                    'name': 'Old Document (migrated)',
                    'editor_state': {'cells': [{'type': 'text', 'content': str(old_doc)}]}
                })
        except:
            pass

    # Extract pictures
    pictures = []
    if request.dailyPictures:
        try:
            pics = json.loads(request.dailyPictures)
            for pic in pics:
                pictures.append({
                    'date': pic['date'],
                    'image_base64': pic['base64'],
                    'prompt': pic.get('prompt', '')
                })
        except:
            pass

    # Extract preferences
    preferences = {}
    if request.voiceCustomizations:
        try:
            preferences['voice_configs'] = json.loads(request.voiceCustomizations)
        except:
            pass

    if request.metaPrompt:
        preferences['meta_prompt'] = request.metaPrompt

    if request.stateConfig:
        try:
            preferences['state_config'] = json.loads(request.stateConfig)
        except:
            pass

    if request.selectedState:
        preferences['selected_state'] = request.selectedState

    # Extract reports
    reports = []
    if request.analysisReports:
        try:
            report_list = json.loads(request.analysisReports)
            for report in report_list:
                reports.append({
                    'type': report.get('type', 'unknown'),
                    'data': report.get('data', {}),
                    'allNotes': report.get('allNotes', ''),
                    'timestamp': report.get('timestamp', '')
                })
        except:
            pass

    # Import to database
    database.import_user_data(user_id, sessions, pictures, preferences, reports)

    return {
        "success": True,
        "imported": {
            "sessions": len(sessions),
            "pictures": len(pictures),
            "preferences": len([k for k, v in preferences.items() if v]),
            "reports": len(reports)
        }
    }

# ========== Session Storage Endpoints ==========

@app.post("/api/sessions")
def save_session(
    request: dict,
    current_user: dict = Depends(get_current_user)
):
    """
    Save or update a session.

    Request body:
    {
        "session_id": "string",
        "name": "optional string",
        "editor_state": {...}
    }
    """
    user_id = current_user['user_id']
    session_id = request.get('session_id')
    editor_state = request.get('editor_state')
    name = request.get('name')

    if not session_id or not editor_state:
        raise HTTPException(status_code=400, detail="session_id and editor_state required")

    database.save_session(user_id, session_id, editor_state, name)

    return {"success": True}

@app.post("/api/import-calendar-recovery")
def import_calendar_recovery(
    request: dict,
    current_user: dict = Depends(get_current_user)
):
    """
    Recovery endpoint to import calendar entries that were missed in initial migration.

    Request body:
    {
        "calendarEntries": "{\"2025-11-01\": [...]}"  # JSON string
    }
    """
    import json

    user_id = current_user['user_id']
    calendar_json = request.get('calendarEntries')

    if not calendar_json:
        raise HTTPException(status_code=400, detail="calendarEntries required")

    sessions = []
    try:
        calendar = json.loads(calendar_json)
        print(f"📅 Recovery import: {len(calendar)} dates")
        for date, entries in calendar.items():
            print(f"  - {date}: {len(entries)} entries")
            for entry in entries:
                sessions.append({
                    'id': entry['id'],
                    'name': f"{date} - {entry.get('firstLine', 'Untitled')}",
                    'editor_state': entry['state']
                })
    except Exception as e:
        print(f"❌ Failed to parse calendar: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Failed to parse calendar: {str(e)}")

    # Import to database
    database.import_user_data(user_id, sessions, [], {}, [])

    return {
        "success": True,
        "imported": {
            "sessions": len(sessions)
        }
    }

@app.get("/api/sessions")
def list_sessions(current_user: dict = Depends(get_current_user)):
    """
    List all sessions for current user.

    Returns: Array of session metadata (without full editor state)
    """
    user_id = current_user['user_id']
    sessions = database.list_sessions(user_id)
    return {"sessions": sessions}

@app.get("/api/sessions/{session_id}")
def get_session(session_id: str, current_user: dict = Depends(get_current_user)):
    """
    Get a specific session by ID.

    Returns: Full session including editor_state
    """
    user_id = current_user['user_id']
    session = database.get_session(user_id, session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session

@app.delete("/api/sessions/{session_id}")
def delete_session_endpoint(session_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a session."""
    user_id = current_user['user_id']
    database.delete_session(user_id, session_id)
    return {"success": True}

# ========== Pictures Endpoints ==========

@app.get("/api/pictures")
def get_pictures(
    limit: int = 30,
    current_user: dict = Depends(get_current_user)
):
    """
    Get recent daily pictures for current user.

    Query params:
    - limit: Max number of pictures to return (default 30)
    """
    user_id = current_user['user_id']
    pictures = database.get_daily_pictures(user_id, limit)
    return {"pictures": pictures}

@app.post("/api/pictures")
def save_picture(
    request: dict,
    current_user: dict = Depends(get_current_user)
):
    """
    Save a daily picture.

    Request body:
    {
        "date": "YYYY-MM-DD",
        "image_base64": "base64 string",
        "prompt": "optional prompt"
    }
    """
    user_id = current_user['user_id']
    date = request.get('date')
    image_base64 = request.get('image_base64')
    prompt = request.get('prompt', '')

    if not date or not image_base64:
        raise HTTPException(status_code=400, detail="date and image_base64 required")

    database.save_daily_picture(user_id, date, image_base64, prompt)
    return {"success": True}

# ========== Preferences Endpoints ==========

@app.get("/api/preferences")
def get_preferences(current_user: dict = Depends(get_current_user)):
    """Get user preferences."""
    user_id = current_user['user_id']
    preferences = database.get_preferences(user_id)
    return preferences or {}

@app.post("/api/preferences")
def save_preferences_endpoint(
    request: dict,
    current_user: dict = Depends(get_current_user)
):
    """
    Save user preferences.

    Request body can contain any of:
    - voice_configs: dict
    - meta_prompt: str
    - state_config: dict
    - selected_state: str
    """
    user_id = current_user['user_id']

    database.save_preferences(
        user_id,
        voice_configs=request.get('voice_configs'),
        meta_prompt=request.get('meta_prompt'),
        state_config=request.get('state_config'),
        selected_state=request.get('selected_state')
    )

    return {"success": True}

# ========== Analysis Reports Endpoints ==========

@app.get("/api/reports")
def get_reports(
    limit: int = 10,
    current_user: dict = Depends(get_current_user)
):
    """Get recent analysis reports."""
    user_id = current_user['user_id']
    reports = database.get_analysis_reports(user_id, limit)
    return {"reports": reports}

@app.post("/api/reports")
def save_report(
    request: dict,
    current_user: dict = Depends(get_current_user)
):
    """
    Save an analysis report.

    Request body:
    {
        "report_type": "echoes" | "traits" | "patterns",
        "report_data": {...},
        "all_notes_text": "optional text"
    }
    """
    user_id = current_user['user_id']
    report_type = request.get('report_type')
    report_data = request.get('report_data')
    all_notes_text = request.get('all_notes_text', '')

    if not report_type or not report_data:
        raise HTTPException(status_code=400, detail="report_type and report_data required")

    database.save_analysis_report(user_id, report_type, report_data, all_notes_text)
    return {"success": True}

@app.get("/api/default-voices")
def get_default_voices():
    """Get default voice configurations"""
    return config.VOICE_ARCHETYPES

@app.post("/api/analyze")
async def analyze_api(request_data: dict):
    """
    @@@ Analyze text and return ONE new voice comment (sync API).

    Uses PolyCLI's sync API internally - no polling needed!
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8765/polycli/api/trigger-sync",
            json={
                "session_id": "analyze_text",
                "params": request_data,
                "timeout": 30.0
            },
            timeout=35.0
        )
        return response.json()

@app.post("/api/chat")
async def chat_api(request_data: dict):
    """
    @@@ Chat with a voice persona (sync API).

    Uses PolyCLI's sync API internally - no polling needed!
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8765/polycli/api/trigger-sync",
            json={
                "session_id": "chat_with_voice",
                "params": request_data,
                "timeout": 30.0
            },
            timeout=35.0
        )
        return response.json()

@app.post("/api/generate-image")
async def generate_image_api(request_data: dict):
    """
    @@@ Generate artistic image from notes (sync API).

    This may take longer (60s timeout) due to image generation.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8765/polycli/api/trigger-sync",
            json={
                "session_id": "generate_daily_picture",
                "params": request_data,
                "timeout": 60.0  # Image generation takes longer
            },
            timeout=65.0
        )
        return response.json()

@app.post("/api/analyze-echoes")
async def analyze_echoes_api(request_data: dict):
    """Analyze recurring themes in notes (sync API)."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8765/polycli/api/trigger-sync",
            json={
                "session_id": "analyze_echoes",
                "params": request_data,
                "timeout": 30.0
            },
            timeout=35.0
        )
        return response.json()

@app.post("/api/analyze-traits")
async def analyze_traits_api(request_data: dict):
    """Analyze personality traits from notes (sync API)."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8765/polycli/api/trigger-sync",
            json={
                "session_id": "analyze_traits",
                "params": request_data,
                "timeout": 30.0
            },
            timeout=35.0
        )
        return response.json()

@app.post("/api/analyze-patterns")
async def analyze_patterns_api(request_data: dict):
    """Analyze behavioral patterns from notes (sync API)."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8765/polycli/api/trigger-sync",
            json={
                "session_id": "analyze_patterns",
                "params": request_data,
                "timeout": 30.0
            },
            timeout=35.0
        )
        return response.json()

# ========== Mount PolyCLI Control Panel ==========

registry = get_registry()
mount_control_panel(app, registry, prefix="/polycli")

# ========== Main ==========

if __name__ == "__main__":
    import uvicorn

    print("\n" + "="*60)
    print("🎭 Ink & Memory FastAPI Server")
    print("="*60)
    print("\n📚 API Endpoints:")
    print("  Clean API:")
    print("    POST /api/analyze         - Analyze text (sync)")
    print("    POST /api/chat            - Chat with voice (sync)")
    print("    POST /api/generate-image  - Generate image (sync)")
    print("    POST /api/analyze-echoes  - Find themes (sync)")
    print("    POST /api/analyze-traits  - Identify traits (sync)")
    print("    POST /api/analyze-patterns - Find patterns (sync)")
    print("    GET  /api/default-voices  - Get voice configs")
    print("\n  PolyCLI Control Panel:")
    print("    /polycli                  - Control panel UI")
    print("    /polycli/api/trigger-sync - Direct sync API")
    print("\n  Documentation:")
    print("    /docs                     - Auto-generated API docs")
    print("="*60 + "\n")

    uvicorn.run(app, host="127.0.0.1", port=8765)
