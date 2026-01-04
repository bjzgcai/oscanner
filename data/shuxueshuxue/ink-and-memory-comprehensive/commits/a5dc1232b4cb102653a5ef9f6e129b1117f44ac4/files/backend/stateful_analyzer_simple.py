#!/usr/bin/env python3
"""Simplified stateful voice analyzer - tracks comments but with fewer constraints."""

from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from polycli import PolyAgent
from polycli.orchestration import pattern
import config
import re
import time

class VoiceTrigger(BaseModel):
    phrase: str = Field(description="Exact trigger phrase from text (verbatim)")
    voice: str = Field(description="Voice archetype name from the available list")
    comment: str = Field(description="What this voice is saying (as if speaking)")
    icon: str = Field(description="Icon: brain, heart, question, cloud, masks, eye, fist, lightbulb, shield, wind, fire, compass")
    color: str = Field(description="Color: blue, pink, yellow, green, purple")

class SingleVoiceAnalysis(BaseModel):
    voice: Optional[VoiceTrigger] = Field(description="Single voice trigger", default=None)

class StatefulVoiceAnalyzer:
    """
    Simplified stateful analyzer that:
    1. Tracks APPLIED comments only
    2. Only asks LLM for new comments
    3. Returns ONE comment at a time
    """

    def __init__(self):
        self.applied_comments = []  # List of APPLIED comments only
        self.last_text = ""

    def _prune_deleted_comments(self, text: str):
        """Remove comments whose trigger phrases no longer exist in text."""
        self.comments = [
            c for c in self.comments
            if c["phrase"].lower() in text.lower()
        ]

    @pattern
    def analyze(self, agent: PolyAgent, text: str, voices: dict = None) -> dict:
        """
        Analyze text and return ALL comments (existing + new) plus metadata.
        Simplified version - just returns ONE new comment at a time.
        """
        print(f"\n{'='*60}")
        print(f"📊 Simplified Stateful Analysis")
        print(f"   Text length: {len(text)}")
        print(f"   Existing comments: {len(self.comments)}")
        print(f"{'='*60}\n")

        # Step 1: Prune deleted comments
        old_count = len(self.comments)
        self._prune_deleted_comments(text)
        if len(self.comments) < old_count:
            print(f"🗑️  Pruned {old_count - len(self.comments)} deleted comments")

        # Step 2: Build prompt with existing comments
        voice_archetypes = voices or config.VOICE_ARCHETYPES
        # Use user-defined 'name' (e.g., "吕布") instead of key (e.g., "Composure")
        voice_list = "\n".join([
            f"- {v.get('name', name)} ({v['icon']}, {v['color']}): {v['tagline']}"
            for name, v in voice_archetypes.items()
        ])

        # Build list of existing comments
        existing_summary = ""
        if self.comments:
            existing_summary = "\n\nEXISTING COMMENTS (do not repeat these):\n"
            for c in self.comments:
                existing_summary += f"- {c['voice']} commented on \"{c['phrase']}\": {c['comment']}\n"
            existing_summary += "\n👉 Find something NEW to comment on!\n"

        prompt = f"""You are analyzing internal dialogue as distinct inner voice personas.

Analyze this text and identify ONE NEW voice that wants to comment:

"{text}"

Available voice personas (THESE ARE THE ONLY VOICES YOU CAN USE):
{voice_list}
{existing_summary}

Find ONE NEW voice to comment:
1. Extract a SHORT phrase (2-6 words ideal) that triggered it - MUST be EXACT text from above
2. Choose the matching voice persona from the list
3. Write what this voice is saying (1-2 sentences)
4. Use the voice's designated icon and color

RULES:
- Return ONLY ONE comment (the most interesting/relevant one)
- DO NOT repeat existing comments
- DO NOT CREATE NEW VOICE NAMES - Only use the exact voice names from the available list
- It's perfectly fine to return null if nothing new is worth commenting on
- Phrase MUST be EXACT verbatim substring from text
- Only comment on complete sentences (ending with .!?。！？)
- Write comments in the SAME LANGUAGE as the text"""

        print("🤖 Calling LLM for ONE new comment...")

        result = agent.run(
            prompt,
            model=config.MODEL,
            cli="no-tools",
            schema_cls=SingleVoiceAnalysis,
            tracked=True
        )

        if not result.is_success or not result.has_data():
            print("❌ LLM failed, returning existing comments")
            return {"voices": self.comments, "new_voices_added": 0}

        # Extract single voice
        voice = result.data.get("voice")
        new_voices = [voice] if voice else []

        print(f"✅ LLM returned {'1 new comment' if voice else 'no new comment'}")

        if new_voices:
            # Build name → key mapping (e.g., "吕布" → "Composure")
            name_to_key = {}
            for key, v in voice_archetypes.items():
                user_name = v.get("name", key)
                name_to_key[user_name] = key

            # Override LLM's icon/color with actual config values
            for v in new_voices:
                if v:
                    llm_voice_name = v.get("voice")
                    # Find the key for this name
                    archetype_key = name_to_key.get(llm_voice_name)
                    if archetype_key and archetype_key in voice_archetypes:
                        v["icon"] = voice_archetypes[archetype_key]["icon"]
                        v["color"] = voice_archetypes[archetype_key]["color"]
                        # Keep the user-defined name (already correct from LLM)
                        v["voice"] = llm_voice_name

            # Add to our comments
            self.comments.extend(new_voices)

        self.last_text = text

        print(f"📝 Total comments: {len(self.comments)}")
        for i, c in enumerate(self.comments):
            print(f"   {i+1}. {c['voice']}: \"{c['phrase'][:30]}...\"")
        print(f"{'='*60}\n")

        # Return both voices and metadata about new voices added
        return {
            "voices": self.comments,
            "new_voices_added": len(new_voices)
        }

# Multi-user support - Session-based storage
_user_analyzers = {}  # session_id -> StatefulVoiceAnalyzer
_last_access = {}     # session_id -> timestamp

# Session cleanup config
SESSION_TTL = 3600  # 1 hour - sessions inactive for this long will be cleaned up

def cleanup_stale_sessions():
    """Remove sessions that haven't been accessed in SESSION_TTL seconds."""
    now = time.time()
    stale_sessions = [
        sid for sid, last_time in _last_access.items()
        if now - last_time > SESSION_TTL
    ]

    for sid in stale_sessions:
        print(f"🗑️  Cleaning up stale session: {sid} (inactive for {SESSION_TTL}s)")
        del _user_analyzers[sid]
        del _last_access[sid]

    if stale_sessions:
        print(f"📊 Active sessions: {len(_user_analyzers)}")

def get_analyzer(session_id: str) -> StatefulVoiceAnalyzer:
    """Get or create analyzer for this user session."""
    if session_id not in _user_analyzers:
        print(f"🆕 Creating new analyzer for session: {session_id}")
        _user_analyzers[session_id] = StatefulVoiceAnalyzer()

    # Update last access time
    _last_access[session_id] = time.time()

    return _user_analyzers[session_id]

def analyze_stateful(agent: PolyAgent, text: str, session_id: str, voices: dict = None) -> dict:
    """Analyze text using session-isolated analyzer.

    Returns:
        Dict with 'voices' (list of all comments) and 'new_voices_added' (count of new voices from this LLM call)
    """
    # Cleanup stale sessions before processing
    cleanup_stale_sessions()

    analyzer = get_analyzer(session_id)
    return analyzer.analyze(agent, text, voices)