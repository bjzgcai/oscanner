"""Voice archetypes configuration - Echo system."""

import json
import os
from typing import Any, Dict

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "models.json")


def _load_models_config() -> Dict[str, Any]:
    """Load configuration from models.json."""
    if not os.path.exists(CONFIG_PATH):
        raise RuntimeError(
            "models.json not found; copy backend/models.json.example and fill in your keys"
        )
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise RuntimeError("models.json must contain a JSON object at the top level")
    return data


_CONFIG = _load_models_config()


def _get_roles() -> Dict[str, str]:
    roles = _CONFIG.get("roles")
    if not isinstance(roles, dict) or not roles:
        raise RuntimeError('models.json must define a "roles" object with model names')
    return roles


_ROLES = _get_roles()


def _role_model(role: str) -> str:
    try:
        model_name = _ROLES[role]
    except KeyError as exc:
        raise RuntimeError(f'model role "{role}" missing in models.json "roles"') from exc
    if not isinstance(model_name, str) or not model_name.strip():
        raise RuntimeError(f'model role "{role}" must map to a non-empty model name string')
    return model_name


def _resolve_model_config(model_name: str) -> Dict[str, Any]:
    models = _CONFIG.get("models")
    if not isinstance(models, dict) or not models:
        raise RuntimeError('models.json must define a non-empty "models" object')
    entry = models.get(model_name)
    if not isinstance(entry, dict):
        raise RuntimeError(
            f'model "{model_name}" not found under "models" in models.json'
        )
    return entry


VOICE_ANALYSIS_MODEL = _role_model("voice_analysis")
VOICE_INSPIRATION_MODEL = _role_model("voice_inspiration")
VOICE_CHAT_MODEL = _role_model("voice_chat")
ECHO_ANALYSIS_MODEL = _role_model("echo_analysis")
TRAIT_ANALYSIS_MODEL = _role_model("trait_analysis")
PATTERN_ANALYSIS_MODEL = _role_model("pattern_analysis")
_IMAGE_DESCRIPTION_ROLE_KEY = _role_model("image_description")
_IMAGE_DESCRIPTION_CONFIG = _resolve_model_config(_IMAGE_DESCRIPTION_ROLE_KEY)
IMAGE_DESCRIPTION_MODEL = _IMAGE_DESCRIPTION_CONFIG.get(
    "model", _IMAGE_DESCRIPTION_ROLE_KEY
)


# @@@ Image role resolution - tie model selection to the credentials used for HTTP calls
IMAGE_GENERATION_MODEL = _role_model("image_generation")
_IMAGE_MODEL_CONFIG = _resolve_model_config(IMAGE_GENERATION_MODEL)
IMAGE_GENERATION_MODEL = _IMAGE_MODEL_CONFIG.get("model", IMAGE_GENERATION_MODEL)
IMAGE_API_KEY = _IMAGE_MODEL_CONFIG.get("api_key")
if not IMAGE_API_KEY:
    raise RuntimeError(
        f'api_key missing for image generation model "{IMAGE_GENERATION_MODEL}" in models.json'
    )
_IMAGE_API_SECTION = _CONFIG.get("image_api") or {}
IMAGE_API_ENDPOINT = _IMAGE_MODEL_CONFIG.get("endpoint") or _IMAGE_API_SECTION.get(
    "endpoint"
)
if not IMAGE_API_ENDPOINT:
    raise RuntimeError(
        f'endpoint missing for image generation model "{IMAGE_GENERATION_MODEL}" '
        'and no "image_api.endpoint" fallback provided'
    )

# Retry configuration for image generation
_IMAGE_RETRY = _CONFIG.get("image_retry") or {}
IMAGE_RETRY_MAX_ATTEMPTS = _IMAGE_RETRY.get("max_attempts", 3)
IMAGE_RETRY_BASE_TIMEOUT = _IMAGE_RETRY.get(
    "base_timeout", 90
)  # First attempt: 90s, then +30s per retry
IMAGE_RETRY_TIMEOUT_INCREMENT = _IMAGE_RETRY.get("timeout_increment", 30)
IMAGE_MAX_TOKENS = _IMAGE_RETRY.get("max_tokens", 1000)
IMAGE_DESCRIPTION_MAX_TOKENS = _IMAGE_RETRY.get("description_max_tokens", 500)
IMAGE_DESCRIPTION_TIMEOUT = _IMAGE_RETRY.get("description_timeout", 120)

# @@@ Helper function to load voice prompts from files
def _load_prompt(filename):
    """Load prompt from prompts/ directory."""
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", filename)
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


# Voice archetypes (Echo system - 5 Chinese voice personas)
VOICE_ARCHETYPES = {
    "holder": {
        "name": "接纳者 (The Holder)",
        "systemPrompt": _load_prompt("holder.md"),
        "icon": "heart",
        "color": "pink",
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
