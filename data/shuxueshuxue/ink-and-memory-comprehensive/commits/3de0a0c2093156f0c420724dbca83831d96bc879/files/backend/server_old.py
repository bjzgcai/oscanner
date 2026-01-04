#!/usr/bin/env python3
"""Stateless voice analysis server - no state tracking, just returns new comments."""

import time
from polycli.orchestration.session_registry import session_def, get_registry
from polycli import PolyAgent
from stateless_analyzer import analyze_stateless
import config
from proxy_config import get_image_api_proxies

@session_def(
    name="Chat with Voice",
    description="Have a conversation with a specific inner voice persona",
    params={
        "voice_name": {"type": "str"},
        "voice_config": {"type": "dict"},
        "conversation_history": {"type": "list"},
        "user_message": {"type": "str"},
        "original_text": {"type": "str"},
        "meta_prompt": {"type": "str"},
        "state_prompt": {"type": "str"}
    },
    category="Chat"
)
def chat_with_voice(voice_name: str, voice_config: dict, conversation_history: list, user_message: str, original_text: str = "", meta_prompt: str = "", state_prompt: str = ""):
    """
    Chat with a specific voice persona.

    Args:
        voice_name: Name of the voice (e.g., "Logic", "Drama")
        voice_config: Voice configuration with tagline, icon, color
        conversation_history: Previous messages in the conversation
        user_message: The user's new message
        original_text: The user's original writing text
        meta_prompt: Additional instructions that apply to all voices

    Returns:
        Dictionary with assistant's response
    """
    print(f"\n{'='*60}")
    print(f"💬 chat_with_voice() called")
    print(f"   Voice: {voice_name}")
    print(f"   User message: {user_message}")
    print(f"   History length: {len(conversation_history)}")
    print(f"   Meta prompt: {repr(meta_prompt)[:100]}")
    print(f"   State prompt: {repr(state_prompt)[:100]}")
    print(f"{'='*60}\n")

    agent = PolyAgent(id=f"voice-chat-{voice_name.lower()}")

    # Ensure voice_config is a dict
    if not isinstance(voice_config, dict):
        print(f"⚠️  voice_config is not a dict: {type(voice_config)}, using default")
        voice_config = {"tagline": f"{voice_name} voice from Disco Elysium"}

    # Build system prompt for this voice
    system_prompt = f"""You are {voice_name}, an inner voice archetype from Disco Elysium.

Your character: {voice_config.get('tagline', '')}

Respond in character as {voice_name}. Be concise (1-3 sentences). Stay true to your archetype.
Use the conversation context but focus on your unique perspective."""

    # Add original writing area text if available
    if original_text and original_text.strip():
        system_prompt += f"""

Context: The user is writing this text:
---
{original_text.strip()}
---

Your initial comment was about this text. Keep this context in mind when responding to the user's questions."""

    # Add meta prompt if available
    if meta_prompt and meta_prompt.strip():
        system_prompt += f"""

Additional instructions:
{meta_prompt.strip()}"""

    # @@@ Add state prompt if available (between meta and voice-specific)
    if state_prompt and state_prompt.strip():
        system_prompt += f"""

User's current state:
{state_prompt.strip()}"""

    # Build full prompt with conversation history
    prompt = system_prompt + "\n\nConversation history:\n"

    # Add conversation history
    for msg in conversation_history:
        role_label = "User" if msg["role"] == "user" else voice_name
        prompt += f"\n{role_label}: {msg['content']}"

    # Add user's new message
    prompt += f"\n\nUser: {user_message}\n\n{voice_name}:"

    # Get response from LLM
    result = agent.run(prompt, model="gpt-4o-dou", cli="no-tools", tracked=True)

    if not result.is_success or not result.content:
        response = "..."
    else:
        response = result.content

    print(f"✅ Got response: {response[:100]}...")

    return {
        "response": response,
        "voice_name": voice_name
    }

@session_def(
    name="Analyze Voices",
    description="Get one new voice comment for text",
    params={
        "text": {"type": "str"},
        "session_id": {"type": "str"},
        "voices": {"type": "dict"},
        "applied_comments": {"type": "list"},
        "meta_prompt": {"type": "str"},
        "state_prompt": {"type": "str"}
    },
    category="Analysis"
)
def analyze_text(text: str, session_id: str, voices: dict = None, applied_comments: list = None, meta_prompt: str = "", state_prompt: str = "", overlapped_phrases: list = None):
    """
    Stateless analysis - returns ONE new comment based on text and applied comments.

    Args:
        text: Text to analyze (should be complete sentences only)
        session_id: Session ID (for future use)
        voices: Voice configuration
        applied_comments: List of already applied comments (to avoid duplicates)
        meta_prompt: Additional instructions that apply to all voices
        state_prompt: User's current emotional state prompt
        overlapped_phrases: Phrases that were rejected due to overlap (feedback loop)

    Returns:
        Dictionary with single new voice (or empty list)
    """
    print(f"\n{'='*60}")
    print(f"🎯 Stateless analyze_text() called")
    print(f"   Text: {text[:100]}...")
    print(f"   Applied comments: {len(applied_comments or [])}")
    print(f"   Overlapped phrases: {len(overlapped_phrases or [])}")
    print(f"   Meta prompt: {repr(meta_prompt)[:100]}")
    print(f"   State prompt: {repr(state_prompt)[:100]}")
    print(f"{'='*60}\n")

    agent = PolyAgent(id="voice-analyzer")

    # Get voices from stateless analyzer
    result = analyze_stateless(agent, text, applied_comments or [], voices, meta_prompt, state_prompt, overlapped_phrases or [])

    print(f"✅ Returning {result['new_voices_added']} new voice(s)")

    return {
        "voices": result["voices"],
        "new_voices_added": result["new_voices_added"],
        "status": "completed"
    }

@session_def(
    name="Analyze Echoes",
    description="Find recurring themes and topics in all user notes",
    params={
        "all_notes": {"type": "str"}
    },
    category="Analysis"
)
def analyze_echoes(all_notes: str):
    """Analyze recurring themes and topics across all notes."""
    print(f"\n{'='*60}")
    print(f"🔄 analyze_echoes() called")
    print(f"   Notes length: {len(all_notes)} chars")
    print(f"{'='*60}\n")

    agent = PolyAgent(id="echoes-analyzer")

    prompt = f"""Analyze these personal notes and identify recurring themes, topics, or concerns that keep appearing.

Notes:
---
{all_notes}
---

Find 3-5 echoes (recurring themes) that appear across different entries. For each echo:
- Give it a short title (2-4 words)
- Explain what pattern you see
- Quote 2-3 specific examples from the notes

Format as a JSON array:
[
  {{"title": "...", "description": "...", "examples": ["quote1", "quote2", "quote3"]}},
  ...
]

Return ONLY the JSON array, no other text."""

    result = agent.run(prompt, model="gpt-4o-dou", cli="no-tools", tracked=True)

    if not result.is_success or not result.content:
        return {"echoes": []}

    try:
        import json
        echoes = json.loads(result.content.strip())
        return {"echoes": echoes}
    except:
        return {"echoes": []}

@session_def(
    name="Analyze Traits",
    description="Identify personality traits and characteristics from user notes",
    params={
        "all_notes": {"type": "str"}
    },
    category="Analysis"
)
def analyze_traits(all_notes: str):
    """Analyze personality traits from all notes."""
    print(f"\n{'='*60}")
    print(f"👤 analyze_traits() called")
    print(f"   Notes length: {len(all_notes)} chars")
    print(f"{'='*60}\n")

    agent = PolyAgent(id="traits-analyzer")

    prompt = f"""Analyze these personal notes and identify personality traits and characteristics.

Notes:
---
{all_notes}
---

Identify 4-6 personality traits that are evident from the writing. For each trait:
- Give it a name (1-2 words)
- Rate the strength (1-5)
- Explain why you see this trait with specific examples

Format as a JSON array:
[
  {{"trait": "...", "strength": 4, "evidence": "..."}},
  ...
]

Return ONLY the JSON array, no other text."""

    result = agent.run(prompt, model="gpt-4o-dou", cli="no-tools", tracked=True)

    if not result.is_success or not result.content:
        return {"traits": []}

    try:
        import json
        traits = json.loads(result.content.strip())
        return {"traits": traits}
    except:
        return {"traits": []}

@session_def(
    name="Analyze Patterns",
    description="Identify behavioral patterns and habits from user notes",
    params={
        "all_notes": {"type": "str"}
    },
    category="Analysis"
)
def analyze_patterns(all_notes: str):
    """Analyze behavioral patterns from all notes."""
    print(f"\n{'='*60}")
    print(f"🔍 analyze_patterns() called")
    print(f"   Notes length: {len(all_notes)} chars")
    print(f"{'='*60}\n")

    agent = PolyAgent(id="patterns-analyzer")

    prompt = f"""Analyze these personal notes and identify behavioral patterns or habits.

Notes:
---
{all_notes}
---

Identify 3-5 behavioral patterns or habits. For each pattern:
- Give it a descriptive name
- Describe the pattern
- Note the frequency/context when it appears

Format as a JSON array:
[
  {{"pattern": "...", "description": "...", "frequency": "..."}},
  ...
]

Return ONLY the JSON array, no other text."""

    result = agent.run(prompt, model="gpt-4o-dou", cli="no-tools", tracked=True)

    if not result.is_success or not result.content:
        return {"patterns": []}

    try:
        import json
        patterns = json.loads(result.content.strip())
        return {"patterns": patterns}
    except:
        return {"patterns": []}

@session_def(
    name="Generate Daily Picture",
    description="Generate an artistic image based on user's daily notes",
    params={
        "all_notes": {"type": "str"}
    },
    category="Creative"
)
def generate_daily_picture(all_notes: str):
    """Generate an image based on the essence of user's daily notes.

    Uses a two-step process:
    1. LLM analyzes notes and creates artistic image description
    2. Image generation model creates the image
    """
    print(f"\n{'='*60}")
    print(f"🎨 generate_daily_picture() called")
    print(f"   Notes length: {len(all_notes)} chars")
    print(f"{'='*60}\n")

    import requests

    # @@@ Step 1: Convert notes to artistic image description using Claude Haiku

    description_prompt = f"""Read these personal notes and create a vivid, artistic image description that captures the essence, mood, and themes.

Notes:
---
{all_notes}
---

Create a detailed image description (2-3 sentences) that:
- Captures the emotional tone and atmosphere
- Uses visual metaphors for abstract concepts
- Specifies artistic style (e.g., watercolor, impressionist, minimalist)
- Describes colors, lighting, composition

Be creative and interpretive. Focus on mood and feeling, not literal representation.

Return ONLY the image description, no other text."""

    print("🧠 Creating image description from notes with Claude Haiku...")

    # @@@ Use proxy for GFW bypass (if configured)
    proxies = get_image_api_proxies()

    claude_response = requests.post(
        f"{config.IMAGE_API_ENDPOINT}/chat/completions",
        headers={
            "Authorization": f"Bearer {config.IMAGE_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": config.IMAGE_DESCRIPTION_MODEL,
            "messages": [{"role": "user", "content": description_prompt}],
            "max_tokens": config.IMAGE_DESCRIPTION_MAX_TOKENS
        },
        proxies=proxies,
        timeout=config.IMAGE_DESCRIPTION_TIMEOUT
    )

    if claude_response.status_code != 200:
        return {"image_base64": None, "error": "Failed to create image description"}

    claude_data = claude_response.json()
    image_description = claude_data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()

    if not image_description:
        return {"image_base64": None, "error": "Failed to create image description"}

    print(f"📝 Image description: {image_description}")

    # @@@ Step 2: Generate image from description with retry logic
    url = f"{config.IMAGE_API_ENDPOINT}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.IMAGE_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": config.IMAGE_GENERATION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": image_description
            }
        ],
        "max_tokens": config.IMAGE_MAX_TOKENS
    }

    # @@@ Retry logic with increasing timeouts
    for attempt in range(1, config.IMAGE_RETRY_MAX_ATTEMPTS + 1):
        try:
            timeout_seconds = config.IMAGE_RETRY_BASE_TIMEOUT + (attempt - 1) * config.IMAGE_RETRY_TIMEOUT_INCREMENT
            print(f"🎨 Generating image (attempt {attempt}/{config.IMAGE_RETRY_MAX_ATTEMPTS}, timeout={timeout_seconds}s)...")
            response = requests.post(url, headers=headers, json=payload, proxies=proxies, timeout=timeout_seconds)

            if response.status_code != 200:
                print(f"❌ Error: {response.status_code}")
                if attempt < config.IMAGE_RETRY_MAX_ATTEMPTS:
                    print(f"⏳ Retrying in 2 seconds...")
                    import time
                    time.sleep(2)
                    continue
                return {"image_base64": None, "error": "Image generation failed"}

            data = response.json()

            # Extract image from response
            if 'choices' in data and len(data['choices']) > 0:
                message = data['choices'][0].get('message', {})
                images = message.get('images', [])

                if images:
                    image_data = images[0].get('image_url', {}).get('url', '')

                    if image_data.startswith('data:image/png;base64,'):
                        # Extract base64 data (without the data URI prefix)
                        base64_data = image_data.split(',', 1)[1]

                        print(f"✅ Image generated successfully")
                        print(f"   Size: {len(base64_data)} chars")

                        return {
                            "image_base64": base64_data,
                            "prompt": image_description  # Return the creative description
                        }

            if attempt < config.IMAGE_RETRY_MAX_ATTEMPTS:
                print(f"⚠️ No image in response, retrying...")
                import time
                time.sleep(2)
                continue
            return {"image_base64": None, "error": "No image in response"}

        except Exception as e:
            print(f"❌ Exception on attempt {attempt}: {e}")
            if attempt < config.IMAGE_RETRY_MAX_ATTEMPTS:
                print(f"⏳ Retrying in 2 seconds...")
                import time
                time.sleep(2)
                continue
            return {"image_base64": None, "error": str(e)}

    return {"image_base64": None, "error": "All retry attempts failed"}

if __name__ == "__main__":
    # Get the global registry
    registry = get_registry()

    # Start the control panel
    print("\n" + "="*60)
    print("🎭 Stateless Voice Analysis Server")
    print("="*60)

    # Monkey-patch to add /api/default-voices endpoint
    server, thread = registry.serve_control_panel(port=8765)

    original_do_get = server.RequestHandlerClass.do_GET
    def patched_do_get(handler_self):
        if handler_self.path == "/api/default-voices":
            import json
            body = json.dumps(config.VOICE_ARCHETYPES).encode("utf-8")
            handler_self.send_response(200)
            handler_self.send_header("Content-Type", "application/json")
            handler_self.send_header("Access-Control-Allow-Origin", "*")
            handler_self.end_headers()
            handler_self.wfile.write(body)
        else:
            original_do_get(handler_self)

    server.RequestHandlerClass.do_GET = patched_do_get

    print("\n📚 Available endpoints:")
    print("  - POST /api/trigger")
    print("    Body: {\"session_id\": \"analyze_text\", \"params\": {\"text\": \"...\", \"applied_comments\": [...]}}")
    print("    Body: {\"session_id\": \"chat_with_voice\", \"params\": {\"voice_name\": \"...\", \"user_message\": \"...\", ...}}")
    print("  - GET /api/default-voices")
    print("\n" + "="*60 + "\n")

    # Keep server running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down...")