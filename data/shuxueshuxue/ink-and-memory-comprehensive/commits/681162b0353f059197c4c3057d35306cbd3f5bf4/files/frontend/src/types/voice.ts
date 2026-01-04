export interface VoiceConfig {
  name: string;
  systemPrompt: string;
  enabled: boolean;
  icon: string;
  color: string;
}

export interface UserState {
  name: string;
  prompt: string;
  greeting: string;
}

export interface StateConfig {
  greeting: string;
  states: Record<string, UserState>;
}
