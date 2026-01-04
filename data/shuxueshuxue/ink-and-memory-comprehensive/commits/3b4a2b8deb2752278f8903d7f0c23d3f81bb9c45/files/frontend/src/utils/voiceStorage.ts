import type { VoiceConfig, StateConfig } from '../types/voice';

const KEY = 'voice-customizations';
const META_PROMPT_KEY = 'meta-prompt';
const STATE_CONFIG_KEY = 'state-config';

// @@@ Default meta prompt: honest, pragmatic advice over role-playing fluff
const DEFAULT_META_PROMPT = `Be honest and pragmatic. This is not actual Disco Elysium - prioritize the user's mental well-being and genuine insight over pure role-playing. Offer constructive perspectives that help with real thinking and writing, not just theatrical commentary.`;

// @@@ Default state configuration
const DEFAULT_STATE_CONFIG: StateConfig = {
  greeting: "How are you feeling today?",
  states: {
    happy: {
      name: "Happy",
      prompt: "The user is feeling positive and energized. Encourage creative exploration and bold ideas."
    },
    ok: {
      name: "OK",
      prompt: "The user is feeling neutral. Provide balanced, steady guidance."
    },
    unhappy: {
      name: "Unhappy",
      prompt: "The user is feeling down. Be gentle, supportive, and focus on small wins."
    }
  }
};

export const getVoices = (): Record<string, VoiceConfig> | null =>
  JSON.parse(localStorage.getItem(KEY) || 'null');

export const saveVoices = (voices: Record<string, VoiceConfig>) =>
  localStorage.setItem(KEY, JSON.stringify(voices));

export const clearVoices = () => localStorage.removeItem(KEY);

export const getMetaPrompt = (): string =>
  localStorage.getItem(META_PROMPT_KEY) || DEFAULT_META_PROMPT;

export const saveMetaPrompt = (prompt: string) =>
  localStorage.setItem(META_PROMPT_KEY, prompt);

export const getStateConfig = (): StateConfig => {
  const stored = localStorage.getItem(STATE_CONFIG_KEY);
  return stored ? JSON.parse(stored) : DEFAULT_STATE_CONFIG;
};

export const saveStateConfig = (config: StateConfig) =>
  localStorage.setItem(STATE_CONFIG_KEY, JSON.stringify(config));
