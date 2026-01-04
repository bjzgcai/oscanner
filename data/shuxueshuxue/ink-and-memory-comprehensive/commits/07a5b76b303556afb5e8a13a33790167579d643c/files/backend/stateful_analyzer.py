#!/usr/bin/env python3
"""Stateful voice analyzer that tracks comments across continuous writing."""

from pathlib import Path
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
        # @@@ multilingual-sentence-split - English: .!? Chinese: 。！？，
        # Also treat newlines as sentence boundaries
        sentences = re.split(r'[.!?。！？，]+|\n+', text)
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
        1. Max 1 persona per sentence
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

            # Rule: Only 1 comment per sentence
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
            if comment_sentence_idx is not None:
                sentence_has_comment[comment_sentence_idx] = True

        return filtered

    @pattern
    def analyze(self, agent: PolyAgent, text: str, voices: dict = None) -> list[dict]:
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

        # @@@ Removed debouncing - allow multiple LLM calls on same text
        # This enables energy pool to trigger multiple times and get different comments
        # The LLM prompt includes existing comments, so it will return new ones

        # Step 3: Build prompt with existing comments
        voice_archetypes = voices or config.VOICE_ARCHETYPES
        voice_list = "\n".join([
            f"- {name} ({v['icon']}, {v['color']}): {v['tagline']}"
            for name, v in voice_archetypes.items()
        ])

        # @@@ Build list of occupied sentences AND used personas to guide LLM
        existing_summary = ""
        if self.comments:
            # Get sentence boundaries
            sentences = self._get_sentences(text)
            sentence_positions = []
            pos = 0
            for sent in sentences:
                start = text.lower().find(sent.lower(), pos)
                if start != -1:
                    sentence_positions.append((start, start + len(sent), sent))
                    pos = start + len(sent)

            # Find which sentences are occupied
            occupied_sentences = set()
            for comment in self.comments:
                phrase_pos = text.lower().find(comment["phrase"].lower())
                if phrase_pos != -1:
                    for i, (start, end, sent) in enumerate(sentence_positions):
                        if start <= phrase_pos < end:
                            occupied_sentences.add(i)
                            break

            # Build summary with occupied sentences
            existing_summary = "\n\nEXISTING COMMENTS:\n"
            for c in self.comments:
                existing_summary += f"- {c['voice']} commented on phrase \"{c['phrase']}\": {c['comment']}\n"

            if occupied_sentences:
                # @@@ phrase-vs-sentence - LLM must understand that even though only a phrase is highlighted,
                # the ENTIRE sentence containing that phrase is off-limits for new comments
                existing_summary += f"\n⚠️  OCCUPIED SENTENCES (already have comments, CANNOT comment anywhere in these sentences):\n"
                existing_summary += "NOTE: Even though only a PHRASE is highlighted/commented, the rule is that the ENTIRE SENTENCE containing that phrase is now occupied.\n"
                existing_summary += "You cannot add any new comment to any part of these full sentences:\n\n"
                for i in sorted(occupied_sentences):
                    if i < len(sentence_positions):
                        full_sentence = sentence_positions[i][2]  # Show FULL sentence, no truncation
                        # Find which comment triggered this sentence
                        trigger_phrase = None
                        for c in self.comments:
                            phrase_pos = text.lower().find(c["phrase"].lower())
                            if phrase_pos != -1:
                                start, end, _ = sentence_positions[i]
                                if start <= phrase_pos < end:
                                    trigger_phrase = c["phrase"]
                                    break

                        existing_summary += f"  Sentence {i+1} (triggered by phrase \"{trigger_phrase}\"):\n"
                        existing_summary += f"  \"{full_sentence}\"\n\n"
                existing_summary += "👉 Focus your analysis on NEW/UNCOMMENTED sentences only!\n"

        prompt = f"""You are analyzing internal dialogue using the voice system from Disco Elysium.

In Disco Elysium, thoughts manifest as distinct inner voices - each representing a cognitive skill with its own personality and perspective. These voices interrupt, comment on, and debate each other as the protagonist thinks.

Analyze this text and identify NEW voices that want to comment:

"{text}"

Available voice archetypes:
{voice_list}
{existing_summary}

For each NEW voice you detect:
1. Extract a SHORT phrase that triggered it (word-for-word from the text)
   - The phrase should be SMALL - typically 2-6 words, the most essential/striking part
   - This phrase will be HIGHLIGHTED in the UI - keep it concise!
   - ✅ Good examples: "contemplative walk", "thinking about meaning", "life and death"
   - ❌ Bad examples: (whole sentences, too long, not focused)
2. Choose the matching voice archetype
3. Write what this voice is saying (as if the voice itself is speaking)
4. Use the voice's designated icon and color

CRITICAL DISTINCTION:
- **Phrase** = SHORT essential words you return (what gets highlighted, 2-6 words ideal)
- **Sentence** = The occupation boundary (you can't comment anywhere else in that sentence)
- Even though your phrase is short, it occupies the ENTIRE sentence it appears in

IMPORTANT:
- Maximum {config.MAX_VOICES} NEW voices
- **It's perfectly fine to return NO comment (null) if nothing is worth commenting on**
- Only identify clearly present voices - quality over quantity
- Phrase must be verbatim from text and KEEP IT SHORT (2-6 words typical)
- Each voice should be distinct
- DO NOT comment on parts that already have comments
- Avoid commenting too close to existing comments
- DO NOT comment on the last sentence if it appears incomplete (no ending punctuation like .!?。！？)
- **If all available sentences are already occupied or incomplete, return null**
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

        # @@@ Override LLM's icon/color with actual config values, and use user-friendly name
        for v in new_voices:
            if v and v.get("voice") in voice_archetypes:
                archetype_key = v["voice"]
                v["icon"] = voice_archetypes[archetype_key]["icon"]
                v["color"] = voice_archetypes[archetype_key]["color"]
                # Replace key with user-friendly name (e.g., "Composure" -> "另一个我")
                v["voice"] = voice_archetypes[archetype_key].get("name", archetype_key)

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

# @@@ Multi-user support - Session-based storage
# Each user gets their own analyzer instance, keyed by session_id
_user_analyzers = {}  # session_id -> StatefulVoiceAnalyzer
_last_access = {}     # session_id -> timestamp

# @@@ Session cleanup config
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

def analyze_stateful(agent: PolyAgent, text: str, session_id: str, voices: dict = None) -> list[dict]:
    """Analyze text using session-isolated analyzer."""
    # Cleanup stale sessions before processing
    cleanup_stale_sessions()

    analyzer = get_analyzer(session_id)
    return analyzer.analyze(agent, text, voices)
