import { useState, useEffect, useRef } from 'react'
import './App.css'
import WritingArea from './components/WritingArea'
import type { EditableTextAreaRef } from './components/EditableTextArea'
import VoicesPanel from './components/VoicesPanel'
import VoiceComment from './components/VoiceComment'
import BinderRings from './components/BinderRings'
import VoiceSettings from './components/VoiceSettings'
import CalendarView from './components/CalendarView'
import AnalysisView from './components/AnalysisView'
import LeftSidebar from './components/LeftSidebar'
import type { VoiceTrigger } from './extensions/VoiceHighlight'
import type { VoiceConfig } from './types/voice'
import { analyzeText, getDefaultVoices } from './api/voiceApi'
import { getVoices } from './utils/voiceStorage'

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

  // @@@ Version logging and initialize default voices from backend
  useEffect(() => {
    console.log('🎭 Ink & Memory - Version: v1.2.0-energy-pool');
    console.log('⚡ Energy pool trigger: accumulate weight changes, trigger at 40 energy');
    console.log('📐 Weights: CJK=2, punctuation(.!?。！？，\\n)=4, other=1');
    console.log('🔒 Single-threaded: max 1 backend request at a time');

    // Fetch default voices from backend
    getDefaultVoices().then(backendVoices => {
      // Convert backend format to frontend VoiceConfig format (keep text names)
      const converted: Record<string, VoiceConfig> = {};
      for (const [name, data] of Object.entries(backendVoices)) {
        const v = data as any;
        converted[name] = {
          name,
          systemPrompt: v.tagline,
          enabled: true,
          icon: v.icon,    // Keep text name: "brain"
          color: v.color   // Keep text name: "blue"
        };
      }
      // Use localStorage if exists, otherwise use backend defaults
      setVoiceConfigs(getVoices() || converted);
    });
  }, [sessionId]);

  const [currentView, setCurrentView] = useState<'writing' | 'settings' | 'calendar' | 'analysis'>('writing');
  const [voices, setVoices] = useState<Voice[]>([]);
  const [voiceTriggers, setVoiceTriggers] = useState<VoiceTrigger[]>([]);
  const [voiceConfigs, setVoiceConfigs] = useState<Record<string, VoiceConfig>>({});
  const [currentText, setCurrentText] = useState<string>('');
  const [currentHTML, setCurrentHTML] = useState<string>('');
  const [cursorPosition, setCursorPosition] = useState<number>(0);
  const [focusedVoiceIndex, setFocusedVoiceIndex] = useState<number | undefined>(undefined);
  const currentTextRef = useRef<string>('');
  const isAnalyzingRef = useRef<boolean>(false);
  const editorRef = useRef<EditableTextAreaRef>(null);

  // @@@ Energy pool trigger system
  const energyRef = useRef<number>(0);
  const lastPollWeightRef = useRef<number>(0);

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

  // @@@ weighted-character-counting with punctuation bonus
  // Sentence separators get high weight to encourage natural boundaries
  const getWeightedLength = (text: string): number => {
    let weight = 0;

    for (const char of text) {
      // Sentence separators (English + Chinese) and newlines = 4 weight
      if (/[.!?。！？\n]/.test(char)) {
        weight += 4;
      }
      // Chinese comma = 0 weight (ignored)
      else if (char === '，') {
        weight += 0;
      }
      // CJK characters (Chinese, Japanese, Korean) = 2 weight
      else if (/[\u4e00-\u9fa5\u3040-\u309f\u30a0-\u30ff]/.test(char)) {
        weight += 2;
      }
      // English/other = 1 weight
      else {
        weight += 1;
      }
    }

    return weight;
  };

  const analyzeIfNeeded = async () => {
    // Skip if already analyzing (single-threaded)
    if (isAnalyzingRef.current) {
      return;
    }

    const currentTextValue = currentTextRef.current;
    const currentWeight = getWeightedLength(currentTextValue);

    // Calculate weight difference since last poll
    const weightDiff = currentWeight - lastPollWeightRef.current;

    // Accumulate energy (only positive changes, ignore deletions)
    if (weightDiff > 0) {
      energyRef.current += weightDiff;
      console.log(`⚡ Energy accumulated: +${weightDiff} → ${energyRef.current} total`);
    }

    // @@@ Update last poll weight ALWAYS (every cycle, even if negative)
    lastPollWeightRef.current = currentWeight;

    // Check if we have enough energy to trigger
    if (energyRef.current < 40) {
      return;
    }

    // Trigger backend request and consume energy
    isAnalyzingRef.current = true;
    energyRef.current -= 40;
    const remainingEnergy = energyRef.current;

    try {
      console.log(`🔍 Calling backend analysis (consumed 40 energy, ${remainingEnergy} remaining)...`);
      console.log(`📝 Current voiceConfigs:`, voiceConfigs);
      // Convert frontend VoiceConfig to backend format
      const backendFormat: Record<string, any> = {};
      for (const [name, cfg] of Object.entries(voiceConfigs)) {
        if (cfg.enabled) {
          backendFormat[name] = {
            name: cfg.name,
            tagline: cfg.systemPrompt,
            icon: cfg.icon,
            color: cfg.color
          };
        }
      }
      console.log(`📤 Sending to backend:`, backendFormat);
      const backendVoices = await analyzeText(currentTextValue, sessionId, backendFormat);
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
  // Must include voiceConfigs in deps so interval uses latest config
  useEffect(() => {
    const interval = setInterval(analyzeIfNeeded, 5000);
    return () => clearInterval(interval);
  }, [voiceConfigs]);

  const handleTextChange = (newText: string) => {
    setCurrentText(newText);
    currentTextRef.current = newText;

    // Instantly update display with current triggers
    detectVoices(newText, voiceTriggers);
  };

  const handleContentChange = (newHTML: string) => {
    setCurrentHTML(newHTML);
  };

  const handleQuote = (voiceName: string, comment: string) => {
    // Format as HTML blockquote for TipTap
    const quoteHTML = `<blockquote><strong>${voiceName}</strong>: ${comment}</blockquote><p></p>`;
    editorRef.current?.insertText(quoteHTML);
  };

  // @@@ Re-detect voices when triggers change
  useEffect(() => {
    detectVoices(currentText, voiceTriggers);
  }, [voiceTriggers]);

  return (
    <>
      <LeftSidebar currentView={currentView} onViewChange={setCurrentView} />
      {currentView === 'writing' && (
        <div className="book-interface">
          <WritingArea
            ref={editorRef}
            onChange={handleTextChange}
            onContentChange={handleContentChange}
            triggers={voiceTriggers}
            onCursorChange={setCursorPosition}
            content={currentHTML}
          />
          <VoicesPanel focusedVoiceIndex={focusedVoiceIndex}>
            {voices.map((voice, index) => (
              <VoiceComment
                key={index}
                voice={voice.name}
                text={voice.text}
                icon={voice.icon}
                color={voice.color}
                onQuote={() => handleQuote(voice.name, voice.text)}
              />
            ))}
          </VoicesPanel>
          <BinderRings />
        </div>
      )}
      {currentView === 'settings' && (
        <div style={{
          position: 'fixed',
          top: 60,
          left: 0,
          right: 0,
          bottom: 0,
          background: '#f5e6d3',
          display: 'flex',
          overflow: 'hidden'
        }}>
          <VoiceSettings
            defaultVoices={voiceConfigs}
            onSave={setVoiceConfigs}
          />
        </div>
      )}
      {currentView === 'calendar' && (
        <div style={{
          position: 'fixed',
          top: 60,
          left: 0,
          right: 0,
          bottom: 0,
          background: '#f5e6d3',
          display: 'flex',
          overflow: 'hidden'
        }}>
          <CalendarView />
        </div>
      )}
      {currentView === 'analysis' && (
        <div style={{
          position: 'fixed',
          top: 60,
          left: 0,
          right: 0,
          bottom: 0,
          background: '#f5e6d3',
          display: 'flex',
          overflow: 'hidden'
        }}>
          <AnalysisView />
        </div>
      )}
    </>
  );
}

export default App