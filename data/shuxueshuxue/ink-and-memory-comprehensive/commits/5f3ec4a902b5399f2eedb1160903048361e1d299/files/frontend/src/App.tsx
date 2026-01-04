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

function App() {
  // @@@ Multi-user support - Generate unique session ID on mount
  const sessionId = useRef(crypto.randomUUID()).current;

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

  const analyzeIfNeeded = async () => {
    // Skip if already analyzing
    if (isAnalyzingRef.current) {
      return;
    }

    const currentTextValue = currentTextRef.current;
    const textDiff = Math.abs(currentTextValue.length - lastAnalyzedTextRef.current.length);

    // Only analyze if text changed by >10 characters
    if (textDiff <= 10) {
      return;
    }

    isAnalyzingRef.current = true;
    lastAnalyzedTextRef.current = currentTextValue;

    try {
      console.log(`🔍 Calling backend analysis (${textDiff} chars changed)...`);
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