#!/usr/bin/env python3
"""
Simplified voice analyzer - stateless, no density enforcement
Just returns voices for given text
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from polycli import PolyAgent
import config

class VoiceTrigger(BaseModel):
    phrase: str = Field(description="Exact trigger phrase from text (verbatim, 2-6 words ideal)")
    voice: str = Field(description="Voice archetype name from the available list")
    comment: str = Field(description="What this voice is saying (as if speaking)")
    icon: str = Field(description="Icon identifier")
    color: str = Field(description="Color identifier")

class SingleVoice(BaseModel):
    voice: Optional[VoiceTrigger] = Field(description="Single voice trigger, or None if nothing to comment")

def analyze_simple(agent: PolyAgent, text: str, voices: dict = None) -> List[dict]:
    """
    Simple stateless analysis - just return voices for the given text

    Args:
        agent: PolyAgent instance
        text: Text to analyze
        voices: Voice configuration

    Returns:
        List of voice dictionaries
    """
    # Skip if text too short
    if len(text.strip()) < 20:
        return []

    # Use provided voices or defaults
    voice_archetypes = voices or config.VOICE_ARCHETYPES

    # Build voice list for prompt
    voice_list = "\n".join([
        f"- {v.get('name', name)} ({v['icon']}, {v['color']}): {v['tagline']}"
        for name, v in voice_archetypes.items()
    ])

    prompt = f"""You are analyzing internal dialogue as distinct inner voice personas.

Analyze this text and identify ONE voice that wants to comment:

"{text}"

Available voice personas (ONLY use these):
{voice_list}

Find ONE voice to comment:
1. Extract a SHORT phrase (2-6 words) that triggered it - MUST be EXACT text from above
2. Choose the matching voice persona from the list
3. Write what this voice is saying (1-2 sentences)
4. Use the voice's designated icon and color

Rules:
- Return ONLY ONE voice comment (the most interesting/relevant one)
- Quality over quantity - be selective
- Phrase MUST be exact substring from text
- Only comment on complete sentences (ending with .!?。！？)
- Return null if nothing is worth commenting on
- Respond in the SAME LANGUAGE as the text"""

    # Get analysis from LLM
    result = agent.run(
        prompt,
        model=config.MODEL,
        cli="no-tools",
        schema_cls=SingleVoice,
        tracked=True
    )

    if not result.is_success or not result.has_data():
        return []

    voice = result.data.get("voice")
    voices = [voice] if voice else []

    # Map user-defined names back to get correct icon/color
    name_to_key = {}
    for key, v in voice_archetypes.items():
        user_name = v.get("name", key)
        name_to_key[user_name] = key

    # Update icon/color from config
    for v in voices:
        if v:
            llm_voice_name = v.get("voice")
            archetype_key = name_to_key.get(llm_voice_name)
            if archetype_key and archetype_key in voice_archetypes:
                v["icon"] = voice_archetypes[archetype_key]["icon"]
                v["color"] = voice_archetypes[archetype_key]["color"]
                v["voice"] = llm_voice_name  # Keep user-defined name

    return voices