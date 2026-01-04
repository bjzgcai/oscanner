/**
 * API client for voice analysis backend
 */

const API_BASE = 'http://localhost:8765';

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
export async function triggerAnalysis(text: string): Promise<string> {
  const response = await fetch(`${API_BASE}/api/trigger`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: 'analyze_text',
      params: { text }
    })
  });

  const data: TriggerResponse = await response.json();
  if (!data.success) {
    throw new Error('Failed to trigger analysis');
  }

  return data.exec_id;
}

/**
 * Get analysis result (polls until completed)
 */
export async function getAnalysisResult(exec_id: string): Promise<StatusResponse['result']> {
  // Poll every 500ms, max 30 seconds
  const maxAttempts = 60;
  let attempts = 0;

  while (attempts < maxAttempts) {
    const response = await fetch(`${API_BASE}/api/status/${exec_id}`);
    const data: StatusResponse = await response.json();

    if (data.status === 'completed') {
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
export async function analyzeText(text: string) {
  const exec_id = await triggerAnalysis(text);
  const result = await getAnalysisResult(exec_id);
  return result?.voices || [];
}
