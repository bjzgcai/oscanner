#!/usr/bin/env python3
"""Stateless voice analyzer - receives applied comments, returns one new comment."""

from typing import Optional, List
from pydantic import BaseModel, Field
from polycli import PolyAgent
import config

class VoiceTrigger(BaseModel):
    phrase: str = Field(description="Exact trigger phrase from text (verbatim, 2-4 words, avoid punctuation)")
    voice: str = Field(description="Voice archetype name from the available list")
    comment: str = Field(description="What this voice is saying (as if speaking)")
    icon: str = Field(description="Icon identifier")
    color: str = Field(description="Color identifier")

class SingleVoiceAnalysis(BaseModel):
    voice: Optional[VoiceTrigger] = Field(description="Single voice trigger, or None if nothing to comment")

def analyze_stateless(agent: PolyAgent, text: str, applied_comments: List[dict], voices: dict = None, meta_prompt: str = "", state_prompt: str = "", overlapped_phrases: List[str] = None) -> dict:
    """
    Stateless analysis - receives applied comments, returns ONE new comment.

    Args:
        agent: PolyAgent instance
        text: Text to analyze (completed sentences only)
        applied_comments: List of already applied comments (to avoid duplicates)
        voices: Voice configuration
        meta_prompt: Additional instructions that apply to all voices
        state_prompt: User's current emotional state prompt
        overlapped_phrases: Phrases that were rejected due to overlap (feedback loop)

    Returns:
        Dict with single new voice (or empty list if none)
    """
    overlapped_phrases = overlapped_phrases or []
    print(f"\n{'='*60}")
    print(f"📊 Stateless Analysis")
    print(f"   Text: {text[:100]}...")
    print(f"   Applied comments: {len(applied_comments)}")
    print(f"{'='*60}\n")

    # Use provided voices or defaults
    voice_archetypes = voices or config.VOICE_ARCHETYPES

    # Build voice list for prompt
    voice_list = "\n".join([
        f"- {v.get('name', name)} ({v['icon']}, {v['color']}): {v['tagline']}"
        for name, v in voice_archetypes.items()
    ])

    # Build list of applied comments with their phrases
    existing_summary = ""
    highlighted_phrases = []
    if applied_comments:
        existing_summary = "\n\nALREADY APPLIED COMMENTS (do not repeat or overlap with these):\n"
        for c in applied_comments:
            phrase = c.get('phrase', '')
            highlighted_phrases.append(phrase)
            existing_summary += f"- {c.get('voice', 'Unknown')} on \"{phrase}\": {c.get('comment', '')}\n"
        existing_summary += f"\n👉 These phrases are already highlighted: {highlighted_phrases}\n"
        existing_summary += "👉 Choose a DIFFERENT phrase that does NOT overlap with any of these!\n"

    # @@@ Add overlapped phrases feedback (phrases that were rejected due to overlap)
    if overlapped_phrases:
        existing_summary += f"\n\nREJECTED PHRASES (these overlapped with existing highlights):\n"
        for phrase in overlapped_phrases:
            existing_summary += f"- \"{phrase}\" (REJECTED - do NOT suggest this again)\n"
        existing_summary += f"\n⚠️ AVOID these phrases: {overlapped_phrases}\n"
        existing_summary += "⚠️ The system already tried these and rejected them - choose something completely different!\n"

    prompt = f"""You are analyzing internal dialogue as distinct inner voice personas.

Analyze this text and identify ONE NEW voice that wants to comment:

"{text}"

Available voice personas (ONLY use these):
{voice_list}
{existing_summary}

Find ONE NEW voice to comment:
1. Extract a SHORT phrase (2-4 words) that triggered it - MUST be EXACT text from above
2. Choose a voice persona from the available list
3. Write what this voice is saying (1-2 sentences)

CRITICAL RULES:
- Return ONLY ONE comment
- DO NOT repeat any applied comments
- DO NOT choose phrases that overlap or intersect with already highlighted phrases
- Your chosen phrase must be completely separate from existing highlights
- DO NOT CREATE NEW VOICE NAMES - Only use from the available list
- Return null if nothing is worth commenting on
- Phrase MUST be EXACT substring from text - verify by checking character-by-character
- IGNORE text inside quotation marks ("..." or '...') - only highlight the author's own words
- DO NOT extract phrases from quoted responses, references, or examples
- Only comment on what the AUTHOR wrote, not what they are quoting or citing
- Only comment on complete sentences (ending with .!?。！？)
- Prefer SHORT highlights without punctuation (e.g., "feel anxious" not "I feel anxious.")
- Keep highlights tight and focused - avoid including sentence endings
- Write in the SAME LANGUAGE as the text"""

    # @@@ Add meta prompt if available
    if meta_prompt and meta_prompt.strip():
        prompt += f"""

Additional instructions:
{meta_prompt.strip()}"""

    # @@@ Add state prompt if available
    if state_prompt and state_prompt.strip():
        prompt += f"""

User's current state:
{state_prompt.strip()}"""

    print("🤖 Calling LLM for one new comment...")

    result = agent.run(
        prompt,
        model=config.MODEL,
        cli="no-tools",
        schema_cls=SingleVoiceAnalysis,
        tracked=True
    )

    if not result.is_success or not result.has_data():
        print("❌ LLM failed")
        return {"voices": [], "new_voices_added": 0}

    voice = result.data.get("voice")

    if voice:
        print(f"✅ Got 1 new comment: {voice.get('voice', 'Unknown')}")

        # Map user-defined names back to get correct icon/color
        name_to_key = {}
        for key, v in voice_archetypes.items():
            user_name = v.get("name", key)
            name_to_key[user_name] = key

        # Override icon/color with config values
        llm_voice_name = voice.get("voice")
        archetype_key = name_to_key.get(llm_voice_name)
        if archetype_key and archetype_key in voice_archetypes:
            voice["icon"] = voice_archetypes[archetype_key]["icon"]
            voice["color"] = voice_archetypes[archetype_key]["color"]
            voice["voice"] = llm_voice_name

        return {"voices": [voice], "new_voices_added": 1}
    else:
        print("📭 No new comment")
        return {"voices": [], "new_voices_added": 0}