# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

**Ink & Memory** is a Disco Elysium-inspired journaling interface where inner voice personas comment on your writing in real-time. The system uses LLMs to generate commentary from distinct archetypes that interrupt and debate as you write.

**Key Innovation**: Trace-based energy accumulation system where writing builds up energy until threshold is reached, then triggers LLM analysis. Comments appear as watercolor highlights with personas commenting in the margins.

---

## Development Commands

### Backend (Python + PolyCLI)

```bash
# Setup
cd backend
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install PolyCLI from local development
cd ~/Codebase/PolyCLI
uv pip install -e .

cd ~/Codebase/ink-and-memory/backend
uv pip install beautifulsoup4 requests 'httpx[socks]' Pillow PyJWT

# Start server
python server.py
# Runs on http://localhost:8765
```

### Frontend (React + TypeScript + Vite)

```bash
cd frontend

# Development
npm install
npm run dev
# Runs on http://localhost:5173

# Production build
npm run build
# Output: dist/

# Lint
npm run lint

# Preview production build
npm preview
```

---

## Architecture Deep Dive

### Core Data Flow

```
User types → Weight accumulates → Threshold (40 energy) → Backend analysis
         ↓                                                         ↓
    EditorEngine                                    PolyCLI session function
         ↓                                                         ↓
  Apply comment → Collision detection → Highlight phrase in cell
```

### Critical Components

#### 1. EditorEngine (`frontend/src/engine/EditorEngine.ts`)

**Purpose**: Single source of truth for editor state. Manages cells, commentors, energy accumulation.

**Key patterns**:
- **Weight function** (`computeWeight`): CJK chars = 2, sentence endings = 4, Chinese comma = 0, other = 1
- **Energy accumulation**: `delta = max(0, currentWeight - lastWeight)`, only positive deltas add energy
- **Collision detection**: Before applying comment, check if phrase overlaps with existing highlights
- **Cells system**: Editor content is an array of cells (text cells + widget cells like chat)

**@@@ Critical**: When programmatically inserting text (e.g., quoting a comment), you MUST update the baseline weight to prevent false energy accumulation:

```typescript
setTimeout(() => {
  lastPollWeightRef.current = getWeightedLength(currentTextRef.current);
}, 0);
```

#### 2. Voice Analysis System (`backend/stateless_analyzer.py`)

**Stateless design**: Receives applied comments, returns ONE new comment (gradual accumulation).

**Key features**:
- **Explicit overlap avoidance**: Prompt shows LLM all existing highlighted phrases + rejected phrases
- **Voice ID system**: LLM returns `voice_id` (e.g., "holder"), backend auto-fills display name from config
- **Language matching**: LLM writes comments in same language as input text
- **Structured output**: Uses Pydantic schema for reliable JSON parsing

**@@@ Important**: The prompt explicitly tells LLM to extract phrases ONLY from "TEXT TO ANALYZE" section, NOT from conversation context.

#### 3. Authentication & Database (`backend/auth.py`, `backend/database.py`)

**JWT-based auth**:
- Users register/login → receive JWT token
- Frontend stores token in localStorage
- All API calls to `/polycli/api/trigger-sync` include `Authorization: Bearer <token>` header
- PolyCLI middleware extracts user_id from token, injects into session params

**Database schema**:
- `users` - email, password_hash, display_name
- `sessions` - editor_state (JSON), user_id, session_id
- `daily_pictures` - base64 images, thumbnails, prompts
- `preferences` - voice_configs, meta_prompt, state_config, selected_state
- `analysis_reports` - echoes/traits/patterns analysis results

**@@@ Migration system**: First-time login shows migration dialog to import localStorage data to database.

#### 4. PolyCLI Integration

**Session definitions** (`@session_def` in `backend/server.py`):

```python
@session_def(name="Analyze Voices", params={...})
def analyze_text(text: str, session_id: str, user_id: int, applied_comments: list, ...):
    # user_id injected by auth middleware
    # Loads voice configs from database using user_id
    prefs = database.get_preferences(user_id)
    voices = prefs['voice_configs'] or config.VOICE_ARCHETYPES
    # ...
```

**Frontend calls**:
```typescript
fetch(`${API_BASE}/polycli/api/trigger-sync`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify({
    session_id: 'analyze_voices',  // Matches @session_def name
    params: { text, session_id, applied_comments, ... },
    timeout: 60
  })
})
```

**Response format**: `{success: true, result: {...}}` or `{success: false, error: "..."}`

---

## Key Implementation Patterns

### Pattern 1: Energy Pool System

**Problem**: How to trigger LLM analysis without constant polling waste?

**Solution**: Track weight changes over time, accumulate only positive deltas as energy:

```typescript
// In App.tsx, every 5 seconds:
const currentWeight = computeWeight(allText);
const delta = Math.max(0, currentWeight - lastPollWeightRef.current);
energyRef.current += delta;

if (energyRef.current >= 40 && !isAnalyzing) {
  // Trigger backend analysis
  energyRef.current -= 40;  // Consume energy, preserve remainder
}

lastPollWeightRef.current = currentWeight;
```

**@@@ Quote weight hack**: When quoting a voice comment, the quoted text gets inserted but should NOT count as "new writing". Solution: immediately update baseline after insertion.

### Pattern 2: Collision Detection (Two-Layer Defense)

**Layer 1 (Backend LLM prompt)**: Show LLM all existing highlighted phrases + rejected phrases

```python
conversation_context += f"⚠️ Already highlighted: {highlighted_phrases}\n"
rejected_section += f"✗ '{phrase}' - REJECTED, do NOT suggest again\n"
```

**Layer 2 (Frontend engine)**: Before applying comment, check for overlap:

```typescript
const hasCollision = existingHighlights.some(h =>
  (newStart >= h.start && newStart < h.end) ||
  (newEnd > h.start && newEnd <= h.end) ||
  (newStart <= h.start && newEnd >= h.end)
);

if (hasCollision) {
  // Add to overlappedPhrases, send as feedback on next analysis
  return;
}
```

**Why two layers?** LLMs are not 100% reliable, so frontend provides safety net.

### Pattern 3: Per-Cell State Management

**Why?** Multi-cell editor with IME composition (Chinese/Japanese input) requires careful state isolation.

```typescript
// Track local text per cell ID
const [localTexts, setLocalTexts] = useState<Map<string, string>>(new Map());
const [composingCells, setComposingCells] = useState<Set<string>>(new Set());

const handleTextChange = (cellId: string, newText: string) => {
  setLocalTexts(prev => {
    const next = new Map(prev);
    next.set(cellId, newText);
    return next;
  });

  // Only update engine if NOT composing
  if (!composingCells.has(cellId)) {
    engineRef.current.updateTextCell(cellId, newText);
  }
};

const handleCompositionEnd = (cellId: string, e: CompositionEvent) => {
  // Commit to engine only after composition finishes
  engineRef.current.updateTextCell(cellId, e.currentTarget.value);
};
```

**@@@ Critical**: Never use array indices to track cells. Always use cell IDs (UUIDs).

### Pattern 4: Voice Configuration Hierarchy

**Three sources** (in priority order):

1. **User's custom configs** (stored in database `preferences` table)
2. **Default archetypes** (`backend/config.py` → `VOICE_ARCHETYPES`)
3. **Fallback** (if voice_id not found)

```python
# Backend loads from database
prefs = database.get_preferences(user_id)
voice_configs = prefs['voice_configs'] if prefs else None

# Lookup specific voice
if voice_id in voice_configs:
    voice_config = voice_configs[voice_id]
else:
    # Fall back to default
    voice_config = config.VOICE_ARCHETYPES.get(voice_id, {...})
```

**Frontend never sends voice configs** - backend loads from database using `user_id` from JWT.

### Pattern 5: Scroll-Independent Positioning

**Problem**: Comments were shifting when user scrolled then clicked.

**Solution**: Use `offsetTop` (document-relative) instead of `getBoundingClientRect()` (viewport-relative):

```typescript
const cellWrapper = cellTextarea.parentElement; // The div with position: relative
const cellOffsetTop = cellWrapper.offsetTop;

// Position using offsetTop (scroll-independent)
const topPosition = cellOffsetTop + group.centerY + containerPadding + stateChooserHeight - (lineHeight * 0.7);
```

**Why 0.7 lineHeight?** Iteratively tested: 1.0 = too far up, 0.5 = too far down, 0.7 = perfect alignment.

---

## Database-First Architecture (Recent Refactor)

**Before**: Frontend sent voice configs in every API call, used localStorage

**After**:
- Voice configs stored in database `preferences.voice_configs`
- Backend loads configs using `user_id` from JWT token
- Frontend only sends `voice_id` (e.g., "holder"), backend looks up full config
- localStorage only used for unauthenticated draft mode

**Migration path**:
1. User logs in for first time
2. Frontend shows migration dialog
3. Calls `/api/import-local-data` with localStorage export
4. Backend imports sessions/pictures/preferences/reports to database
5. Sets `first_login_completed` flag

---

## File Organization

```
ink-and-memory/
├── backend/
│   ├── server.py              # FastAPI app + PolyCLI session definitions
│   ├── stateless_analyzer.py  # LLM prompt + analysis logic
│   ├── config.py              # Voice archetypes + model config
│   ├── auth.py                # JWT token creation/verification
│   ├── database.py            # SQLite operations
│   ├── proxy_config.py        # GFW bypass for API calls
│   └── prompts/               # Voice persona system prompts
│       ├── holder.md
│       ├── unpacker.md
│       └── ...
│
└── frontend/
    ├── src/
    │   ├── App.tsx            # Main application component
    │   │                      # - Energy polling system
    │   │                      # - Comment positioning logic
    │   │                      # - Per-cell state management
    │   │
    │   ├── engine/
    │   │   ├── EditorEngine.ts    # Core state management + collision detection
    │   │   └── ChatWidget.ts      # Chat widget data model
    │   │
    │   ├── components/
    │   │   ├── VoiceSettings.tsx  # Voice persona CRUD
    │   │   ├── StateChooser.tsx   # Emotional state selector
    │   │   ├── AgentDropdown.tsx  # @ voice selection dropdown
    │   │   ├── ChatWidgetUI.tsx   # Chat widget UI
    │   │   ├── CalendarPopup.tsx  # Calendar for saving/loading entries
    │   │   ├── AnalysisView.tsx   # Echoes/traits/patterns analysis
    │   │   └── ...
    │   │
    │   ├── api/
    │   │   └── voiceApi.ts        # Backend API calls
    │   │
    │   ├── contexts/
    │   │   └── AuthContext.tsx    # JWT token management
    │   │
    │   └── utils/
    │       ├── voiceStorage.ts    # localStorage utilities
    │       ├── calendarStorage.ts # Calendar entry management
    │       └── textNormalize.ts   # Case-insensitive phrase matching
    │
    └── vite.config.ts         # CRITICAL: base: '/ink-and-memory/'
```

---

## Common Development Tasks

### Adding a New Voice Persona

1. Create prompt file: `backend/prompts/new_voice.md`
2. Add to `backend/config.py`:
   ```python
   VOICE_ARCHETYPES = {
       "new_voice": {
           "name": "Display Name",
           "tagline": _load_prompt("new_voice.md"),
           "icon": "brain",  # Must be from icon list
           "color": "blue"   # Must be from color list
       }
   }
   ```
3. Icon options: brain, heart, question, cloud, masks, eye, fist, lightbulb, shield, wind, fire, compass
4. Color options: blue, pink, yellow, green, purple

### Adding a New PolyCLI Session

1. Define in `backend/server.py`:
   ```python
   @session_def(
       name="Your Session Name",
       description="What it does",
       params={"param1": {"type": "str"}, ...},
       category="Category"
   )
   def your_function(param1: str, user_id: int):
       # user_id is auto-injected by auth middleware
       # ...
       return {"result": "..."}
   ```

2. Call from frontend:
   ```typescript
   const token = localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN);

   const response = await fetch(`${API_BASE}/polycli/api/trigger-sync`, {
     method: 'POST',
     headers: {
       'Authorization': `Bearer ${token}`,
       'Content-Type': 'application/json'
     },
     body: JSON.stringify({
       session_id: 'your_session_name',  // Lowercase snake_case
       params: { param1: "value" },
       timeout: 60
     })
   });

   const data = await response.json();
   if (data.success) {
     // Use data.result
   }
   ```

### Debugging Energy System

Check energy accumulation in browser console:
```
Energy accumulated: +5 (total: 12/40)
```

Check weight calculation:
```typescript
console.log('Weight:', computeWeight(text));
console.log('Delta:', currentWeight - lastWeight);
```

Check backend logs for LLM calls:
```
🎯 Stateless analyze_text() called
   Text: ...
   Applied comments: 3
```

### Testing Collision Detection

1. Write text with multiple distinct phrases
2. Wait for first comment to appear (energy >= 40)
3. Continue writing
4. Check if new comments avoid overlapping with existing highlights
5. Check console for:
   ```
   ⚠️ Collision detected for "phrase", skipping
   ```

---

## Important Patterns to Remember

### @@@ Comment Format
Use `@@@title - explanation` format for tricky code sections to enable easy navigation:

```typescript
// @@@ Quote Weight Hack - prevent false energy accumulation
setTimeout(() => {
  lastPollWeightRef.current = getWeightedLength(currentTextRef.current);
}, 0);
```

### Minimal Implementation Principle
- Code is expensive (buys features with complexity)
- Prefer simple solutions over defensive edge cases
- Show what's there, don't guess (print-based debugging)

### Authentication Headers
All `/polycli/api/trigger-sync` calls MUST include:
```typescript
headers: {
  'Authorization': `Bearer ${token}`
}
```

### Response Format Pattern
PolyCLI always returns:
```typescript
{
  success: true,
  result: {...}  // Your data here
}
// or
{
  success: false,
  error: "Error message"
}
```

Always check `data.success` before accessing `data.result`.

---

## Deployment to Production

**Server**: Alibaba Cloud (101.201.227.31)
**SSH Key**: `~/Codebase/serverManagement/keys/Jeffry.pem`
**Live URL**: https://lexicalmathical.com/ink-and-memory/

### Full Deployment Process

```bash
# 1. Build frontend
cd ~/Codebase/ink-and-memory/frontend
npm run build

# 2. Deploy frontend
scp -i ~/Codebase/serverManagement/keys/Jeffry.pem -r dist/* \
  root@101.201.227.31:/var/www/lexicalmathical.com/ink-and-memory/

# 3. Fix permissions
ssh -i ~/Codebase/serverManagement/keys/Jeffry.pem root@101.201.227.31 \
  "chown -R www-data:www-data /var/www/lexicalmathical.com/ink-and-memory/"

# 4. Deploy backend
cd ~/Codebase/ink-and-memory/backend
scp -i ~/Codebase/serverManagement/keys/Jeffry.pem *.py \
  root@101.201.227.31:/root/ink-and-memory/backend/

# 5. Restart backend (running in tmux session 'ink-and-memory')
ssh -i ~/Codebase/serverManagement/keys/Jeffry.pem root@101.201.227.31 "
  tmux send-keys -t ink-and-memory:0 C-c
  sleep 2
  tmux send-keys -t ink-and-memory:0 'cd /root/ink-and-memory/backend && source .venv/bin/activate && python server.py' Enter
"
```

**Verification**:
```bash
# Check backend is running
ssh -i ~/Codebase/serverManagement/keys/Jeffry.pem root@101.201.227.31 \
  "lsof -i :8765"

# Test live API
curl -s https://lexicalmathical.com/ink-and-memory/api/sessions | jq
```

**CRITICAL**: `vite.config.ts` must have `base: '/ink-and-memory/'` to match deployment path.

---

## Known Issues & Quirks

### IME Composition
Chinese/Japanese input requires special handling. Never update state during composition, only on `compositionend` event.

### Font Loading
Uses `font-display: swap` to prevent FOIT (Flash of Invisible Text). Fonts are preloaded in `index.html`.

### Mobile Differences
- No left sidebar (hidden)
- Floating toolbar in top right
- Comment popup at bottom instead of right margin
- Detection: `useMobile()` hook checks `window.innerWidth < 768`

### Browser Auto-Scroll
Prevent browser from scrolling element into view on focus:
```typescript
onFocus={(e) => {
  e.preventDefault();
}}
```

---

## Testing Checklist

Before deploying:
- [ ] Backend starts without errors on :8765
- [ ] Frontend builds without errors
- [ ] Voice comment analysis works (energy >= 40 triggers LLM)
- [ ] Chat widget works (can chat with voice personas)
- [ ] Authentication works (login/register/JWT)
- [ ] Calendar saves/loads entries correctly
- [ ] Voice settings CRUD works
- [ ] Mobile layout renders correctly
- [ ] No collision between highlighted phrases
- [ ] Image generation works (daily pictures)

---

## Dependencies

### Backend
- **PolyCLI** (local development): `~/Codebase/PolyCLI`
- **FastAPI**: Web server
- **Pillow**: Image conversion (PNG → JPEG + thumbnails)
- **PyJWT**: JWT token handling
- **httpx[socks]**: Proxy support for GFW bypass

### Frontend
- **React 19**: UI framework
- **Vite**: Build tool
- **TypeScript**: Type safety
- **react-icons**: Icon library

---

## Related Documentation

- **Server Infrastructure**: `~/Codebase/serverManagement/CLAUDE.md`
- **PolyCLI**: `~/Codebase/PolyCLI/README.md`
- **User Guide**: `README.md`
- **Refactor Status**: `/tmp/ink-and-memory-refactor-status.md` (recent changes)
