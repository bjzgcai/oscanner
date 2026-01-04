const CANONICAL_LOCALE = 'en-CA';

function ensureDate(value?: string | number | Date | null): Date | null {
  if (!value && value !== 0) return null;
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
  if (typeof value === 'number') {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }
  if (typeof value === 'string') {
    const normalized = value.includes('T') ? value : `${value}T00:00:00Z`;
    const parsed = new Date(normalized);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }
  return null;
}

export function formatDateInTimeZone(date: Date, timeZone: string): string {
  return new Intl.DateTimeFormat(CANONICAL_LOCALE, {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }).format(date);
}

export function getLocalDayKey(value: Date | string | number | null | undefined, timeZone: string): string | null {
  const date = ensureDate(value ?? null);
  if (!date) return null;
  return formatDateInTimeZone(date, timeZone);
}

export function parseFlexibleTimestamp(value?: string | null): Date | null {
  if (!value) return null;
  return ensureDate(value);
}

export function getTodayKeyInTimezone(timeZone: string): string {
  return formatDateInTimeZone(new Date(), timeZone);
}

export function areDatesSameLocalDay(a?: string, b?: string, timeZone: string = 'UTC'): boolean {
  if (!a || !b) return false;
  const dayA = getLocalDayKey(a, timeZone);
  const dayB = getLocalDayKey(b, timeZone);
  return Boolean(dayA && dayB && dayA === dayB);
}

export function convertLocalDayToUtcRange(dayKey: string, timeZone: string): { start: Date; end: Date } {
  const [year, month, day] = dayKey.split('-').map(Number);
  const local = new Date(Date.UTC(year, month - 1, day));
  const tzDate = new Date(local.toLocaleString('en-US', { timeZone }));
  const start = new Date(tzDate);
  start.setHours(0, 0, 0, 0);
  const end = new Date(start);
  end.setDate(end.getDate() + 1);
  return {
    start: new Date(start.toLocaleString('en-US', { timeZone: 'UTC' })),
    end: new Date(end.toLocaleString('en-US', { timeZone: 'UTC' }))
  };
}
