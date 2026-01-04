import type { VoiceConfig, StateConfig } from '../types/voice';
import { STORAGE_KEYS } from '../constants/storageKeys';

// @@@ Default meta prompt: honest, pragmatic advice over role-playing fluff
const DEFAULT_META_PROMPT = `Be honest and pragmatic. This is not actual Disco Elysium - prioritize the user's mental well-being and genuine insight over pure role-playing. Offer constructive perspectives that help with real thinking and writing, not just theatrical commentary.`;

// @@@ Default state configuration
const DEFAULT_STATE_CONFIG: StateConfig = {
  greeting: "How are you feeling today?",
  states: {
    happy: {
      name: "Happy",
      prompt: "The user is feeling positive and energized. Encourage creative exploration and bold ideas.",
      greeting: "Great to see you in high spirits! Let's capture this energy."
    },
    ok: {
      name: "OK",
      prompt: "The user is feeling neutral. Provide balanced, steady guidance.",
      greeting: "Steady and ready. Let's see what today brings."
    },
    unhappy: {
      name: "Unhappy",
      prompt: "The user is feeling down. Be gentle, supportive, and focus on small wins.",
      greeting: "I'm here with you. Sometimes writing helps make sense of things."
    }
  }
};

export const getVoices = (): Record<string, VoiceConfig> | null =>
  JSON.parse(localStorage.getItem(STORAGE_KEYS.VOICE_CONFIGS) || 'null');

export const saveVoices = (voices: Record<string, VoiceConfig>) =>
  localStorage.setItem(STORAGE_KEYS.VOICE_CONFIGS, JSON.stringify(voices));

export const clearVoices = () => localStorage.removeItem(STORAGE_KEYS.VOICE_CONFIGS);

export const getMetaPrompt = (): string =>
  localStorage.getItem(STORAGE_KEYS.META_PROMPT) || DEFAULT_META_PROMPT;

export const saveMetaPrompt = (prompt: string) =>
  localStorage.setItem(STORAGE_KEYS.META_PROMPT, prompt);

export const getStateConfig = (): StateConfig => {
  const stored = localStorage.getItem(STORAGE_KEYS.STATE_CONFIG);
  return stored ? JSON.parse(stored) : DEFAULT_STATE_CONFIG;
};

export const saveStateConfig = (config: StateConfig) =>
  localStorage.setItem(STORAGE_KEYS.STATE_CONFIG, JSON.stringify(config));
