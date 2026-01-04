# Ink & Memory · English | [中文](README.zh.md)

Ink & Memory is a Disco Elysium–inspired journaling studio where inner voices respond to every sentence. It has grown into a complete daily writing workspace with auto-save, calendar and timeline review, friend timelines, and per-user timezone awareness. The entire experience works in both English and Chinese.

![Writing area](assets/writing-area.png)

---

## What You Can Do

- **Write in two languages** – The notebook, highlights, captions, and voice comments support both English and Chinese, switching automatically with your text.
- **Hear your inner council** – Thirteen Disco-style voices comment live, each with its own highlight color, icon, and persona.
- **Trust auto-save** – Manual “Save today” and the silent auto-save share the exact same logic, so every session is persisted with `editor_state.createdAt` and can be reopened from the calendar or timeline.
- **Review your days** – Calendar and timeline use the same grouped session data, so captions, pictures, and timestamps always match. Clicking a day reloads that precise session.
- **Compare with friends** – Pin a friend’s timeline to the right edge, complete with hint cards when they have no entries for a range of days.
- **See your time** – All timestamps are stored in UTC but displayed in your local timezone. We also record your preferred timezone for future per-user scheduling.

---

## The Voices

All thirteen Disco Elysium archetypes are included: Logic, Empathy, Inland Empire, Volition, Drama, Authority, Half Light, Shivers, Composure, Encyclopedia, Conceptualization, Suggestion, and Electrochemistry. Each persona keeps its own comment history, avoids duplicates, and responds in the language you are currently writing in.

---

## Architecture Snapshot

### Frontend (React + TypeScript)
- TipTap editor with custom highlight brushes and per-voice overlays.
- Auto-save every 3 seconds using the same routine as manual saves.
- Shared session grouping helper (`src/utils/sessionGrouping.ts`) powers both the calendar popup and timeline view.
- Browser timezone detection synced to backend preferences.

### Backend (FastAPI + PolyCLI)
- Stateful analyzer enforcing density rules, deduplication, and emotional-state prompts.
- Timeline image scheduler (currently global, future per-user cadence) built on PolyCLI sessions.
- SQLite persistence with UTC timestamps (TZ forced at process start).
- Control panel and session registry for debugging and PolyCLI experiments.

---

## Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- [uv](https://github.com/astral-sh/uv) for Python package management

### Backend
```bash
cd backend
uv venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
uv pip install -e ../PolyCLI
uv pip install beautifulsoup4 requests 'httpx[socks]'

cat > models.json <<'EOC'
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

python server.py
```
Runs at `http://localhost:8765`.

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Runs at `http://localhost:5173`.

---

## Daily Workflow
1. Start backend + frontend.
2. Write in English or Chinese; voices respond immediately.
3. Auto-save handles persistence. “Save today” is optional if you want to tag the calendar entry.
4. Review prior days via the calendar or timeline; both use the same captions and timestamps.
5. Pin a friend timeline from the picker to compare side-by-side.
6. Export/import data via the built-in API endpoints when switching devices.

---

## Roadmap
- **Per-user timeline scheduling** – Scheduler currently runs once per day using a single timezone; we now store `timezone` in preferences and will move to per-user cadence.
- **Friend timezone awareness** – Friend timelines will eventually display which timezone their entries use once per-user scheduling lands.
- **Visitor “shadow accounts”** – Reintroduce visitor mode by minting anonymous user records per browser session (UUID + JWT) so visitors hit the exact same backend paths with restricted quotas. No localStorage divergences.
- **Open-source polish** – Document control-plane endpoints, linting, and seed data for new deployments.

---

## Project Structure
```
ink-and-memory/
├── assets/                         # README screenshots, fonts, art
│   └── writing-area.png            # Current product shot
├── backend/                        # FastAPI + PolyCLI server
│   ├── server.py                   # Main API entrypoint (UTC enforced)
│   ├── scheduler.py                # Timeline image cron
│   ├── database.py                 # SQLite schema + helpers (sessions, prefs)
│   ├── config.py / prompts/        # Voice archetypes + system prompts
│   └── archive/                    # Research + vibe-coding notes
└── frontend/                       # React + TipTap client
    ├── src/App.tsx                 # Notebook, auto-save, timezone sync
    ├── src/components/             # Calendar, timeline, friends, decks, etc.
    ├── src/utils/sessionGrouping.ts# Shared calendar/timeline grouping helper
    ├── src/api/voiceApi.ts         # REST client for backend
    └── public/                     # Fonts, favicon, static assets
```

---

## Contributing
This is still a personal experimental project, but feel free to fork and adapt.

## License
MIT

## Credits
- Inspired by [Disco Elysium](https://discoelysium.com/)
- Built with [PolyCLI](https://github.com/shuxueshuxue/PolyCLI)
- Fonts: [Excalifont](https://github.com/excalidraw/excalidraw) & Xiaolai
