# Ink & Memory: Your Mind, Mirrored

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

## The Voices

Ink & Memory features 16 distinct voices, organized into three decks. Each voice has its own unique personality and perspective.

### The Introspection Deck
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

## Technical Deep Dive

Ink & Memory is built on a modern, robust technology stack:

*   **Frontend:** A beautiful and responsive interface built with **React** and **TypeScript**. We use **Vite** for a fast and efficient development experience, and the **TipTap** editor for a smooth and customizable writing surface. A custom **EditorEngine** manages the editor state and communicates with the backend.
*   **Backend:** A powerful and scalable API built with **FastAPI** and **Python**. We use the **PolyCLI** library to orchestrate calls to Large Language Models (LLMs), constructing detailed prompts to generate high-quality, context-aware comments from the different AI personas. A **Stateless Analyzer** is at the core of the "voices" feature.
*   **Database:** A reliable and efficient **SQLite** database stores all your data, including users, sessions, preferences, decks, voices, and friends.

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
