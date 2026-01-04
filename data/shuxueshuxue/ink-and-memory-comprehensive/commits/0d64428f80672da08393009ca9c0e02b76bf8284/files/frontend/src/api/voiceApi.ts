/**
 * API client for voice analysis backend
 */

// nginx proxies /ink-and-memory/api/* to backend (8765)
const API_BASE = '/ink-and-memory';

interface TriggerResponse {
  success: boolean;
  exec_id: string;
}

interface StatusResponse {
  exec_id: string;
  status: 'running' | 'completed' | 'failed';
  result?: {
    voices: Array<{
      phrase: string;
      voice: string;
      comment: string;
      icon: string;
      color: string;
    }>;
    status: string;
  };
  error?: string;
}

/**
 * Trigger voice analysis session
 */
export async function triggerAnalysis(text: string, sessionId: string): Promise<string> {
  console.log('📤 Sending trigger request...');
  const response = await fetch(`${API_BASE}/api/trigger`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: 'analyze_text',
      params: { text, session_id: sessionId }
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
 * Analyze text and return voices (all-in-one)
 */
export async function analyzeText(text: string, sessionId: string) {
  const exec_id = await triggerAnalysis(text, sessionId);
  const result = await getAnalysisResult(exec_id);
  return result?.voices || [];
}
