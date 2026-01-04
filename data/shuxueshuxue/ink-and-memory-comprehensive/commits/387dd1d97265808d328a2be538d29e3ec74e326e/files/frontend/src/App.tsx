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
  const [voices, setVoices] = useState<Voice[]>([]);
  const [voiceTriggers, setVoiceTriggers] = useState<VoiceTrigger[]>([]);
  const [currentText, setCurrentText] = useState<string>('');
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
      const backendVoices = await analyzeText(currentTextValue);
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
      <WritingArea onChange={handleTextChange} triggers={voiceTriggers} />
      <VoicesPanel>
        {voices.map((voice, index) => (
          <VoiceComment
            key={index}
            voice={voice.name}
            text={voice.text}
            icon={voice.icon}
            color={voice.color}
            isTopCard={index === voices.length - 1}
            style={{
              zIndex: index + 1,
              transform: `translateY(${(voices.length - 1 - index) * 30}%)`,
            }}
          />
        ))}
      </VoicesPanel>
      <BinderRings />
    </div>
  );
}

export default App