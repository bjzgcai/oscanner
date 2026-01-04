# Ink & Memory

Ink & Memory is a Disco Elysium–inspired journaling studio where your inner voices react to every sentence. It has grown beyond a concept demo into a multi-surface workspace with auto-save, calendar + timeline review, friend timelines, and per-user timezone awareness. English and Chinese are first-class citizens: the editor, calendar, timeline, voices, and prompts work in both languages from the first keystroke.

![Writing Area Screenshot](assets/writing-area.png)

## ✨ Experience Highlights

- **Living Commentary** — Thirteen Disco-style voices (Logic, Empathy, Volition, etc.) watch your text and deliver contextual comments, each with unique color/highlight styling.
- **Dynamic Highlighting** — Trigger phrases are painted directly on the notebook, pairing each voice’s comment with the exact text that summoned it.
- **Stateful Engine** — The backend remembers prior comments, prevents duplicates, enforces per-voice density, and honors the current emotional state/cube selection.
- **English + Chinese Support** — The editor, calendar/timeline, and all voices operate seamlessly in either language. Titles, captions, and first-line extraction work with both scripts.
- **Auto-Save = Save** — Manual “Save today” and silent auto-save share identical logic, so every session writes `editor_state.createdAt`. Nothing gets lost, and the calendar/timeline stay synchronized.
- **Calendar + Timeline Unification** — Both surfaces consume the same grouped session data, so captions + timezones always match. Clicking a day loads the exact session with full comments.
- **Timezone-Aware Timeline** — Timestamps are stored in UTC but rendered in the viewer’s local timezone. We also capture each user’s preferred timezone to support future per-user scheduling.
- **Friend Timelines** — Select friends to compare their daily pictures/comments side-by-side, with gentle hint cards when no friend data exists.
- **Binder Aesthetic** — The UI is intentionally tactile with ring binders, Excalifont handwriting, and Xiaolai Chinese glyphs.

## 🎭 The Voices

All thirteen voices from Disco Elysium ship with the app: Logic, Empathy, Inland Empire, Volition, Drama, Authority, Half Light, Shivers, Composure, Encyclopedia, Conceptualization, Suggestion, and Electrochemistry. Each voice stores its history, applies its own highlight gradient, and responds in English or Chinese depending on your writing language.

## 🏗️ Architecture

### Frontend (React + TypeScript)
- TipTap editor with custom highlight/brush renderers
- Auto-save every 3 seconds (shared logic with manual save)
- Calendar/timeline share the same grouping helper (`utils/sessionGrouping.ts`)
- Friend timeline picker + hint cards
- Browser timezone detection -> sent to backend preferences

### Backend (FastAPI + PolyCLI)
- Stateful analyzer enforcing density, deduplication, and history
- PolyCLI session registry + control panel for debugging
- Timeline scheduler capable of per-date generation (future: per-user timezone cadence)
- SQLite persistence with UTC timestamps (TZ forced at process start)

## 🚀 Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- [uv](https://github.com/astral-sh/uv) for Python package management

### Backend

```bash
cd backend

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install PolyCLI (from parent directory)
cd ~/Codebase/PolyCLI
uv pip install -e .

cd ~/Codebase/ink-and-memory/backend

# Install additional dependencies
uv pip install beautifulsoup4 requests 'httpx[socks]'

# Create models.json with your LLM API config
cat > models.json << 'EOC'
{
  "models": {
    "gpt-4o-dou": {
      "endpoint": "https://api.example.com/v1",
      "api_key": "your-api-key",
      "model": "openai/chatgpt-4o-latest"
    }
  }
}
EOC

# Start server
python server.py
```

Server runs at `http://localhost:8765`

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

App runs at `http://localhost:5173`

## 📖 Usage

1. Run backend + frontend
2. Compose in English or Chinese — voices respond immediately
3. Auto-save keeps every keystroke; manual “Save today” is only for calendar tagging
4. Calendar view lets you jump to any saved day, timeline shows daily pictures + captions
5. Friend timelines appear on the right, with hint cards when no data exists
6. Export/import your calendar via the built-in API endpoints

## 🗺️ Roadmap / TODO

- **Per-user timeline scheduling** — Scheduler still triggers in a single timezone. Now that each user preference stores `timezone`, we need to update the cron job + DB helpers to run at each user’s local midnight.
- **Friend timezone awareness** — When we implement per-user scheduling, we should also adjust friend views to clarify which timezone each timeline reflects.
- **Open-source polish** — Document control-plane endpoints, linting scripts, and provide sample data/migrations for new deployments.

## 📁 Project Structure

```
ink-and-memory/
├── assets/                         # README screenshots, fonts, art
│   └── writing-area.png            # Current product shot
├── backend/                        # FastAPI + PolyCLI server
│   ├── server.py                   # Main API entrypoint (UTC enforced)
│   ├── scheduler.py                # Timeline image cron
│   ├── database.py                 # SQLite schema + helpers (user_sessions, prefs)
│   ├── config.py / prompts/        # Voice archetypes + system prompts
│   └── archive/                    # Research + vibe coding notes
└── frontend/                       # React + TipTap client
    ├── src/App.tsx                 # Notebook, auto-save, timezone sync
    ├── src/components/             # Calendar, timeline, friends, decks, etc.
    ├── src/utils/sessionGrouping.ts# Shared calendar/timeline grouping helper
    ├── src/api/voiceApi.ts         # REST client for backend
    └── public/                     # Fonts, favicon, static assets
```

## 🤝 Contributing

This is a personal experimental project, but feel free to fork and adapt!

## 📜 License

MIT

## 🙏 Credits

- Inspired by [Disco Elysium](https://discoelysium.com/)
- Built with [PolyCLI](https://github.com/shuxueshuxue/PolyCLI)
- Fonts: [Excalifont](https://github.com/excalidraw/excalidraw) & Xiaolai
