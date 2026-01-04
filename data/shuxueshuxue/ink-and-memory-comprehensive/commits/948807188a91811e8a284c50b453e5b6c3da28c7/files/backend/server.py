#!/usr/bin/env python3
"""Voice analysis server using PolyCLI Session Registry."""

import time
from polycli.orchestration.session_registry import session_def, get_registry
from polycli import PolyAgent
from stateful_analyzer import analyze_stateful
import config

@session_def(
    name="Chat with Voice",
    description="Have a conversation with a specific inner voice persona",
    params={
        "voice_name": {"type": "str"},
        "voice_config": {"type": "dict"},
        "conversation_history": {"type": "list"},
        "user_message": {"type": "str"},
        "original_text": {"type": "str"}
    },
    category="Chat"
)
def chat_with_voice(voice_name: str, voice_config: dict, conversation_history: list, user_message: str, original_text: str = ""):
    """
    Chat with a specific voice persona.

    Args:
        voice_name: Name of the voice (e.g., "Logic", "Drama")
        voice_config: Voice configuration with tagline, icon, color
        conversation_history: Previous messages in the conversation
        user_message: The user's new message

    Returns:
        Dictionary with assistant's response
    """
    print(f"\n{'='*60}")
    print(f"💬 chat_with_voice() called")
    print(f"   Voice: {voice_name}")
    print(f"   User message: {user_message}")
    print(f"   History length: {len(conversation_history)}")
    print(f"{'='*60}\n")

    agent = PolyAgent(id=f"voice-chat-{voice_name.lower()}")

    # @@@ Ensure voice_config is a dict (defensive check)
    if not isinstance(voice_config, dict):
        print(f"⚠️  voice_config is not a dict: {type(voice_config)}, using default")
        voice_config = {"tagline": f"{voice_name} voice from Disco Elysium"}

    # Build system prompt for this voice
    system_prompt = f"""You are {voice_name}, an inner voice archetype from Disco Elysium.

Your character: {voice_config.get('tagline', '')}

Respond in character as {voice_name}. Be concise (1-3 sentences). Stay true to your archetype.
Use the conversation context but focus on your unique perspective."""

    # @@@ Add original writing area text if available
    if original_text and original_text.strip():
        system_prompt += f"""

Context: The user is writing this text:
---
{original_text.strip()}
---

Your initial comment was about this text. Keep this context in mind when responding to the user's questions."""

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
    description="Detect inner voices in text using Disco Elysium archetypes",
    params={
        "text": {"type": "str"},
        "session_id": {"type": "str"},
        "voices": {"type": "dict"}
    },
    category="Analysis"
)
def analyze_text(text: str, session_id: str, voices: dict = None):
    """
    Analyze text and detect inner voice triggers.

    Args:
        text: Text to analyze

    Returns:
        Dictionary with voices array and status
    """
    print(f"\n{'='*60}")
    print(f"🎯 analyze_text() called")
    print(f"   Session ID: {session_id}")
    print(f"   Text length: {len(text)}")
    print(f"   Text preview: {text[:100]}...")
    print(f"{'='*60}\n")

    print("Creating PolyAgent...")
    agent = PolyAgent(id="voice-analyzer")

    print("Calling analyze_stateful pattern...")
    custom_voices = voices or config.VOICE_ARCHETYPES
    analysis_result = analyze_stateful(agent, text, session_id, custom_voices)

    # @@@ analyze_stateful now returns dict with 'voices' and 'new_voices_added'
    result_voices = analysis_result["voices"]
    new_voices_added = analysis_result["new_voices_added"]

    print(f"✅ Got {len(result_voices)} total voices ({new_voices_added} new from this LLM call)")
    for i, v in enumerate(result_voices):
        print(f"   {i+1}. {v.get('voice', 'unknown')}: {v.get('comment', '')[:50]}...")

    result = {
        "voices": result_voices,
        "new_voices_added": new_voices_added,  # Frontend uses this for energy refund
        "status": "completed",
        "text_length": len(text)
    }

    print(f"Returning result: {result}")
    print(f"{'='*60}\n")

    return result

if __name__ == "__main__":
    # Get the global registry (session auto-registered via decorator)
    registry = get_registry()

    # Start the control panel
    print("\n" + "="*60)
    print("🎭 Voice Analysis Server")
    print("="*60)

    # Monkey-patch the handler to add /api/default-voices endpoint
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
    print("    Body: {\"session_id\": \"analyze_text\", \"params\": {\"text\": \"...\"}}")
    print("  - GET /api/sessions (list all sessions)")
    print("  - GET /api/running (list running sessions)")
    print("  - GET /api/status/{exec_id} (get session status)")
    print("\n" + "="*60 + "\n")

    # Keep server running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down...")
