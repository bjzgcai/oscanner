# Voice Customization System

## Architecture

### Source of Truth
- **Server**: Owns default voice configurations
- **localStorage**: Stores user customizations (complete replacement, not merge)

### Rule: No Merging
- User either uses server defaults OR their own customizations
- Never merge the two
- Clear ownership prevents conflicts

## Data Flow

```
┌─────────────────────────────────────────────────────────┐
│ 1. App Init: GET /api/sessions/analyze_text            │
│    Server returns default voices                        │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│ 2. Check localStorage['voice-customizations']          │
│    EXISTS    → Use customizations (ignore server)       │
│    NOT EXIST → Use server defaults                      │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│ 3. User edits in Settings Panel                        │
│    [Save]        → Write to localStorage                │
│    [Use Default] → Delete from localStorage             │
│    [Export]      → Download JSON file                   │
│    [Import]      → Read JSON → Write to localStorage    │
└─────────────────────────────────────────────────────────┘
```

## API Contract

### GET /api/sessions/{session_id}

**Response:**
```json
{
  "id": "analyze_text",
  "name": "Analyze Voices",
  "description": "Detect inner voices in writing",
  "defaultVoices": {
    "logic": {
      "name": "Logic",
      "systemPrompt": "You are Logic. Analyze for patterns and inconsistencies...",
      "icon": "🧠",
      "color": "#4a5568",
      "highlightColor": "blue"
    },
    "empathy": {
      "name": "Empathy",
      "systemPrompt": "You are Empathy. Focus on emotional depth...",
      "icon": "❤️",
      "color": "#e53e3e",
      "highlightColor": "pink"
    },
    "creativity": { /* ... */ },
    "criticism": { /* ... */ }
  }
}
```

### POST /api/trigger

**Request:**
```json
{
  "text": "The protagonist walked slowly...",
  "voices": {
    "logic": {
      "name": "Logic",
      "systemPrompt": "You are Logic...",
      "enabled": true,
      "icon": "🧠",
      "color": "#4a5568",
      "highlightColor": "blue"
    }
  }
}
```

**Notes:**
- Frontend sends complete voice configs (not IDs)
- Backend uses provided systemPrompt (doesn't look up)
- Only enabled voices are sent

## Type Definitions

### TypeScript
```typescript
// src/types/voice.ts
export interface VoiceConfig {
  name: string;
  systemPrompt: string;
  enabled: boolean;
  icon: string;
  color: string;
  highlightColor: string;
}

export type VoicesPayload = Record<string, VoiceConfig>;
```

### Python
```python
# backend/types.py
from pydantic import BaseModel

class VoiceConfig(BaseModel):
    name: str
    systemPrompt: str
    enabled: bool
    icon: str
    color: str
    highlightColor: str
```

## localStorage Schema

**Key:** `voice-customizations`

**Value:**
```json
{
  "version": "1.0.0",
  "voices": {
    "logic": {
      "name": "My Logic",
      "systemPrompt": "Custom prompt...",
      "enabled": true,
      "icon": "🧠",
      "color": "#4a5568",
      "highlightColor": "blue"
    }
  }
}
```

**Important:** If key exists, use it completely. Don't merge with server defaults.

## Settings Panel UI

```
┌────────────────────────────────────┐
│ Voice Settings              [Close]│
├────────────────────────────────────┤
│                                    │
│ [Import] [Export] [Use Default]    │
│                                    │
│ ┌──────────────────────────────┐  │
│ │ ☑ 🧠 Logic                   │  │
│ │ System Prompt:                │  │
│ │ ┌──────────────────────────┐ │  │
│ │ │You are Logic. Analyze... │ │  │
│ │ │                          │ │  │
│ │ └──────────────────────────┘ │  │
│ │ Color: [#4a5568 ▼]           │  │
│ └──────────────────────────────┘  │
│                                    │
│ ┌──────────────────────────────┐  │
│ │ ☑ ❤️ Empathy                  │  │
│ │ ...                           │  │
│ └──────────────────────────────┘  │
│                                    │
│              [Save Changes]        │
└────────────────────────────────────┘
```

### Buttons

**[Import]**
- Opens file picker
- Reads JSON file
- Validates schema
- Writes to localStorage
- Reloads app state

**[Export]**
- Reads current voices (from state, not localStorage)
- Downloads as `voice-config-{timestamp}.json`
- No server interaction

**[Use Default]**
- Deletes `voice-customizations` from localStorage
- Fetches server defaults again
- Reloads app state

**[Save Changes]**
- Writes current form state to localStorage
- No server interaction
- Shows confirmation toast

## Implementation Checklist

### Backend
- [ ] Add `defaultVoices` to session response
- [ ] Update `/api/trigger` to accept `voices` parameter
- [ ] Remove hardcoded voice lookups

### Frontend
- [ ] Create `VoiceConfig` type
- [ ] Create `SettingsPanel` component
- [ ] Create `VoiceEditor` component
- [ ] Implement localStorage manager
- [ ] Add import/export functions
- [ ] Update API calls to send voices
- [ ] Add settings toggle button

### Testing
- [ ] Test: Use server defaults (no localStorage)
- [ ] Test: Save customizations
- [ ] Test: Export → Import
- [ ] Test: Use Default (clears localStorage)
- [ ] Test: Invalid import JSON (error handling)

## Edge Cases

### Server defaults change
- User has old customizations in localStorage
- **Decision:** User customizations take precedence
- User must manually "Use Default" to get new server voices
- Alternative: Show notification "Server voices updated" with option to review

### Invalid localStorage data
- Corrupted JSON
- Missing required fields
- **Decision:** Delete and fall back to server defaults
- Log error to console for debugging

### Voice disabled mid-analysis
- User disables voice while analysis running
- **Decision:** Let current analysis finish
- Next trigger respects new enabled state

## Migration Plan

### Phase 1: Backend changes
1. Add `defaultVoices` to session endpoint
2. Accept `voices` in trigger endpoint
3. Deploy backend

### Phase 2: Frontend changes (compatible)
1. Add Settings Panel UI (hidden behind flag)
2. Add localStorage logic
3. Update trigger to send voices
4. Deploy frontend

### Phase 3: Enable feature
1. Remove feature flag
2. Show Settings button
3. Add onboarding tooltip

## Future Enhancements

### Voice Templates
- Share voice configs via URL
- Community voice library
- One-click install presets

### Validation
- Max prompt length (prevent token overflow)
- Required fields validation
- Color format validation

### Analytics
- Track which voices are most used
- Track customization adoption rate
- Track default vs custom usage

---

**Last Updated:** 2025-10-16
