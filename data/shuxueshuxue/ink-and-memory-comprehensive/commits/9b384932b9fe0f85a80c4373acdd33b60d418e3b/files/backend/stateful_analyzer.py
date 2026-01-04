#!/usr/bin/env python3
"""Stateful voice analyzer that tracks comments across continuous writing."""

from pathlib import Path
from pydantic import BaseModel, Field
from polycli import PolyAgent
from polycli.orchestration import pattern
import config
import re

class VoiceTrigger(BaseModel):
    phrase: str = Field(description="Exact trigger phrase from text (verbatim)")
    voice: str = Field(description="Voice archetype name from the available list")
    comment: str = Field(description="What this voice is saying (as if speaking)")
    icon: str = Field(description="Icon: brain, heart, question, cloud")
    color: str = Field(description="Color: blue, pink, yellow, green, purple")

class VoiceAnalysis(BaseModel):
    voices: list[VoiceTrigger] = Field(description="Detected voice triggers")

class SingleVoiceAnalysis(BaseModel):
    voice: VoiceTrigger | None = Field(description="Single voice trigger", default=None)

class StatefulVoiceAnalyzer:
    """
    Stateful analyzer that:
    1. Tracks existing comments
    2. Prunes comments when trigger text is deleted
    3. Only asks LLM for new comments
    4. Enforces density rules (1 per persona, 1 per sentence)
    """

    def __init__(self):
        self.comments = []  # List of dicts: {phrase, voice, comment, icon, color}
        self.last_text = ""

    def _prune_deleted_comments(self, text: str):
        """Remove comments whose trigger phrases no longer exist in text."""
        self.comments = [
            c for c in self.comments
            if c["phrase"].lower() in text.lower()
        ]

    def _get_sentences(self, text: str) -> list[str]:
        """Split text into sentences (supports English and Chinese)."""
        # @@@ multilingual-sentence-split - English: .!? Chinese: 。！？
        # Also treat newlines as sentence boundaries
        sentences = re.split(r'[.!?。！？]+|\n+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _get_commented_regions(self, text: str) -> list[tuple[int, int]]:
        """Get character ranges that already have comments."""
        regions = []
        for comment in self.comments:
            phrase = comment["phrase"]
            # Find all occurrences (case-insensitive)
            text_lower = text.lower()
            phrase_lower = phrase.lower()
            start = 0
            while True:
                pos = text_lower.find(phrase_lower, start)
                if pos == -1:
                    break
                regions.append((pos, pos + len(phrase)))
                start = pos + 1
        return regions

    def _enforce_density(self, new_comments: list[dict], text: str) -> list[dict]:
        """
        Enforce density rules:
        1. Max 1 comment per persona across whole text
        2. Max 1 persona per sentence
        """
        # Get sentence boundaries
        sentences = self._get_sentences(text)
        sentence_positions = []
        pos = 0
        for sent in sentences:
            start = text.lower().find(sent.lower(), pos)
            if start != -1:
                sentence_positions.append((start, start + len(sent), sent))
                pos = start + len(sent)

        # Track which personas are already used
        used_personas = {c["voice"] for c in self.comments}

        # Track which sentences have comments
        sentence_has_comment = [False] * len(sentence_positions)
        for comment in self.comments:
            phrase_pos = text.lower().find(comment["phrase"].lower())
            if phrase_pos != -1:
                for i, (start, end, _) in enumerate(sentence_positions):
                    if start <= phrase_pos < end:
                        sentence_has_comment[i] = True
                        break

        # Filter new comments
        filtered = []
        for comment in new_comments:
            voice = comment["voice"]
            phrase = comment["phrase"]

            # Rule 1: Only 1 comment per persona
            if voice in used_personas:
                continue

            # Rule 2: Only 1 comment per sentence
            phrase_pos = text.lower().find(phrase.lower())
            if phrase_pos == -1:
                continue

            # Find which sentence this belongs to
            comment_sentence_idx = None
            for i, (start, end, _) in enumerate(sentence_positions):
                if start <= phrase_pos < end:
                    comment_sentence_idx = i
                    break

            if comment_sentence_idx is not None and sentence_has_comment[comment_sentence_idx]:
                continue

            # Accept this comment
            filtered.append(comment)
            used_personas.add(voice)
            if comment_sentence_idx is not None:
                sentence_has_comment[comment_sentence_idx] = True

        return filtered

    @pattern
    def analyze(self, agent: PolyAgent, text: str) -> list[dict]:
        """
        Analyze text and return ALL comments (existing + new).

        Args:
            agent: PolyAgent instance
            text: Current text

        Returns:
            Complete list of all comments
        """
        print(f"\n{'='*60}")
        print(f"📊 Stateful Analysis")
        print(f"   Text length: {len(text)}")
        print(f"   Existing comments: {len(self.comments)}")
        print(f"{'='*60}\n")

        # Step 1: Prune deleted comments
        old_count = len(self.comments)
        self._prune_deleted_comments(text)
        if len(self.comments) < old_count:
            print(f"🗑️  Pruned {old_count - len(self.comments)} deleted comments")

        # Step 2: Check if we need new analysis
        if len(text.strip()) < config.MIN_TEXT_LENGTH:
            print("⏭️  Text too short, returning existing comments")
            return self.comments

        # Check if text changed significantly
        text_diff = abs(len(text) - len(self.last_text))
        if text_diff < 10 and self.comments:
            print(f"⏭️  Text change too small ({text_diff} chars), returning existing")
            return self.comments

        # Step 3: Build prompt with existing comments
        voice_list = "\n".join([
            f"- {name} ({v['icon']}, {v['color']}): {v['tagline']}"
            for name, v in config.VOICE_ARCHETYPES.items()
        ])

        existing_summary = ""
        if self.comments:
            existing_summary = "\n\nEXISTING COMMENTS (do NOT repeat these):\n"
            for c in self.comments:
                existing_summary += f"- {c['voice']} on \"{c['phrase']}\": {c['comment']}\n"

        prompt = f"""You are analyzing internal dialogue using the voice system from Disco Elysium.

In Disco Elysium, thoughts manifest as distinct inner voices - each representing a cognitive skill with its own personality and perspective. These voices interrupt, comment on, and debate each other as the protagonist thinks.

Analyze this text and identify NEW voices that want to comment:

"{text}"

Available voice archetypes:
{voice_list}
{existing_summary}

For each NEW voice you detect:
1. Extract the EXACT phrase that triggered it (word-for-word from the text)
2. Choose the matching voice archetype
3. Write what this voice is saying (as if the voice itself is speaking)
4. Use the voice's designated icon and color

IMPORTANT:
- Maximum {config.MAX_VOICES} NEW voices
- Only identify clearly present voices
- Phrase must be verbatim from text
- Each voice should be distinct
- DO NOT comment on parts that already have comments
- Avoid commenting too close to existing comments
- DO NOT comment on the last sentence if it appears incomplete (no ending punctuation like .!?。！？)
- Write comments in the SAME LANGUAGE as the text being analyzed (if text is Chinese, respond in Chinese; if English, respond in English)
"""

        print("🤖 Calling LLM for new comments...")

        # Choose schema based on config
        if config.SINGLE_COMMENT_MODE:
            schema_cls = SingleVoiceAnalysis
            max_voices_for_prompt = 1
        else:
            schema_cls = VoiceAnalysis
            max_voices_for_prompt = config.MAX_VOICES

        # Update prompt with correct max_voices
        prompt = prompt.replace(f"Maximum {config.MAX_VOICES} NEW voices", f"Maximum {max_voices_for_prompt} NEW voices")

        result = agent.run(
            prompt,
            model=config.MODEL,
            cli="no-tools",
            schema_cls=schema_cls,
            tracked=True
        )

        if not result.is_success or not result.has_data():
            print("❌ LLM failed, returning existing comments")
            return self.comments

        # Extract voices based on schema type
        if config.SINGLE_COMMENT_MODE:
            voice = result.data.get("voice")
            new_voices = [voice] if voice else []
        else:
            new_voices = result.data.get("voices", [])

        print(f"✅ LLM returned {len(new_voices)} new comments")

        # Step 4: Enforce density rules
        filtered_voices = self._enforce_density(new_voices, text)
        print(f"📏 After density filter: {len(filtered_voices)} comments")

        # Step 5: Merge with existing comments
        self.comments.extend(filtered_voices)
        self.last_text = text

        print(f"📝 Total comments: {len(self.comments)}")
        for i, c in enumerate(self.comments):
            print(f"   {i+1}. {c['voice']}: \"{c['phrase'][:30]}...\"")
        print(f"{'='*60}\n")

        return self.comments

# Global instance (shared across all session calls)
global_analyzer = StatefulVoiceAnalyzer()

def analyze_stateful(agent: PolyAgent, text: str) -> list[dict]:
    """Wrapper function that uses global analyzer instance."""
    return global_analyzer.analyze(agent, text)
