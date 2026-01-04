#!/usr/bin/env python3
"""
Simplified voice analysis server - stateless, clean API
"""

import time
from polycli.orchestration.session_registry import session_def, get_registry
from polycli import PolyAgent
from simple_analyzer import analyze_simple
import config

@session_def(
    name="Analyze Text Simple",
    description="Simple stateless voice analysis",
    params={
        "text": {"type": "str"},
        "session_id": {"type": "str"},
        "voices": {"type": "dict"}
    },
    category="Analysis"
)
def analyze_text(text: str, session_id: str, voices: dict = None):
    """
    Simple stateless analysis - returns voices for given text

    Args:
        text: Text to analyze (should be complete sentences only)
        session_id: Session ID (for future use)
        voices: Voice configuration

    Returns:
        Dictionary with voices array
    """
    print(f"\n{'='*60}")
    print(f"📝 Simple analysis called")
    print(f"   Text length: {len(text)}")
    print(f"   Text: {text[:100]}...")
    print(f"{'='*60}\n")

    agent = PolyAgent(id="voice-analyzer")

    # Get voices from simple analyzer
    result_voices = analyze_simple(agent, text, voices)

    print(f"✅ Found {len(result_voices)} voices")

    return {
        "voices": result_voices,
        "new_voices_added": len(result_voices),  # All are new in stateless mode
        "status": "completed"
    }

@session_def(
    name="Chat with Voice",
    description="Have a conversation with a voice persona",
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
    Chat with a specific voice persona (unchanged from original)
    """
    agent = PolyAgent(id=f"voice-chat-{voice_name.lower()}")

    # Build system prompt for this voice
    system_prompt = f"""You are {voice_name}, an inner voice archetype.

Your character: {voice_config.get('tagline', '')}

Respond in character as {voice_name}. Be concise (1-3 sentences). Stay true to your archetype."""

    if original_text and original_text.strip():
        system_prompt += f"""

Context: The user is writing this text:
---
{original_text.strip()}
---"""

    # Build full prompt with conversation history
    prompt = system_prompt + "\n\nConversation history:\n"

    for msg in conversation_history:
        role_label = "User" if msg["role"] == "user" else voice_name
        prompt += f"\n{role_label}: {msg['content']}"

    prompt += f"\n\nUser: {user_message}\n\n{voice_name}:"

    # Get response from LLM
    result = agent.run(prompt, model="gpt-4o-dou", cli="no-tools", tracked=True)

    if not result.is_success or not result.content:
        response = "..."
    else:
        response = result.content

    return {
        "response": response,
        "voice_name": voice_name
    }

if __name__ == "__main__":
    # Get the global registry
    registry = get_registry()

    # Start the control panel
    print("\n" + "="*60)
    print("🎭 Simple Voice Analysis Server")
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
    print("    Body: {\"session_id\": \"analyze_text\", \"params\": {\"text\": \"...\"}}")
    print("  - GET /api/default-voices")
    print("\n" + "="*60 + "\n")

    # Keep server running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down...")