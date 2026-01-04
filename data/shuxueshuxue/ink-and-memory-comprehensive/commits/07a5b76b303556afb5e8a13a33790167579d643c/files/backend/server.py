#!/usr/bin/env python3
"""Voice analysis server using PolyCLI Session Registry."""

import time
from polycli.orchestration.session_registry import session_def, get_registry
from polycli import PolyAgent
from stateful_analyzer import analyze_stateful
import config

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
    result_voices = analyze_stateful(agent, text, session_id, custom_voices)

    print(f"✅ Got {len(result_voices)} voices")
    for i, v in enumerate(result_voices):
        print(f"   {i+1}. {v.get('voice', 'unknown')}: {v.get('comment', '')[:50]}...")

    result = {
        "voices": result_voices,
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
