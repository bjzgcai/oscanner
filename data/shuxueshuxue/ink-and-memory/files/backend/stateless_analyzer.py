#!/usr/bin/env python3
"""Stateless voice analyzer - receives applied comments, returns one new comment."""

from typing import Optional, List
from pydantic import BaseModel, Field
from polycli import PolyAgent
import config


class VoiceTrigger(BaseModel):
    reasoning: str = Field(
        description="Deliberate selection log: candidate phrases considered, verification steps, blacklist checks"
    )
    phrase: str = Field(
        description="Exact trigger phrase from text (verbatim, 2-4 words, avoid punctuation)"
    )
    voice_id: str = Field(
        description="Voice ID from the available list (e.g., 'holder', 'mirror', 'starter')"
    )
    comment: str = Field(description="What this voice is saying (as if speaking)")


class SingleVoiceAnalysis(BaseModel):
    voice: Optional[VoiceTrigger] = Field(
        description="Single voice trigger, or None if nothing to comment"
    )


def analyze_stateless(
    agent: PolyAgent,
    text: str,
    applied_comments: List[dict],
    voices: dict = None,
    meta_prompt: str = "",
    state_prompt: str = "",
    overlapped_phrases: List[str] = None,
    not_found_phrases: List[str] = None,
) -> dict:
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
        not_found_phrases: Phrases that could not be found in text (LLM extraction errors)

    Returns:
        Dict with single new voice (or empty list if none)
    """
    overlapped_phrases = overlapped_phrases or []
    not_found_phrases = not_found_phrases or []
    print(f"\n{'=' * 60}")
    print(f"📊 Stateless Analysis")
    print(f"   Text: {text[:100]}...")
    print(f"   Applied comments: {len(applied_comments)}")
    print(f"   Overlapped phrases: {len(overlapped_phrases)}")
    print(f"   Not found phrases: {len(not_found_phrases)}")
    print(f"{'=' * 60}\n")

    # Use provided voices or defaults
    voice_archetypes = voices or config.VOICE_ARCHETYPES

    # Build voice list for prompt
    voice_list = "\n".join(
        [
            f"- ID: {key} | Name: {v.get('name', key)} | ({v['icon']}, {v['color']})\n  {v.get('systemPrompt', '')}"
            for key, v in voice_archetypes.items()
        ]
    )

    # Build existing conversation context
    conversation_context = ""
    highlighted_phrases = []
    if applied_comments:
        conversation_context = (
            "\n\n════════════════════════════════════════════════════════════════\n"
        )
        conversation_context += (
            "EXISTING CONVERSATION (for context - do NOT extract phrases from here):\n"
        )
        conversation_context += (
            "════════════════════════════════════════════════════════════════\n"
        )
        for c in applied_comments:
            phrase = c.get("phrase", "")
            highlighted_phrases.append(phrase)
            conversation_context += (
                f'\n{c.get("voice", "Unknown")} commented on "{phrase}":\n'
            )
            conversation_context += f"  → {c.get('comment', '')}\n"

        conversation_context += (
            f"\n⚠️ Already highlighted phrases (do NOT overlap): {highlighted_phrases}\n"
        )

    # @@@ Add overlapped phrases feedback (phrases that were rejected due to overlap)
    rejected_section = ""
    if overlapped_phrases:
        rejected_section = (
            "\n\n════════════════════════════════════════════════════════════════\n"
        )
        rejected_section += "REJECTED PHRASES (these were tried but overlapped):\n"
        rejected_section += (
            "════════════════════════════════════════════════════════════════\n"
        )
        for phrase in overlapped_phrases:
            rejected_section += f'  ✗ "{phrase}" - REJECTED, do NOT suggest again\n'
        rejected_section += f"\n⚠️ Do NOT suggest any variation of these phrases!\n"

    not_found_section = ""
    if not_found_phrases:
        not_found_section = (
            "\n\n════════════════════════════════════════════════════════════════\n"
        )
        not_found_section += "HARD BLACKLIST - NOT FOUND (extraction errors, never suggest):\n"
        not_found_section += (
            "════════════════════════════════════════════════════════════════\n"
        )
        for phrase in not_found_phrases:
            not_found_section += (
                f'  ✗ "{phrase}" - NOT FOUND IN TEXT (LLM extraction failure), do NOT suggest again\n'
            )
        not_found_section += (
            "\n⚠️ These phrases failed character-by-character verification. Treat them as forbidden even if they look present. If you cannot find a safe phrase, return null.\n"
        )

    prompt = f"""You are analyzing internal dialogue as distinct inner voice personas.

════════════════════════════════════════════════════════════════
TEXT TO ANALYZE (extract your phrase from THIS text ONLY):
════════════════════════════════════════════════════════════════

"{text}"

════════════════════════════════════════════════════════════════
AVAILABLE VOICE PERSONAS (choose ONE from this list):
════════════════════════════════════════════════════════════════

{voice_list}
{conversation_context}
{rejected_section}
{not_found_section}

════════════════════════════════════════════════════════════════
YOUR TASK:
════════════════════════════════════════════════════════════════

Find ONE NEW voice to comment:

0. Reasoning (think first): list 1-3 candidate substrings from the text, verify each is an exact substring, drop any that appear in rejected/not-found lists, then choose exactly ONE safest remaining candidate. If all are filtered out, generate another small batch and repeat. Only return null when you have exhausted reasonable candidates from the text.
1. Extract a SHORT phrase (2-4 words) from the "TEXT TO ANALYZE" section above
   - MUST be EXACT substring from the quoted text
   - Do NOT extract from the conversation context or rejected phrases
   - Verify character-by-character that your phrase exists in the text

2. Choose a voice ID from the available list above
   - Use the ID field (which might be a complex, nonsensical string), NOT the name
   - Return ONLY the ID in the voice_id field

3. Write what this voice is saying (1-2 sentences)

CRITICAL RULES:
- Return ONLY ONE comment
- Phrase MUST come from "TEXT TO ANALYZE" section ONLY
- DO NOT extract phrases from the "EXISTING CONVERSATION" section
- DO NOT overlap with already highlighted phrases: {highlighted_phrases}
- DO NOT suggest any rejected phrases: {overlapped_phrases}
- DO NOT suggest any not-found phrases: {not_found_phrases}
- HARD BLACKLIST: If a phrase is in either list above, you must not output it. If no safe phrase exists, return null.
- DO NOT CREATE NEW VOICE NAMES - Only use from the available list
- Return null if nothing is worth commenting on
- Write your comment in the EXACT SAME LANGUAGE as the user's text
  * If user writes in Chinese, comment in Chinese
  * If user writes in English, comment in English
  * Match the user's language REGARDLESS of what language the voice's name or system prompt uses

IMPORTANT: Return voice_id only (e.g., "holder"). Do NOT fill voice_name - it will be auto-filled."""

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

    # Re-emphasize hard constraints at the end (higher priority than softer instructions)
    prompt += f"""

FINAL REMINDER (hard constraints):
- DO NOT suggest rejected phrases: {overlapped_phrases}
- DO NOT suggest not-found phrases (extraction failures): {not_found_phrases}
These are hard blacklists. If you cannot comply, return null. These override any softer guidance above.
- Reasoning must show the candidate list, exact-match check, blacklist check, and retries when all candidates are filtered. Only return null after exhausting reasonable options."""

    print("🤖 Calling LLM for one new comment...")

    result = agent.run(
        prompt,
        model=config.VOICE_ANALYSIS_MODEL,
        cli="no-tools",
        schema_cls=SingleVoiceAnalysis,
        tracked=True,
    )

    if not result.is_success or not result.has_data():
        print("❌ LLM failed")
        return {"voices": [], "new_voices_added": 0}

    voice = result.data.get("voice")

    if voice:
        # @@@ Validate LLM returned a valid voice ID
        voice_id = voice.get("voice_id")

        if not voice_id or voice_id not in voice_archetypes:
            print(f"⚠️ Invalid voice ID: {voice_id}, skipping")
            return {"voices": [], "new_voices_added": 0}

        # Get archetype info
        archetype = voice_archetypes[voice_id]

        # Build return object with both ID and name
        result_voice = {
            "phrase": voice.get("phrase"),
            "voice_id": voice_id,  # NEW: ID for lookup
            "voice": archetype.get("name", voice_id),  # KEEP: Name for display
            "comment": voice.get("comment"),
            "icon": archetype["icon"],  # Ensure correct icon
            "color": archetype["color"],  # Ensure correct color
        }

        print(f"✅ Got 1 new comment: {voice_id} ({result_voice['voice']})")
        return {"voices": [result_voice], "new_voices_added": 1}
    else:
        print("📭 No new comment")
        return {"voices": [], "new_voices_added": 0}
