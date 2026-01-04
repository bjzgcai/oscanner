/**
 * API client for voice analysis backend - FastAPI sync API version
 */

import { STORAGE_KEYS } from '../constants/storageKeys';
import { LANGUAGE_STORAGE_KEY } from '../i18n';

// ========== Inline Types (workaround for Vite bug) ==========
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
}

export interface StateConfig {
  greeting: string;
  states: Record<string, UserState>;
}
export interface Voice {
  id: string;
  deck_id: string;
  name: string;
  name_zh?: string;
  name_en?: string;
  system_prompt: string;
  icon: string;
  color: string;
  is_system: boolean;
  parent_id?: string;
  owner_id?: number;
  enabled: boolean;
  order_index?: number;
  created_at?: string;
  updated_at?: string;
}

export interface Deck {
  id: string;
  name: string;
  name_zh?: string;
  name_en?: string;
  description?: string;
  description_zh?: string;
  description_en?: string;
  icon?: string;
  color?: string;
  is_system: boolean;
  parent_id?: string;
  owner_id?: number;
  enabled: boolean;
  order_index?: number;
  voice_count?: number;
  voices?: Voice[];
  created_at?: string;
  updated_at?: string;
  published?: boolean;
  author_name?: string;
  install_count?: number;
}

// nginx proxies /ink-and-memory/api/* to backend (8765)
const API_BASE = '/ink-and-memory';

function getUILanguage(): 'en' | 'zh' {
  const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY);
  return stored === 'zh' ? 'zh' : 'en';
}

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
      voice_id: string;  // NEW: Voice ID for lookup
      voice: string;     // Display name
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
 * Analyze text and return voices with metadata (PolyCLI direct call)
 * Backend loads voice configs from database using user_id from JWT token
 */
export async function analyzeText(text: string, sessionId: string, appliedComments?: any[], metaPrompt?: string, statePrompt?: string, overlappedPhrases?: string[]) {
  const token = localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN);

  const response = await fetch(`${API_BASE}/polycli/api/trigger-sync`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
      session_id: 'analyze_text',  // Maps to function name in backend (NOT the display name)
      params: {
        text,
        editor_session_id: sessionId,  // Renamed to avoid conflict with PolyCLI routing session_id
        applied_comments: appliedComments || [],
        meta_prompt: metaPrompt || '',
        state_prompt: statePrompt || '',
        overlapped_phrases: overlappedPhrases || []
      },
      timeout: 60
    })
  });

  const data: SyncResponse = await response.json();

  if (!data.success) {
    console.error('❌ Analysis failed:', data);
    throw new Error(data.error || 'Analysis failed');
  }

  // Return both voices and new_voices_added for energy refund mechanism
  return {
    voices: data.result?.voices || [],
    new_voices_added: data.result?.new_voices_added ?? 0
  };
}

/**
 * Chat with a voice persona (PolyCLI direct call)
 * Backend loads voice config from database using voice_id and user_id from JWT
 */
export async function chatWithVoice(
  voiceId: string,  // Voice ID for database lookup (e.g., "holder", "mirror")
  conversationHistory: Array<{ role: string; content: string }>,
  userMessage: string,
  originalText?: string,
  metaPrompt?: string,
  statePrompt?: string
): Promise<string> {
  const token = localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN);

  const response = await fetch(`${API_BASE}/polycli/api/trigger-sync`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
      session_id: 'chat_with_voice',
      params: {
        voice_id: voiceId,
        conversation_history: conversationHistory,
        user_message: userMessage,
        original_text: originalText || '',
        meta_prompt: metaPrompt || '',
        state_prompt: statePrompt || ''
      },
      timeout: 60
    })
  });

  const data: SyncResponse = await response.json();

  if (!data.success) {
    throw new Error(data.error || 'Chat failed');
  }

  return data.result?.response || 'Sorry, I could not respond.';
}

/**
 * Analyze echoes (recurring themes) from all notes (PolyCLI direct call)
 */
export async function analyzeEchoes(): Promise<any[]> {
  const token = localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN);
  const language = getUILanguage();

  const response = await fetch(`${API_BASE}/polycli/api/trigger-sync`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
      session_id: 'analyze_echoes',
      params: { language },
      timeout: 60
    })
  });

  const data: SyncResponse = await response.json();

  if (!data.success) {
    throw new Error(data.error || 'Echoes analysis failed');
  }

  return data.result?.echoes || [];
}

/**
 * Analyze traits (personality characteristics) from all notes (PolyCLI direct call)
 */
export async function analyzeTraits(): Promise<any[]> {
  const token = localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN);
  const language = getUILanguage();

  const response = await fetch(`${API_BASE}/polycli/api/trigger-sync`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
      session_id: 'analyze_traits',
      params: { language },
      timeout: 60
    })
  });

  const data: SyncResponse = await response.json();

  if (!data.success) {
    throw new Error(data.error || 'Traits analysis failed');
  }

  return data.result?.traits || [];
}

/**
 * Analyze patterns (behavioral patterns) from all notes (PolyCLI direct call)
 */
export async function analyzePatterns(): Promise<any[]> {
  const token = localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN);
  const language = getUILanguage();

  const response = await fetch(`${API_BASE}/polycli/api/trigger-sync`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
      session_id: 'analyze_patterns',
      params: { language },
      timeout: 60
    })
  });

  const data: SyncResponse = await response.json();

  if (!data.success) {
    throw new Error(data.error || 'Patterns analysis failed');
  }

  return data.result?.patterns || [];
}

/**
 * Generate a daily picture based on user's notes (PolyCLI direct call)
 */
export async function generateDailyPicture(targetDate?: string, timezone?: string): Promise<{ image_base64: string; thumbnail_base64?: string; prompt: string; date?: string }> {
  const token = localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN);
  const params: Record<string, any> = {};
  if (targetDate) params.target_date = targetDate;
  if (timezone) params.timezone = timezone;

  const response = await fetch(`${API_BASE}/polycli/api/trigger-sync`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
      session_id: 'generate_daily_picture',
      params,
      timeout: 60
    })
  });

  const data: SyncResponse = await response.json();

  if (!data.success) {
    throw new Error(data.error || 'Image generation failed');
  }

  const res: any = data.result || {};
  if (res.image_base64) {
    return {
      image_base64: res.image_base64,
      thumbnail_base64: res.thumbnail_base64,
      prompt: res.prompt || 'Generated from your notes',
      date: res.date
    };
  }

  throw new Error(res.error || res.reason || 'Image generation failed - no image in response');
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

type SessionRangeOptions = {
  startDate?: string;
  endDate?: string;
  limit?: number;
};

/**
 * List sessions metadata, optionally scoped to a date range.
 */
export async function listSessions(timezone?: string, options: SessionRangeOptions = {}): Promise<any[]> {
  const params = new URLSearchParams();
  if (timezone) params.append('timezone', timezone);
  if (options.startDate) params.append('start_date', options.startDate);
  if (options.endDate) params.append('end_date', options.endDate);
  const endpoint = options.startDate || options.endDate ? '/api/sessions/range' : '/api/sessions';
  const query = params.toString();

  const response = await fetch(`${API_BASE}${endpoint}${query ? `?${query}` : ''}`, {
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'List sessions failed');
  }

  const data = await response.json();
  return data.sessions;
}

export async function fetchSessionsAggregate(timezone: string): Promise<{
  stats: { total_days: number; total_entries: number; total_words: number };
  sessions: Array<{ id: string; name?: string; created_at?: string; updated_at?: string; has_text: boolean; word_count: number }>;
  timezone: string;
}> {
  const response = await fetch(`${API_BASE}/api/sessions/aggregate?timezone=${encodeURIComponent(timezone)}`, {
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Aggregate sessions failed');
  }

  return await response.json();
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
 * Fetch multiple sessions (with editor_state) in a single request.
 */
export async function getSessionsBatch(sessionIds: string[]): Promise<any[]> {
  if (!sessionIds || sessionIds.length === 0) return [];

  const response = await fetch(`${API_BASE}/api/sessions/batch`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ ids: sessionIds })
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Batch session fetch failed');
  }

  const data = await response.json();
  return data.sessions;
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
type PictureRangeOptions = {
  startDate?: string;
  endDate?: string;
  limit?: number;
};

export async function getDailyPictures(limit: number = 30, options: PictureRangeOptions = {}): Promise<any[]> {
  const params = new URLSearchParams();
  params.append('limit', String(options.limit ?? limit));
  if (options.startDate) params.append('start_date', options.startDate);
  if (options.endDate) params.append('end_date', options.endDate);
  const endpoint = options.startDate || options.endDate ? '/api/pictures/range' : '/api/pictures';
  const query = params.toString();

  const response = await fetch(`${API_BASE}${endpoint}${query ? `?${query}` : ''}`, {
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
  timezone?: string;
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
 * Get writing inspiration from a voice persona
 */
export interface VoiceInspiration {
  inspiration: string;
  voice: string;
  voice_key: string;
  icon: string;
  color: string;
}

export async function getSuggestion(text: string, metaPrompt?: string, statePrompt?: string): Promise<VoiceInspiration | null> {
  const token = localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN);

  const response = await fetch(`${API_BASE}/polycli/api/trigger-sync`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
      session_id: 'get_writing_suggestion',
      params: {
        text,
        meta_prompt: metaPrompt || '',
        state_prompt: statePrompt || ''
      },
      timeout: 60
    })
  });

  if (!response.ok) {
    console.error('Suggestion request failed');
    return null;
  }

  const data = await response.json();

  // PolyCLI returns {success: true, result: {...}}
  if (data.success && data.result?.inspiration) {
    return {
      inspiration: data.result.inspiration,
      voice: data.result.voice,
      voice_key: data.result.voice_key,
      icon: data.result.icon,
      color: data.result.color
    };
  }

  return null;
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

// ========== Deck System API ==========

/**
 * List all decks (includes system decks + user's own decks)
 */
export async function listDecks(published?: boolean): Promise<Deck[]> {
  const url = published
    ? `${API_BASE}/api/decks?published=true`
    : `${API_BASE}/api/decks`;

  const response = await fetch(url, {
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'List decks failed');
  }

  const data = await response.json();
  return data.decks;
}

/**
 * Get a specific deck with all its voices
 */
export async function getDeck(deckId: string): Promise<Deck> {
  const response = await fetch(`${API_BASE}/api/decks/${deckId}`, {
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Get deck failed');
  }

  return await response.json();
}

/**
 * Create a new deck
 */
export async function createDeck(data: {
  name: string;
  name_zh?: string;
  name_en?: string;
  description?: string;
  description_zh?: string;
  description_en?: string;
  icon?: string;
  color?: string;
}): Promise<{ deck_id: string }> {
  const response = await fetch(`${API_BASE}/api/decks`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(data)
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Create deck failed');
  }

  return await response.json();
}

/**
 * Update a deck (only user-owned decks)
 */
export async function updateDeck(deckId: string, data: {
  name?: string;
  name_zh?: string;
  name_en?: string;
  description?: string;
  description_zh?: string;
  description_en?: string;
  icon?: string;
  color?: string;
  enabled?: boolean;
  order_index?: number;
}): Promise<void> {
  const response = await fetch(`${API_BASE}/api/decks/${deckId}`, {
    method: 'PUT',
    headers: getAuthHeaders(),
    body: JSON.stringify(data)
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Update deck failed');
  }
}

/**
 * Delete a deck (only user-owned decks, cascades to voices)
 */
export async function deleteDeck(deckId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/decks/${deckId}`, {
    method: 'DELETE',
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Delete deck failed');
  }
}

/**
 * Fork a deck (copy-on-write: creates user-owned copy of system deck)
 */
export async function forkDeck(deckId: string): Promise<{ deck_id: string }> {
  const response = await fetch(`${API_BASE}/api/decks/${deckId}/fork`, {
    method: 'POST',
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Fork deck failed');
  }

  return await response.json();
}

/**
 * Sync deck with parent template (force overwrites local changes)
 */
export async function syncDeck(deckId: string): Promise<{ success: boolean; synced_voices: number }> {
  const response = await fetch(`${API_BASE}/api/decks/${deckId}/sync`, {
    method: 'POST',
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Sync deck failed');
  }

  return await response.json();
}

/**
 * Publish/unpublish a deck to community store
 * @@@ Warning: Publishing breaks parent_id chain (deck becomes standalone)
 */
export async function publishDeck(deckId: string): Promise<{ success: boolean; published: boolean }> {
  const response = await fetch(`${API_BASE}/api/decks/${deckId}/publish`, {
    method: 'POST',
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Publish deck failed');
  }

  return await response.json();
}

/**
 * Create a new voice in a deck
 */
export async function createVoice(data: {
  deck_id: string;
  name: string;
  name_zh?: string;
  name_en?: string;
  system_prompt: string;
  icon: string;
  color: string;
}): Promise<{ voice_id: string }> {
  const response = await fetch(`${API_BASE}/api/voices`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(data)
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Create voice failed');
  }

  return await response.json();
}

/**
 * Update a voice (only voices in user-owned decks)
 */
export async function updateVoice(voiceId: string, data: {
  name?: string;
  name_zh?: string;
  name_en?: string;
  system_prompt?: string;
  icon?: string;
  color?: string;
  enabled?: boolean;
  order_index?: number;
}): Promise<void> {
  const response = await fetch(`${API_BASE}/api/voices/${voiceId}`, {
    method: 'PUT',
    headers: getAuthHeaders(),
    body: JSON.stringify(data)
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Update voice failed');
  }
}

/**
 * Delete a voice (only voices in user-owned decks)
 */
export async function deleteVoice(voiceId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/voices/${voiceId}`, {
    method: 'DELETE',
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Delete voice failed');
  }
}

/**
 * Fork a voice to a target deck (copy-on-write: creates user-owned copy)
 */
export async function forkVoice(voiceId: string, targetDeckId: string): Promise<{ voice_id: string }> {
  const response = await fetch(`${API_BASE}/api/voices/${voiceId}/fork`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ target_deck_id: targetDeckId })
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Fork voice failed');
  }

  return await response.json();
}

// ========== Voice Config Loading ==========

/**
 * @@@ Load all enabled voices from all enabled decks and convert to VoiceConfig format
 * This bridges the new deck system with the existing voice analysis system
 */
export async function loadVoicesFromDecks(): Promise<Record<string, VoiceConfig>> {
  try {
    const decks = await listDecks();
    const voiceConfigs: Record<string, VoiceConfig> = {};

    // Load voices from each enabled deck
    for (const deck of decks) {
      if (!deck.enabled) continue;

      try {
        const fullDeck = await getDeck(deck.id);

        if (fullDeck.voices) {
          for (const voice of fullDeck.voices) {
            if (!voice.enabled) continue;

            // @@@ Convert Voice to VoiceConfig format
            // Key by voice.id (UUID) so backend can find it in database
            voiceConfigs[voice.id] = {
              name: voice.name,
              systemPrompt: voice.system_prompt,
              enabled: voice.enabled,
              icon: voice.icon,
              color: voice.color
            };
          }
        }
      } catch (err) {
        console.error(`Failed to load voices from deck ${deck.id}:`, err);
        // Continue loading other decks even if one fails
      }
    }

    return voiceConfigs;
  } catch (err) {
    console.error('Failed to load voices from decks:', err);
    // Return empty object if loading fails - app can fall back to localStorage
    return {};
  }
}

// ========== Friend System API ==========

export interface FriendInvite {
  code: string;
  expires_at: string;
  created_at: string;
}

export interface FriendRequest {
  id: number;
  requester_id: number;
  requester_name: string;
  requester_email: string;
  created_at: string;
}

export interface Friend {
  id: number;
  user_id: number;
  friend_id: number;
  friend_name: string;
  friend_email: string;
  created_at: string;
}

/**
 * Generate a new friend invite code (6 chars, 7 days validity)
 */
export async function generateInviteCode(): Promise<FriendInvite> {
  const response = await fetch(`${API_BASE}/api/friends/invite/generate`, {
    method: 'POST',
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Generate invite code failed');
  }

  return await response.json();
}

/**
 * Use an invite code to send a friend request
 */
export async function useInviteCode(code: string): Promise<{ success: boolean; message: string }> {
  const response = await fetch(`${API_BASE}/api/friends/invite/use`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ code })
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Use invite code failed');
  }

  return await response.json();
}

/**
 * Get all pending friend requests for current user
 */
export async function getFriendRequests(): Promise<FriendRequest[]> {
  const response = await fetch(`${API_BASE}/api/friends/requests`, {
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Get friend requests failed');
  }

  const data = await response.json();
  return data.requests;
}

/**
 * Accept a friend request
 */
export async function acceptFriendRequest(requestId: number): Promise<{ success: boolean }> {
  const response = await fetch(`${API_BASE}/api/friends/requests/${requestId}/accept`, {
    method: 'POST',
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Accept friend request failed');
  }

  return await response.json();
}

/**
 * Reject a friend request
 */
export async function rejectFriendRequest(requestId: number): Promise<{ success: boolean }> {
  const response = await fetch(`${API_BASE}/api/friends/requests/${requestId}/reject`, {
    method: 'POST',
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Reject friend request failed');
  }

  return await response.json();
}

/**
 * Get all accepted friends
 */
export async function getFriends(): Promise<Friend[]> {
  const response = await fetch(`${API_BASE}/api/friends`, {
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Get friends failed');
  }

  const data = await response.json();
  return data.friends;
}

/**
 * Remove a friend
 */
export async function removeFriend(friendId: number): Promise<{ success: boolean }> {
  const response = await fetch(`${API_BASE}/api/friends/${friendId}`, {
    method: 'DELETE',
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Remove friend failed');
  }

  return await response.json();
}

/**
 * Get friend's timeline (pictures)
 */
export async function getFriendTimeline(friendId: number, limit: number = 30): Promise<any[]> {
  const response = await fetch(`${API_BASE}/api/friends/${friendId}/timeline?limit=${limit}`, {
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Get friend timeline failed');
  }

  const data = await response.json();
  return data.pictures;
}

/**
 * Get friend's full-resolution picture for a specific date
 */
export async function getFriendPictureFull(friendId: number, date: string): Promise<string> {
  const response = await fetch(`${API_BASE}/api/friends/${friendId}/pictures/${date}/full`, {
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Get friend picture failed');
  }

  const data = await response.json();
  return data.image_base64;
}
