import type { CalendarEntry } from './calendarStorage';
import { extractFirstLine, getTodayKey } from './calendarStorage';
import type { EditorState } from '../engine/EditorEngine';
import { getLocalDayKey, parseFlexibleTimestamp } from './timezone';

type ListSessionsFn = () => Promise<any[]>;
type GetSessionFn = (id: string) => Promise<any>;

function getSessionTimestamp(sessionMeta: any, fullSession: any): Date | null {
  const stateTimestamp = parseFlexibleTimestamp(fullSession?.editor_state?.createdAt);
  if (stateTimestamp) return stateTimestamp;

  const createdAt = parseFlexibleTimestamp(fullSession?.created_at || sessionMeta?.created_at);
  if (createdAt) return createdAt;

  const updatedAt = parseFlexibleTimestamp(fullSession?.updated_at || sessionMeta?.updated_at);
  return updatedAt;
}

function getSessionDateKey(session: any, fullSession: any, timezone: string): string {
  const timestamp = getSessionTimestamp(session, fullSession);
  if (!timestamp) {
    console.warn('Session missing timestamp data', session?.id);
    return getTodayKey();
  }
  return getLocalDayKey(timestamp, timezone) ?? getTodayKey();
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
  options: { requireName?: boolean; timezone?: string } = {}
): Promise<Record<string, CalendarEntry[]>> {
  const { requireName = false, timezone = 'UTC' } = options;
  const sessions = await listSessions();
  const grouped: Record<string, CalendarEntry[]> = {};

  for (const session of sessions) {
    if (requireName && !session.name) continue;

    try {
      const fullSession = await getSession(session.id);
      if (!fullSession?.editor_state) continue;

      const dateKey = getSessionDateKey(session, fullSession, timezone);
      const firstLine = getEntryFirstLine(session.name, fullSession.editor_state);
      if (!grouped[dateKey]) {
        grouped[dateKey] = [];
      }

      const timestamp = getSessionTimestamp(session, fullSession);
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
