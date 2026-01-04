import { useState, useRef, useCallback, useEffect } from 'react';
import type { VoiceInspiration } from '../api/voiceApi';
import { getSuggestion } from '../api/voiceApi';
import { getMetaPrompt, getStateConfig } from '../utils/voiceStorage';

interface UseInspirationOptions {
  debounceMs?: number;
  minTextLength?: number;
  animationDurationMs?: number;
}

interface UseInspirationReturn {
  currentInspiration: VoiceInspiration | null;
  isDisappearing: boolean;
  isAppearing: boolean;
  onTextChange: (allText: string, selectedState: string | null) => void;
  clearInspiration: () => void;
  setTextGetter: (getter: () => string) => void;
}

const DEFAULT_OPTIONS: Required<UseInspirationOptions> = {
  debounceMs: 2000,
  minTextLength: 10,
  animationDurationMs: 800,
};

// @@@ Inspiration suggestion hook - handles debounce, appearance/disappearance animations, and result validation
export function useInspiration(options: UseInspirationOptions = {}): UseInspirationReturn {
  const config = { ...DEFAULT_OPTIONS, ...options };

  const [currentInspiration, setCurrentInspiration] = useState<VoiceInspiration | null>(null);
  const [isDisappearing, setIsDisappearing] = useState(false);
  const [, forceRender] = useState(0);

  const prevInspirationRef = useRef<VoiceInspiration | null>(null);
  const timerRef = useRef<number | null>(null);
  const snapshotRef = useRef<string>('');
  const textGetterRef = useRef<(() => string) | null>(null);

  const isAppearing = !isDisappearing &&
    currentInspiration !== null &&
    currentInspiration !== prevInspirationRef.current;

  useEffect(() => {
    if (isDisappearing) {
      const timer = window.setTimeout(() => {
        setCurrentInspiration(null);
        setIsDisappearing(false);
      }, config.animationDurationMs);
      return () => window.clearTimeout(timer);
    }
  }, [isDisappearing, config.animationDurationMs]);

  useEffect(() => {
    if (currentInspiration) {
      setIsDisappearing(false);
      // Ensure a re-render after the ref update so the appearing animation can settle
      requestAnimationFrame(() => {
        prevInspirationRef.current = currentInspiration;
        forceRender(x => x + 1);
      });
    }
  }, [currentInspiration]);

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        window.clearTimeout(timerRef.current);
      }
    };
  }, []);

  const setTextGetter = useCallback((getter: () => string) => {
    textGetterRef.current = getter;
  }, []);

  const clearInspiration = useCallback(() => {
    if (timerRef.current) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    setCurrentInspiration(null);
    setIsDisappearing(false);
    prevInspirationRef.current = null;
  }, []);

  const onTextChange = useCallback((allText: string, selectedState: string | null) => {
    if (currentInspiration) {
      setIsDisappearing(true);
    }

    if (timerRef.current) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }

    if (allText.trim().length < config.minTextLength) {
      return;
    }

    timerRef.current = window.setTimeout(async () => {
      snapshotRef.current = allText;

      try {
        const metaPrompt = getMetaPrompt();
        const stateConfig = getStateConfig();
        const statePrompt = selectedState && stateConfig.states[selectedState]
          ? stateConfig.states[selectedState].prompt
          : '';

        const suggestion = await getSuggestion(allText, metaPrompt, statePrompt);
        const currentText = textGetterRef.current?.() ?? '';

        if (suggestion && currentText === snapshotRef.current) {
          setCurrentInspiration(suggestion);
        }
      } catch (error) {
        console.error('Failed to get inspiration:', error);
      }
    }, config.debounceMs);
  }, [currentInspiration, config.minTextLength, config.debounceMs]);

  return {
    currentInspiration,
    isDisappearing,
    isAppearing,
    onTextChange,
    clearInspiration,
    setTextGetter,
  };
}
