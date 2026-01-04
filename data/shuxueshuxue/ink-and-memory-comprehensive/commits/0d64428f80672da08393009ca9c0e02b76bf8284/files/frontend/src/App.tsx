import { useState, useEffect, useRef } from 'react'
import './App.css'
import WritingArea from './components/WritingArea'
import VoicesPanel from './components/VoicesPanel'
import VoiceComment from './components/VoiceComment'
import BinderRings from './components/BinderRings'
import type { VoiceTrigger } from './extensions/VoiceHighlight'
import { analyzeText } from './api/voiceApi'

interface Voice {
  name: string;
  text: string;
  icon: string;
  color: string;
  position: number;
}

// @@@ UUID fallback for non-secure contexts
function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

function App() {
  // @@@ Multi-user support - Generate unique session ID on mount
  const sessionId = useRef(
    typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : generateUUID()
  ).current;

  // @@@ Version logging for cache debugging
  useEffect(() => {
    console.log('🎭 Ink & Memory - Version: v1.1.0-weighted-40');
    console.log('📊 Analysis trigger threshold: 40 weight units (~40 English chars OR ~13 Chinese chars)');
  }, []);

  const [voices, setVoices] = useState<Voice[]>([]);
  const [voiceTriggers, setVoiceTriggers] = useState<VoiceTrigger[]>([]);
  const [currentText, setCurrentText] = useState<string>('');
  const [cursorPosition, setCursorPosition] = useState<number>(0);
  const [focusedVoiceIndex, setFocusedVoiceIndex] = useState<number | undefined>(undefined);
  const currentTextRef = useRef<string>('');
  const lastAnalyzedTextRef = useRef<string>('');
  const isAnalyzingRef = useRef<boolean>(false);

  const detectVoices = (text: string, triggers: VoiceTrigger[]) => {
    const newVoices: Voice[] = [];
    const lowerText = text.toLowerCase();

    triggers.forEach(({ phrase, voice, comment, icon, color }) => {
      const index = lowerText.indexOf(phrase.toLowerCase());
      if (index !== -1) {
        newVoices.push({ name: voice, text: comment, icon, color, position: index });
      }
    });

    // Sort by position in text
    newVoices.sort((a, b) => a.position - b.position);

    setVoices(newVoices);
  };

  // @@@ Track which voice comment to focus based on cursor position
  useEffect(() => {
    if (voices.length === 0) {
      setFocusedVoiceIndex(undefined);
      return;
    }

    // Find the comment whose trigger phrase is closest to cursor
    let closestIndex = 0;
    let closestDistance = Math.abs(voices[0].position - cursorPosition);

    for (let i = 1; i < voices.length; i++) {
      const distance = Math.abs(voices[i].position - cursorPosition);
      if (distance < closestDistance) {
        closestDistance = distance;
        closestIndex = i;
      }
    }

    setFocusedVoiceIndex(closestIndex);
  }, [cursorPosition, voices]);

  // @@@ weighted-character-counting - English chars = 1 weight, CJK chars = 3 weight
  // This elegantly balances both languages: ~30 English chars OR ~10 Chinese chars to trigger
  const getWeightedLength = (text: string): number => {
    let weight = 0;

    for (const char of text) {
      // CJK characters (Chinese, Japanese, Korean)
      if (/[\u4e00-\u9fa5\u3040-\u309f\u30a0-\u30ff]/.test(char)) {
        weight += 3;  // Chinese character = 3 weight
      } else {
        weight += 1;  // English/other = 1 weight
      }
    }

    return weight;
  };

  const analyzeIfNeeded = async () => {
    // Skip if already analyzing
    if (isAnalyzingRef.current) {
      return;
    }

    const currentTextValue = currentTextRef.current;
    const lastTextValue = lastAnalyzedTextRef.current;

    const currentWeight = getWeightedLength(currentTextValue);
    const lastWeight = getWeightedLength(lastTextValue);
    const weightDiff = Math.abs(currentWeight - lastWeight);

    // Only analyze if text changed by >40 weight
    // (~40 English chars OR ~13 Chinese chars OR mixed)
    if (weightDiff <= 40) {
      return;
    }

    isAnalyzingRef.current = true;
    lastAnalyzedTextRef.current = currentTextValue;

    try {
      console.log(`🔍 Calling backend analysis (${weightDiff} weight units changed)...`);
      const backendVoices = await analyzeText(currentTextValue, sessionId);
      console.log(`✅ Got ${backendVoices.length} voices from backend`);

      setVoiceTriggers(backendVoices);
      detectVoices(currentTextValue, backendVoices);
    } catch (error) {
      console.error('❌ Voice analysis failed:', error);
    } finally {
      isAnalyzingRef.current = false;
    }
  };

  // @@@ Polling strategy - Check every 5 seconds (stable interval)
  useEffect(() => {
    const interval = setInterval(analyzeIfNeeded, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleTextChange = (newText: string) => {
    setCurrentText(newText);
    currentTextRef.current = newText;

    // Instantly update display with current triggers
    detectVoices(newText, voiceTriggers);
  };

  // @@@ Re-detect voices when triggers change
  useEffect(() => {
    detectVoices(currentText, voiceTriggers);
  }, [voiceTriggers]);

  return (
    <div className="book-interface">
      <WritingArea
        onChange={handleTextChange}
        triggers={voiceTriggers}
        onCursorChange={setCursorPosition}
      />
      <VoicesPanel focusedVoiceIndex={focusedVoiceIndex}>
        {voices.map((voice, index) => (
          <VoiceComment key={index} voice={voice.name} text={voice.text} icon={voice.icon} color={voice.color} />
        ))}
      </VoicesPanel>
      <BinderRings />
    </div>
  );
}

export default App