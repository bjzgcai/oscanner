import type { CalendarEntry } from './calendarStorage';
import { extractFirstLine, getTodayKey } from './calendarStorage';
import type { EditorState } from '../engine/EditorEngine';

type ListSessionsFn = () => Promise<any[]>;
type GetSessionFn = (id: string) => Promise<any>;

function normalizeTimestamp(raw?: string | null): Date | null {
  if (!raw) return null;
  const normalized = raw.includes('T') ? raw : raw.replace(' ', 'T');
  const withZone = /[zZ]$/.test(normalized) ? normalized : `${normalized}Z`;
  const parsed = Date.parse(withZone);
  if (Number.isNaN(parsed)) {
    return null;
  }
  return new Date(parsed);
}

export function getSessionDateKey(session: any, state?: EditorState): string {
  const name = session?.name;
  if (name && /^\d{4}-\d{2}-\d{2}/.test(name)) {
    return name.split(' - ')[0];
  }

  if (state?.createdAt) {
    return state.createdAt;
  }

  const timestamp = normalizeTimestamp(session?.updated_at || session?.created_at);
  if (timestamp) {
    return timestamp.toISOString().substring(0, 10);
  }

  return getTodayKey();
}

function getEntryFirstLine(sessionName: string | undefined, state?: EditorState): string {
  if (sessionName && sessionName.trim().length > 0) {
    return sessionName.trim();
  }
  if (state) {
    return extractFirstLine(state);
  }
  return 'Untitled';
}

export async function loadSessionsGroupedByDate(
  listSessions: ListSessionsFn,
  getSession: GetSessionFn,
  options: { requireName?: boolean } = {}
): Promise<Record<string, CalendarEntry[]>> {
  const { requireName = false } = options;
  const sessions = await listSessions();
  const grouped: Record<string, CalendarEntry[]> = {};

  for (const session of sessions) {
    if (requireName && !session.name) continue;

    try {
      const fullSession = await getSession(session.id);
      if (!fullSession?.editor_state) continue;

      const dateKey = getSessionDateKey(session, fullSession.editor_state);
      const firstLine = getEntryFirstLine(session.name, fullSession.editor_state);
      if (!grouped[dateKey]) {
        grouped[dateKey] = [];
      }

      const timestamp = normalizeTimestamp(session?.created_at || session?.updated_at);
      const displayTimestamp = timestamp ? timestamp.getTime() : Date.now();

      grouped[dateKey].push({
        id: session.id,
        timestamp: displayTimestamp,
        state: fullSession.editor_state,
        firstLine
      });
    } catch (error) {
      console.error(`Failed to load session ${session.id}:`, error);
    }
  }

  return grouped;
}
