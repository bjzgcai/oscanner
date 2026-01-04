#!/usr/bin/env python3
"""Voice detection analyzer using LLM-powered pattern matching."""

from pathlib import Path
from pydantic import BaseModel, Field
from polycli import PolyAgent
from polycli.orchestration import pattern
import config

# Structured output schema
class VoiceTrigger(BaseModel):
    phrase: str = Field(description="Exact trigger phrase from text (verbatim)")
    voice: str = Field(description="Voice archetype name from the available list")
    comment: str = Field(description="What this voice is saying (as if speaking)")
    icon: str = Field(description="Icon: brain, heart, question, cloud")
    color: str = Field(description="Color: blue, pink, yellow, green, purple")

class VoiceAnalysis(BaseModel):
    voices: list[VoiceTrigger] = Field(description="Detected voice triggers")

@pattern
def analyze_voices(agent: PolyAgent, text: str) -> list[dict]:
    """
    Analyze text and detect inner voice triggers.

    Args:
        agent: PolyAgent instance
        text: Text to analyze

    Returns:
        List of voice trigger dicts
    """
    if len(text.strip()) < config.MIN_TEXT_LENGTH:
        return []

    # Build voice list for prompt
    voice_list = "\n".join([
        f"- {name} ({v['icon']}, {v['color']}): {v['tagline']}"
        for name, v in config.VOICE_ARCHETYPES.items()
    ])

    prompt = config.ANALYSIS_PROMPT_TEMPLATE.format(
        text=text,
        voice_list=voice_list,
        max_voices=config.MAX_VOICES
    )

    result = agent.run(
        prompt,
        model=config.MODEL,
        cli="no-tools",
        schema_cls=VoiceAnalysis,
        tracked=True
    )

    if not result.is_success or not result.has_data():
        return []

    return result.data.get("voices", [])
