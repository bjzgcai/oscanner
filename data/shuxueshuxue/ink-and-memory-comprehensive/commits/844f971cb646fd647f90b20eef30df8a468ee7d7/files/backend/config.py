"""Voice archetypes configuration - Echo system."""

import json
import os

# Model to use for voice analysis
MODEL = "claude-haiku-4.5"
MODEL = "deepseek-v3.2"

# @@@ Sparsity control
MAX_VOICES = 5
MIN_TEXT_LENGTH = 20
SINGLE_COMMENT_MODE = (
    True  # If True, only add 1 comment per request (gradual accumulation)
)

# @@@ Image generation configuration
def _load_image_api_key() -> str:
    """
    Load image API key from backend/models.json; fail loudly if missing.

    Expected shape:
    {
      "models": {
        "gpt-5": {
          "endpoint": "...",
          "api_key": "...",
          "model": "..."
        },
        ...
      }
    }
    """
    models_path = os.path.join(os.path.dirname(__file__), "models.json")
    if not os.path.exists(models_path):
        raise RuntimeError("models.json not found; image API key unavailable")

    with open(models_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    models = data.get("models") or {}
    for _, cfg in models.items():
        key = cfg.get("api_key")
        if key:
            return key

    raise RuntimeError("No api_key found under models.* in models.json")


IMAGE_API_KEY = _load_image_api_key()
IMAGE_API_ENDPOINT = "https://api.dou.chat/v1"
IMAGE_DESCRIPTION_MODEL = "anthropic/claude-haiku-4.5"
IMAGE_GENERATION_MODEL = "google/gemini-2.5-flash-image-preview"

# Retry configuration for image generation
IMAGE_RETRY_MAX_ATTEMPTS = 3
IMAGE_RETRY_BASE_TIMEOUT = 90  # First attempt: 90s, then +30s per retry
IMAGE_RETRY_TIMEOUT_INCREMENT = 30
IMAGE_MAX_TOKENS = 1000
IMAGE_DESCRIPTION_MAX_TOKENS = 500
IMAGE_DESCRIPTION_TIMEOUT = 120


# @@@ Helper function to load voice prompts from files
def _load_prompt(filename):
    """Load prompt from prompts/ directory."""
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", filename)
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


# Voice archetypes (Echo system - 6 Chinese voice personas)
VOICE_ARCHETYPES = {
    "holder": {
        "name": "接纳者 (The Holder)",
        "systemPrompt": _load_prompt("holder.md"),
        "icon": "heart",
        "color": "pink",
    },
    "unpacker": {
        "name": "拆解者 (The Unpacker)",
        "systemPrompt": _load_prompt("unpacker.md"),
        "icon": "brain",
        "color": "blue",
    },
    "starter": {
        "name": "启动者 (The Starter)",
        "systemPrompt": _load_prompt("starter.md"),
        "icon": "fist",
        "color": "yellow",
    },
    "mirror": {
        "name": "照镜者 (The Mirror)",
        "systemPrompt": _load_prompt("mirror.md"),
        "icon": "eye",
        "color": "green",
    },
    "weaver": {
        "name": "连接者 (The Weaver)",
        "systemPrompt": _load_prompt("weaver.md"),
        "icon": "compass",
        "color": "purple",
    },
    "absurdist": {
        "name": "幽默者 (The Absurdist)",
        "systemPrompt": _load_prompt("absurdist.md"),
        "icon": "masks",
        "color": "pink",
    },
}

# @@@ Analysis prompt for LLM
ANALYSIS_PROMPT_TEMPLATE = """You are analyzing internal dialogue using the voice system from Disco Elysium.

In Disco Elysium, thoughts manifest as distinct inner voices - each representing a cognitive skill with its own personality and perspective. These voices interrupt, comment on, and debate each other as the protagonist thinks.

Analyze this text and identify which voices are speaking:

"{text}"

Available voice archetypes:
{voice_list}

For each voice you detect:
1. Extract the EXACT phrase that triggered it (word-for-word from the text)
2. Choose the matching voice archetype
3. Write what this voice is saying (as if the voice itself is speaking)
4. Use the voice's designated icon and color

IMPORTANT:
- Maximum {max_voices} voices
- Only identify clearly present voices
- Phrase must be verbatim from text
- Each voice should be distinct
"""
