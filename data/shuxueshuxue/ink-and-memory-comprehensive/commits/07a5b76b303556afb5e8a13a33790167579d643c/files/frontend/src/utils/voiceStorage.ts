import type { VoiceConfig } from '../types/voice';

const KEY = 'voice-customizations';

export const getVoices = (): Record<string, VoiceConfig> | null =>
  JSON.parse(localStorage.getItem(KEY) || 'null');

export const saveVoices = (voices: Record<string, VoiceConfig>) =>
  localStorage.setItem(KEY, JSON.stringify(voices));

export const clearVoices = () => localStorage.removeItem(KEY);
