/**
 * Resolve API base URL at runtime.
 *
 * - If NEXT_PUBLIC_API_SERVER_URL is set: use it.
 * - Otherwise use same-origin (empty base) so the dashboard works when served by the backend.
 * - When opened via file:// (static dashboard opened directly), default to http://localhost:8000.
 */
export function getApiBaseUrl(): string {
  const envBase = (process.env.NEXT_PUBLIC_API_SERVER_URL || '').trim().replace(/\/$/, '');
  if (envBase) return envBase;

  // If the dashboard is opened directly from disk, relative fetches like `/api/...` won't work.
  if (typeof window !== 'undefined') {
    try {
      if (window.location?.protocol === 'file:') {
        return 'http://localhost:8000';
      }
    } catch {
      // ignore
    }
  }

  // Empty base => same-origin relative URLs: `/api/...`
  return '';
}


