# Ink and Memory

Ink & Memory is a Disco Elysium–inspired journaling environment where your inner voices respond to every sentence. The product has graduated from a quick concept to a multi-surface workspace with auto-save, calendar/timeline review, friend timelines, and per-user timezone awareness. We now treat English and Chinese as first-class citizens: voices, state prompts, and every UI label support both languages out of the box.

![Writing Area Screenshot](assets/writing-area.png)

## ✨ Product Capabilities

- **Living Commentary** — Thirteen Disco-style voices (Logic, Empathy, Volition, etc.) watch your text and deliver contextual comments, each with unique color/highlight styling.
- **Dynamic Highlighting** — Trigger phrases are painted directly on the notebook, pairing each voice’s comment with the exact text that summoned it.
- **Stateful Engine** — The backend remembers prior comments, prevents duplicates, enforces per-voice density, and honors the current emotional state/cube selection.
- **English + Chinese Support** — The editor, calendar/timeline, and all voices can operate seamlessly in either language. Calendar titles, timeline captions, and first-line extraction work with both scripts.
- **Auto-Save = Save** — Manual “Save today” and silent auto-save now share identical logic, guaranteeing every session writes `editor_state.createdAt`. Nothing gets lost, and the timeline/calendar stay synchronized.
- **Calendar + Timeline Unification** — Both surfaces consume the same grouped session data, so captions/timezones always match. Clicking a day loads the exact session with full comments.
- **Timezone-Aware Timeline** — Timestamps are stored in UTC but rendered in the viewer’s local timezone. We also capture each user’s preferred timezone to support future per-user scheduling.
- **Friend Timelines** — Select friends to compare their daily pictures/comments side-by-side, with gentle hint cards when no friend data exists.
- **Binder Aesthetic** — The UI is intentionally tactile with ring binders, Excalifont handwriting, and Xiaolai Chinese glyphs.

# 🎭 The Voices

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

## 🎨 Design Philosophy

### Vibe-Coding
This project was built using "observe-code-observe-code" rapid iteration:
- Minimal planning, maximal experimentation
- See `backend/archive/vibe-coding-scraper-example/` for a documented example

### Minimal Implementation
- Simple is better than complex
- Code buys features with complexity - spend wisely
- `@@@` comments mark tricky parts for easy navigation

## 🔧 Technical Highlights

### Stateful Commentary System
```python
class StatefulVoiceAnalyzer:
    def analyze(self, agent, text):
        # 1. Prune deleted comments
        self._prune_deleted_comments(text)

        # 2. Only ask LLM for NEW comments
        # (shows existing comments to avoid repetition)

        # 3. Enforce density rules
        # (1 per persona, 1 per sentence)

        # 4. Return ALL comments (old + new)
```

### Polling Strategy
```typescript
// Every 5 seconds, check if text changed >10 chars
useEffect(() => {
  const interval = setInterval(async () => {
    if (textDiff > 10 && !isAnalyzing) {
      const voices = await analyzeText(currentText);
      setVoiceTriggers(voices);
    }
  }, 5000);
  return () => clearInterval(interval);
}, []);
```

### Sentence Splitting (Multilingual)
```python
# English: .!?  Chinese: 。！？  Also: newlines
re.split(r'[.!?。！？]+|\n+', text)
```

## 🗺️ Roadmap / TODO

- **Per-user timeline scheduling** — Scheduler still triggers in a single timezone. Now that each user preference stores `timezone`, we need to update the cron job + DB helpers to run at each user’s local midnight.
- **Friend timezone awareness** — When we implement per-user scheduling, we should also adjust friend views to clarify which timezone each timeline reflects.
- **Open-source polish** — Document control-plane endpoints, linting scripts, and provide sample data/migrations for new deployments.

## 📁 Project Structure

```
ink-and-memory/
├── assets/
│   ├── demo-screenshot.png    # Demo screenshot
│   └── book-ui-design.png     # Original UI design
├── backend/
│   ├── server.py              # PolyCLI Session Registry server
│   ├── stateful_analyzer.py   # Core voice detection logic
│   ├── config.py              # Voice archetypes & prompts
│   └── archive/               # Learning examples
└── frontend/
    ├── src/
    │   ├── components/        # React components
    │   ├── extensions/        # TipTap voice highlighting
    │   └── api/               # Backend API client
    └── public/                # Fonts & assets
```

## 🤝 Contributing

This is a personal experimental project, but feel free to fork and adapt!

## 📜 License

MIT

## 🙏 Credits

- Inspired by [Disco Elysium](https://discoelysium.com/)
- Built with [PolyCLI](https://github.com/shuxueshuxue/PolyCLI)
- Fonts: [Excalifont](https://github.com/excalidraw/excalidraw) & Xiaolai
