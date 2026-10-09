/**
 * Fetch wrapper for endpoints that synchronously trigger LLM evaluations.
 *
 * Full-context evaluation batches can take tens of minutes, so the browser
 * window is deliberately larger than every server-side timeout (nginx 3600s,
 * LLM client 900s) and lets the server decide when a request is too slow.
 */
export const EVALUATION_TIMEOUT_MS = 75 * 60 * 1000;

export async function evaluationFetch(url: string, init?: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), EVALUATION_TIMEOUT_MS);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}
