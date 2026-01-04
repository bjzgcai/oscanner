#!/usr/bin/env python3
"""Stateless voice analysis server - no state tracking, just returns new comments."""

import time
from polycli.orchestration.session_registry import session_def, get_registry
from polycli import PolyAgent
from stateless_analyzer import analyze_stateless
import config

@session_def(
    name="Analyze Voices",
    description="Get one new voice comment for text",
    params={
        "text": {"type": "str"},
        "session_id": {"type": "str"},
        "voices": {"type": "dict"},
        "applied_comments": {"type": "list"}
    },
    category="Analysis"
)
def analyze_text(text: str, session_id: str, voices: dict = None, applied_comments: list = None):
    """
    Stateless analysis - returns ONE new comment based on text and applied comments.

    Args:
        text: Text to analyze (should be complete sentences only)
        session_id: Session ID (for future use)
        voices: Voice configuration
        applied_comments: List of already applied comments (to avoid duplicates)

    Returns:
        Dictionary with single new voice (or empty list)
    """
    print(f"\n{'='*60}")
    print(f"🎯 Stateless analyze_text() called")
    print(f"   Text: {text[:100]}...")
    print(f"   Applied comments: {len(applied_comments or [])}")
    print(f"{'='*60}\n")

    agent = PolyAgent(id="voice-analyzer")

    # Get voices from stateless analyzer
    result = analyze_stateless(agent, text, applied_comments or [], voices)

    print(f"✅ Returning {result['new_voices_added']} new voice(s)")

    return {
        "voices": result["voices"],
        "new_voices_added": result["new_voices_added"],
        "status": "completed"
    }

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
    print("  - GET /api/default-voices")
    print("\n" + "="*60 + "\n")

    # Keep server running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down...")