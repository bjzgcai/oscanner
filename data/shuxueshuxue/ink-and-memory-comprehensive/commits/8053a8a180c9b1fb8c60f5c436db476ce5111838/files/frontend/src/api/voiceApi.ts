/**
 * API client for voice analysis backend - FastAPI sync API version
 */

import { STORAGE_KEYS } from '../constants/storageKeys';

// nginx proxies /ink-and-memory/api/* to backend (8765)
const API_BASE = '/ink-and-memory';

/**
 * Get auth headers for authenticated requests
 */
function getAuthHeaders(): HeadersInit {
  const token = localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN);
  if (!token) {
    throw new Error('Not authenticated');
  }
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  };
}

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
    thumbnail_base64?: string;  // Thumbnail for image generation
    prompt?: string;  // Image generation prompt
  };
  error?: string;
  exec_id?: string;  // Still included for debugging
}

/**
 * Analyze text and return voices with metadata (sync API - no polling!)
 */
export async function analyzeText(text: string, sessionId: string, voices?: any, appliedComments?: any[], metaPrompt?: string, statePrompt?: string, overlappedPhrases?: string[]) {
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

  if (!data.success) {
    throw new Error(data.error || 'Chat failed');
  }

  return data.result?.response || 'Sorry, I could not respond.';
}

/**
 * Analyze echoes (recurring themes) from all notes (sync API - no polling!)
 */
export async function analyzeEchoes(allNotes: string): Promise<any[]> {
  const response = await fetch(`${API_BASE}/api/analyze-echoes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ all_notes: allNotes })
  });

  const data: SyncResponse = await response.json();

  if (!data.success) {
    throw new Error(data.error || 'Echoes analysis failed');
  }

  return data.result?.echoes || [];
}

/**
 * Analyze traits (personality characteristics) from all notes (sync API - no polling!)
 */
export async function analyzeTraits(allNotes: string): Promise<any[]> {
  const response = await fetch(`${API_BASE}/api/analyze-traits`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ all_notes: allNotes })
  });

  const data: SyncResponse = await response.json();

  if (!data.success) {
    throw new Error(data.error || 'Traits analysis failed');
  }

  return data.result?.traits || [];
}

/**
 * Analyze patterns (behavioral patterns) from all notes (sync API - no polling!)
 */
export async function analyzePatterns(allNotes: string): Promise<any[]> {
  const response = await fetch(`${API_BASE}/api/analyze-patterns`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ all_notes: allNotes })
  });

  const data: SyncResponse = await response.json();

  if (!data.success) {
    throw new Error(data.error || 'Patterns analysis failed');
  }

  return data.result?.patterns || [];
}

/**
 * Generate a daily picture based on user's notes (sync API - no polling!)
 */
export async function generateDailyPicture(allNotes: string): Promise<{ image_base64: string; thumbnail_base64?: string; prompt: string }> {
  const response = await fetch(`${API_BASE}/api/generate-image`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ all_notes: allNotes })
  });

  const data: SyncResponse = await response.json();

  if (!data.success) {
    throw new Error(data.error || 'Image generation failed');
  }

  if (data.result?.image_base64) {
    return {
      image_base64: data.result.image_base64,
      thumbnail_base64: data.result.thumbnail_base64,
      prompt: data.result.prompt || 'Generated from your notes'
    };
  }

  throw new Error('Image generation failed - no image in response');
}

// ========== Authenticated Endpoints (require login) ==========

/**
 * Import localStorage data to database (one-time migration)
 */
export async function importLocalData(data: {
  currentSession?: string;
  calendarEntries?: string;
  dailyPictures?: string;
  voiceCustomizations?: string;
  metaPrompt?: string;
  stateConfig?: string;
  selectedState?: string;
  analysisReports?: string;
  oldDocument?: string;
}): Promise<{ success: boolean; imported: any }> {
  const response = await fetch(`${API_BASE}/api/import-local-data`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(data)
  });

  if (!response.ok) {
    // Handle 413 Payload Too Large (nginx returns HTML, not JSON)
    if (response.status === 413) {
      throw new Error('413: Request too large - your data exceeds the server limit');
    }

    // Try to parse JSON error response
    try {
      const error = await response.json();
      throw new Error(error.detail || 'Import failed');
    } catch {
      // If JSON parsing fails, throw generic error with status
      throw new Error(`Import failed with status ${response.status}`);
    }
  }

  return await response.json();
}

/**
 * Save session to database
 */
export async function saveSession(sessionId: string, editorState: any, name?: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/sessions`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({
      session_id: sessionId,
      editor_state: editorState,
      name
    })
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Save session failed');
  }
}

/**
 * List all sessions
 */
export async function listSessions(): Promise<any[]> {
  const response = await fetch(`${API_BASE}/api/sessions`, {
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'List sessions failed');
  }

  const data = await response.json();
  return data.sessions;
}

/**
 * Get a specific session
 */
export async function getSession(sessionId: string): Promise<any> {
  const response = await fetch(`${API_BASE}/api/sessions/${sessionId}`, {
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Get session failed');
  }

  return await response.json();
}

/**
 * Delete a session
 */
export async function deleteSession(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/sessions/${sessionId}`, {
    method: 'DELETE',
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Delete session failed');
  }
}

/**
 * Save daily picture
 */
export async function saveDailyPicture(date: string, imageBase64: string, prompt: string, thumbnailBase64?: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/pictures`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({
      date,
      image_base64: imageBase64,
      thumbnail_base64: thumbnailBase64,
      prompt
    })
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Save picture failed');
  }
}

/**
 * Get daily pictures (thumbnails only for fast timeline loading)
 */
export async function getDailyPictures(limit: number = 30): Promise<any[]> {
  const response = await fetch(`${API_BASE}/api/pictures?limit=${limit}`, {
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Get pictures failed');
  }

  const data = await response.json();
  return data.pictures;
}

/**
 * Get full resolution image for a specific date (on-demand loading)
 */
export async function getDailyPictureFull(date: string): Promise<string> {
  const response = await fetch(`${API_BASE}/api/pictures/${date}/full`, {
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Get full picture failed');
  }

  const data = await response.json();
  return data.image_base64;
}

/**
 * Save user preferences
 */
export async function savePreferences(preferences: {
  voice_configs?: any;
  meta_prompt?: string;
  state_config?: any;
  selected_state?: string;
}): Promise<void> {
  const response = await fetch(`${API_BASE}/api/preferences`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(preferences)
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Save preferences failed');
  }
}

/**
 * Get user preferences
 */
export async function getPreferences(): Promise<any> {
  const response = await fetch(`${API_BASE}/api/preferences`, {
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Get preferences failed');
  }

  return await response.json();
}

/**
 * Save analysis report
 */
export async function saveAnalysisReport(reportType: string, reportData: any, allNotesText?: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/reports`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({
      report_type: reportType,
      report_data: reportData,
      all_notes_text: allNotesText
    })
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Save report failed');
  }
}

/**
 * Get analysis reports
 */
export async function getAnalysisReports(limit: number = 10): Promise<any[]> {
  const response = await fetch(`${API_BASE}/api/reports?limit=${limit}`, {
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Get reports failed');
  }

  const data = await response.json();
  return data.reports;
}

/**
 * Mark first login as completed (after migration dialog)
 */
export async function markFirstLoginCompleted(): Promise<void> {
  const response = await fetch(`${API_BASE}/api/mark-first-login-completed`, {
    method: 'POST',
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Mark first login completed failed');
  }
}
