/**
 * API client for voice analysis backend - FastAPI sync API version
 */

// nginx proxies /ink-and-memory/api/* to backend (8765)
const API_BASE = '/ink-and-memory';

/**
 * Get default voices from backend
 */
export async function getDefaultVoices(): Promise<any> {
  const response = await fetch(`${API_BASE}/api/default-voices`);
  return await response.json();
}

interface SyncResponse {
  success: boolean;
  result?: {
    voices?: Array<{
      phrase: string;
      voice: string;
      comment: string;
      icon: string;
      color: string;
    }>;
    new_voices_added?: number;
    status?: string;
    response?: string;  // For chat responses
    voice_name?: string;  // For chat responses
    echoes?: any[];  // For echoes analysis
    traits?: any[];  // For traits analysis
    patterns?: any[];  // For patterns analysis
    image_base64?: string;  // For image generation
    prompt?: string;  // Image generation prompt
  };
  error?: string;
  exec_id?: string;  // Still included for debugging
}

/**
 * Analyze text and return voices with metadata (sync API - no polling!)
 */
export async function analyzeText(text: string, sessionId: string, voices?: any, appliedComments?: any[], metaPrompt?: string, statePrompt?: string, overlappedPhrases?: string[]) {
  console.log('📤 Sending analyze request (sync API)...');

  const response = await fetch(`${API_BASE}/api/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      text,
      session_id: sessionId,
      voices,
      applied_comments: appliedComments || [],
      meta_prompt: metaPrompt || '',
      state_prompt: statePrompt || '',
      overlapped_phrases: overlappedPhrases || []
    })
  });

  const data: SyncResponse = await response.json();
  console.log('✅ Got sync response:', data);

  if (!data.success) {
    throw new Error(data.error || 'Analysis failed');
  }

  // Return both voices and new_voices_added for energy refund mechanism
  return {
    voices: data.result?.voices || [],
    new_voices_added: data.result?.new_voices_added ?? 0
  };
}

/**
 * Chat with a voice persona (sync API - no polling!)
 */
export async function chatWithVoice(
  voiceName: string,
  voiceConfig: any,
  conversationHistory: Array<{ role: string; content: string }>,
  userMessage: string,
  originalText?: string,
  metaPrompt?: string,
  statePrompt?: string
): Promise<string> {
  console.log('💬 Sending chat request (sync API)...');

  const response = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      voice_name: voiceName,
      voice_config: voiceConfig,
      conversation_history: conversationHistory,
      user_message: userMessage,
      original_text: originalText || '',
      meta_prompt: metaPrompt || '',
      state_prompt: statePrompt || ''
    })
  });

  const data: SyncResponse = await response.json();
  console.log('✅ Got chat response:', data);

  if (!data.success) {
    throw new Error(data.error || 'Chat failed');
  }

  return data.result?.response || 'Sorry, I could not respond.';
}

/**
 * Analyze echoes (recurring themes) from all notes (sync API - no polling!)
 */
export async function analyzeEchoes(allNotes: string): Promise<any[]> {
  console.log('🔄 Sending echoes analysis request (sync API)...');

  const response = await fetch(`${API_BASE}/api/analyze-echoes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ all_notes: allNotes })
  });

  const data: SyncResponse = await response.json();
  console.log('✅ Got echoes response:', data);

  if (!data.success) {
    throw new Error(data.error || 'Echoes analysis failed');
  }

  return data.result?.echoes || [];
}

/**
 * Analyze traits (personality characteristics) from all notes (sync API - no polling!)
 */
export async function analyzeTraits(allNotes: string): Promise<any[]> {
  console.log('👤 Sending traits analysis request (sync API)...');

  const response = await fetch(`${API_BASE}/api/analyze-traits`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ all_notes: allNotes })
  });

  const data: SyncResponse = await response.json();
  console.log('✅ Got traits response:', data);

  if (!data.success) {
    throw new Error(data.error || 'Traits analysis failed');
  }

  return data.result?.traits || [];
}

/**
 * Analyze patterns (behavioral patterns) from all notes (sync API - no polling!)
 */
export async function analyzePatterns(allNotes: string): Promise<any[]> {
  console.log('🔍 Sending patterns analysis request (sync API)...');

  const response = await fetch(`${API_BASE}/api/analyze-patterns`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ all_notes: allNotes })
  });

  const data: SyncResponse = await response.json();
  console.log('✅ Got patterns response:', data);

  if (!data.success) {
    throw new Error(data.error || 'Patterns analysis failed');
  }

  return data.result?.patterns || [];
}

/**
 * Generate a daily picture based on user's notes (sync API - no polling!)
 */
export async function generateDailyPicture(allNotes: string): Promise<{ image_base64: string; prompt: string }> {
  console.log('🎨 Sending image generation request (sync API)...');

  const response = await fetch(`${API_BASE}/api/generate-image`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ all_notes: allNotes })
  });

  const data: SyncResponse = await response.json();
  console.log('✅ Got image response:', data);

  if (!data.success) {
    throw new Error(data.error || 'Image generation failed');
  }

  if (data.result?.image_base64) {
    return {
      image_base64: data.result.image_base64,
      prompt: data.result.prompt || 'Generated from your notes'
    };
  }

  throw new Error('Image generation failed - no image in response');
}
