# Ink & Memory · English | [中文](README.zh.md)
<p align="center">
  <img src="assets/banner.png" alt="Ink & Memory Banner" width="700"/>
</p>

**Ink & Memory** is a journaling studio inspired by the inner monologues of the video game *Disco Elysium*. It’s a space to write, reflect, and hear your own thoughts echoed back to you through a cast of distinct inner voices. As you type, a council of archetypes chimes in, offering perspective, guidance, and a touch of the absurd.

This is more than just a notebook. It's a daily writing companion that saves your work, organizes your thoughts, and helps you discover the patterns in your own thinking. It supports both English and Chinese, adapting to your language on the fly.

---

## Core Features

### The Writing Experience
At the heart of Ink & Memory is a clean, minimalist writing environment. The editor is designed to be a distraction-free space for your thoughts. As you write, the system automatically saves your work, so you never have to worry about losing a single word.

### The Inner Council
As you write, a council of 16 inner voices will comment on your text, highlighting key phrases and offering their unique perspectives. These voices are inspired by a variety of archetypes, from the analytical "Unpacker" to the gentle "Holder". This feature is powered by a sophisticated AI system that analyzes your writing in real-time.

<p align="center">
  <img src="assets/writing-area.png" alt="Ink & Memory UI" width="700"/>
</p>

### The Timeline and Calendar
Every writing session is automatically saved and organized into a timeline and a calendar. This allows you to easily look back at your past entries, see your progress, and rediscover old ideas.

### Daily Image Generation
Each day, the system automatically generates a unique image based on the content of your writing. This creates a beautiful and evocative visual representation of your thoughts and feelings over time.

### Customizable Decks
The 16 voices are organized into three "decks": the **Introspection Deck**, the **Scholar Deck**, and the **Philosophy Deck**. You can enable or disable decks to customize which voices are active, and you can even create your own decks with your own custom voices.

### Friend Timelines
You can add friends and view their timelines alongside your own. This feature is designed to foster a sense of connection and shared experience, allowing you to see what your friends are writing and thinking about.

---

## Default Voice Decks

Ink & Memory ships with three carefully crafted decks containing 16 voices to get you started. These are designed to offer different perspectives on your writing—but they're just the beginning.

**You're not limited to these voices.** The deck system lets you:
- 🔀 **Fork** any deck to create your own customized version
- ✏️ **Edit** voice personalities, prompts, icons, and colors
- ➕ **Create** entirely new voices from scratch
- 🌐 **Explore** the community store for decks made by other users
- 📤 **Publish** your own decks to share with the community

### The Introspection Deck (Default)
This deck is focused on self-reflection and personal growth.

| Icon | Name | Description |
|---|---|---|
| 🧠 | **The Unpacker** | An analyst who dissects complex situations into clear, understandable structures. |
| ❤️ | **The Holder** | A gentle and supportive companion who validates the user's emotions. |
| 👁️ | **The Mirror** | An observer who points out recurring patterns in the user's behavior and thoughts. |
| 👊 | **The Starter** | A motivator who breaks down tasks into small steps and pushes the user to take action. |
| 🧭 | **The Weaver** | An observer who finds hidden themes and connections in the user's writing. |
| 🎭 | **The Absurdist** | A voice that uses black humor to point out the absurdity of the user's situation. |

### The Scholar Deck
This deck offers academic and intellectual perspectives on your writing.

| Icon | Name | Description |
|---|---|---|
| 🧭 | **The Linguist** | Analyzes your writing from the perspective of linguistic structure, semantics, and pragmatics. |
| 👁️ | **The Painter** | Focuses on aesthetics, visual imagery, and mood. |
| 💡 | **The Physicist** | Applies the laws of physics, mechanics, and energy to your writing. |
| 🧠 | **The Computer Scientist** | Uses algorithms, data structures, and complexity to analyze your thoughts. |
| ❤️ | **The Doctor** | Offers a medical, physiological, and psychological perspective. |
| 🧭 | **The Historian** | Provides historical context, cultural background, and identifies patterns. |

### The Philosophy Deck
This deck examines your writing through the lens of different philosophical schools of thought.

| Icon | Name | Description |
|---|---|---|
| 🛡️ | **The Stoic** | Emphasizes reason, self-control, and the acceptance of the uncontrollable. |
| 💨 | **The Taoist** | Focuses on wu-wei (effortless action), natural flow, and simplicity. |
| 🤔 | **The Existentialist** | Emphasizes choice, freedom, responsibility, and the creation of meaning. |
| 👊 | **The Pragmatist** | Focuses on practical effects, usefulness, and real-world results. |

---

### Creating Your Own Voices

Each voice is defined by:
- **A system prompt** that shapes its personality and perspective
- **An icon** for visual identification
- **A color** that tints its highlights in your text

When you fork a deck, you get full control over all these elements. Want a voice that channels your favorite philosopher? A critic that focuses on narrative structure? A cheerleader for your creative projects? Build it yourself or find it in the community store.

---

## How the Voices Work

As you write, Ink & Memory analyzes your text using a **trace-based energy system**. Here's what happens behind the scenes:

1. **Energy Accumulates** — As you type, the system builds up "energy" based on your writing.
2. **Threshold Triggers** — When enough energy accumulates, the AI analyzes your recent text.
3. **Voices Respond** — Enabled voices scan for phrases that resonate with their personality.
4. **Comments Appear** — Relevant voices highlight phrases and offer their perspective in the margin.

This creates an organic, non-intrusive experience where comments appear naturally as you write, rather than constantly interrupting you.

---

## Technical Architecture

Ink & Memory is built on a modern stack designed for real-time AI interaction:

### Frontend
- **React 19 + TypeScript** — Type-safe, component-based UI.
- **Vite** — Fast dev server and builds.
- **TipTap** — Extensible rich text editing with custom extensions for voice highlights.
- **Custom EditorEngine** — Manages editor state, comments, and chat widgets.

### Backend
- **FastAPI + Python** — High-performance async API server.
- **PolyCLI** — Orchestrates LLM calls with structured prompts and retry logic.
- **Stateless Analyzer** — Core voice analysis engine that keeps context without server-side state.
- **SQLite + WAL** — Reliable storage with concurrent read support.

### AI Integration
- **Multi-model support** — Works with GPT-4, Claude, DeepSeek, and Gemini.
- **Structured outputs** — Pydantic models ensure type-safe LLM responses.
- **Daily image generation** — Automatic visual summaries of your writing.

### Key Design Decisions
- **Deck-based architecture** — Voices are organized into forkable, shareable decks.
- **Parent-child relationships** — Forked decks can sync updates from their source.
- **Community store** — Published decks are discoverable and installable by other users.

---

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- [uv](https://github.com/astral-sh/uv) for Python package management

### Backend
```bash
cd backend
uv venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt

# Create a models.json file for your LLM configuration
# The endpoint and api_key are examples, please use your own
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
The backend will be running at `http://localhost:8765`.

### Frontend
```bash
cd frontend
npm install
npm run dev
```
The frontend will be running at `http://localhost:5173`.

---

## Roadmap

We have a lot of ideas for the future of Ink & Memory. Here are some of the things we're working on:

*   **More Voices and Decks:** We plan to continue expanding the library of voices and decks, offering even more perspectives on your writing.
*   **Richer, More Immersive Experience:** We’re exploring new ways to visualize your entries, your progress, and your connections with friends.
*   **A Platform for Creativity:** We want to make Ink & Memory a place where you can not only write, but also create, share, and collaborate with others.
*   **Mobile App:** We're working on a mobile version of Ink & Memory, so you can write and reflect on the go.

---

## Contributing

Ink & Memory is an open-source project, and we welcome contributions from the community. If you’re interested in contributing, please feel free to fork the repository, make your changes, and submit a pull request.

Here are some of the ways you can contribute:

*   **Report bugs:** If you find a bug, please open an issue on our GitHub repository.
*   **Suggest features:** If you have an idea for a new feature, please open an issue to discuss it.
*   **Write code:** If you're a developer, we'd love for you to help us build new features and fix bugs.
*   **Create new voices and decks:** If you have an idea for a new voice or deck, we'd love to hear it.

---

## License

MIT

## Credits

- Inspired by [Disco Elysium](https://discoelysium.com/)
- Built with [PolyCLI](https://github.com/shuxueshuxue/PolyCLI)
- Fonts: [Excalifont](https://github.com/excalidraw/excalidraw) & Xiaolai
