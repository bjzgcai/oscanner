"""Voice archetypes configuration - inspired by Disco Elysium."""

# Model to use for voice analysis
MODEL = "gpt-4o-dou"

# @@@ Sparsity control
MAX_VOICES = 5
MIN_TEXT_LENGTH = 20
SINGLE_COMMENT_MODE = True  # If True, only add 1 comment per request (gradual accumulation)

# Voice archetypes (Disco Elysium skills adapted for general writing)
VOICE_ARCHETYPES = {
    "Logic": {
        "tagline": "Wield raw intellectual power. Deduce the world.",
        "icon": "brain",
        "color": "blue"
    },
    "Rhetoric": {
        "tagline": "Practice the art of persuasion. Enjoy rigorous intellectual discourse.",
        "icon": "brain",
        "color": "purple"
    },
    "Drama": {
        "tagline": "Play the actor. Lie and detect lies.",
        "icon": "question",
        "color": "pink"
    },
    "Conceptualization": {
        "tagline": "Understand creativity. See Art in the world.",
        "icon": "cloud",
        "color": "purple"
    },
    "Volition": {
        "tagline": "Hold yourself together. Keep your Morale up.",
        "icon": "brain",
        "color": "green"
    },
    "Inland Empire": {
        "tagline": "Hunches and gut feelings. Dreams in waking life.",
        "icon": "cloud",
        "color": "purple"
    },
    "Empathy": {
        "tagline": "Understand others. Work your mirror neurons.",
        "icon": "heart",
        "color": "pink"
    },
    "Authority": {
        "tagline": "Intimidate the public. Assert yourself.",
        "icon": "brain",
        "color": "yellow"
    },
    "Electrochemistry": {
        "tagline": "Go to party planet. Love and be loved by drugs.",
        "icon": "heart",
        "color": "pink"
    },
    "Shivers": {
        "tagline": "Raise the hair on your neck. Tune in to the city.",
        "icon": "cloud",
        "color": "blue"
    },
    "Half Light": {
        "tagline": "Let the body take control. Threaten people.",
        "icon": "question",
        "color": "yellow"
    },
    "Perception": {
        "tagline": "See, hear and smell everything. Let no detail go unnoticed.",
        "icon": "brain",
        "color": "green"
    },
    "Composure": {
        "tagline": "Straighten your back. Keep your poker face.",
        "icon": "brain",
        "color": "blue"
    }
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
