/**
 * API client for voice analysis backend
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

interface TriggerResponse {
  success: boolean;
  exec_id: string;
}

interface StatusResponse {
  exec_id: string;
  status: 'running' | 'completed' | 'failed';
  result?: {
    voices?: Array<{
      phrase: string;
      voice: string;
      comment: string;
      icon: string;
      color: string;
    }>;
    new_voices_added?: number;  // @@@ Number of new voices from this LLM call
    status?: string;
    response?: string;  // For chat responses
    voice_name?: string;  // For chat responses
    echoes?: any[];  // For echoes analysis
    traits?: any[];  // For traits analysis
    patterns?: any[];  // For patterns analysis
  };
  error?: string;
}

/**
 * Trigger voice analysis session
 */
export async function triggerAnalysis(text: string, sessionId: string, voices?: any, appliedComments?: any[], metaPrompt?: string, statePrompt?: string): Promise<string> {
  console.log('📤 Sending trigger request...');
  const response = await fetch(`${API_BASE}/api/trigger`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: 'analyze_text',
      params: { text, session_id: sessionId, voices, applied_comments: appliedComments || [], meta_prompt: metaPrompt || '', state_prompt: statePrompt || '' }
    })
  });

  console.log('📥 Got response, status:', response.status);
  const data: TriggerResponse = await response.json();
  console.log('📋 Parsed JSON:', data);

  if (!data.success) {
    throw new Error('Failed to trigger analysis');
  }

  console.log('✅ Exec ID:', data.exec_id);
  return data.exec_id;
}

/**
 * Get analysis result (polls until completed)
 */
export async function getAnalysisResult(exec_id: string): Promise<StatusResponse['result']> {
  // Poll every 500ms, max 30 seconds
  const maxAttempts = 60;
  let attempts = 0;

  console.log('🔄 Starting to poll for exec_id:', exec_id);

  while (attempts < maxAttempts) {
    console.log(`📊 Polling attempt ${attempts + 1}/${maxAttempts}...`);
    const response = await fetch(`${API_BASE}/api/status/${exec_id}`);
    const data: StatusResponse = await response.json();
    console.log('📊 Status:', data.status);

    if (data.status === 'completed') {
      console.log('✅ Analysis completed!', data.result);
      return data.result;
    }

    if (data.status === 'failed') {
      throw new Error(data.error || 'Analysis failed');
    }

    // Still running, wait and retry
    await new Promise(resolve => setTimeout(resolve, 500));
    attempts++;
  }

  throw new Error('Analysis timeout');
}

/**
 * Analyze text and return voices with metadata (all-in-one)
 */
export async function analyzeText(text: string, sessionId: string, voices?: any, appliedComments?: any[], metaPrompt?: string, statePrompt?: string) {
  const exec_id = await triggerAnalysis(text, sessionId, voices, appliedComments, metaPrompt, statePrompt);
  const result = await getAnalysisResult(exec_id);
  // @@@ Return both voices and new_voices_added for energy refund mechanism
  return {
    voices: result?.voices || [],
    new_voices_added: result?.new_voices_added ?? 0
  };
}

/**
 * Chat with a voice persona
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
  console.log('💬 Sending chat request to backend...');

  // Trigger chat session
  const response = await fetch(`${API_BASE}/api/trigger`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: 'chat_with_voice',
      params: {
        voice_name: voiceName,
        voice_config: voiceConfig,
        conversation_history: conversationHistory,
        user_message: userMessage,
        original_text: originalText || '',
        meta_prompt: metaPrompt || '',
        state_prompt: statePrompt || ''
      }
    })
  });

  const data: TriggerResponse = await response.json();
  if (!data.success) {
    throw new Error('Failed to trigger chat');
  }

  console.log('✅ Chat triggered, exec_id:', data.exec_id);

  // Poll for result
  const result = await getAnalysisResult(data.exec_id);
  console.log('✅ Got chat response:', result);

  return result?.response || 'Sorry, I could not respond.';
}

/**
 * Analyze echoes (recurring themes) from all notes
 */
export async function analyzeEchoes(allNotes: string): Promise<any[]> {
  console.log('🔄 Sending echoes analysis request...');

  const response = await fetch(`${API_BASE}/api/trigger`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: 'analyze_echoes',
      params: { all_notes: allNotes }
    })
  });

  const data: TriggerResponse = await response.json();
  if (!data.success) {
    throw new Error('Failed to trigger echoes analysis');
  }

  const result = await getAnalysisResult(data.exec_id);
  return result?.echoes || [];
}

/**
 * Analyze traits (personality characteristics) from all notes
 */
export async function analyzeTraits(allNotes: string): Promise<any[]> {
  console.log('👤 Sending traits analysis request...');

  const response = await fetch(`${API_BASE}/api/trigger`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: 'analyze_traits',
      params: { all_notes: allNotes }
    })
  });

  const data: TriggerResponse = await response.json();
  if (!data.success) {
    throw new Error('Failed to trigger traits analysis');
  }

  const result = await getAnalysisResult(data.exec_id);
  return result?.traits || [];
}

/**
 * Analyze patterns (behavioral patterns) from all notes
 */
export async function analyzePatterns(allNotes: string): Promise<any[]> {
  console.log('🔍 Sending patterns analysis request...');

  const response = await fetch(`${API_BASE}/api/trigger`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: 'analyze_patterns',
      params: { all_notes: allNotes }
    })
  });

  const data: TriggerResponse = await response.json();
  if (!data.success) {
    throw new Error('Failed to trigger patterns analysis');
  }

  const result = await getAnalysisResult(data.exec_id);
  return result?.patterns || [];
}
