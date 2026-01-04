import { useState, useEffect } from 'react';
import {
  getCalendarData,
  getDateKey,
  getTodayKey,
  deleteEntry,
  type CalendarEntry
} from '../utils/calendarStorage';
import { useAuth } from '../contexts/AuthContext';

interface Props {
  onLoadEntry: (entry: CalendarEntry) => void;
  onClose: () => void;
}

export default function CalendarPopup({ onLoadEntry, onClose }: Props) {
  const { isAuthenticated } = useAuth();
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState<string | null>(getTodayKey());
  const [calendarData, setCalendarData] = useState<Record<string, CalendarEntry[]>>({});

  // @@@ Load calendar data from database if authenticated, localStorage if guest
  useEffect(() => {
    const loadData = async () => {
      if (isAuthenticated) {
        try {
          // Load from database - sessions imported during migration
          const { listSessions, getSession } = await import('../api/voiceApi');
          const sessions = await listSessions();

          // Group sessions by date (extract from session name which has format "YYYY-MM-DD - FirstLine")
          const grouped: Record<string, CalendarEntry[]> = {};

          for (const session of sessions) {
            // @@@ Skip unnamed sessions (working drafts not saved yet)
            if (!session.name) continue;

            const fullSession = await getSession(session.id);

            // @@@ BUGFIX: Extract date from timestamp (format: "2025-11-02 10:42:17" or "2025-11-02T10:42:17")
            // Just take first 10 characters to get "YYYY-MM-DD"
            let dateKey = session.created_at?.substring(0, 10) || getTodayKey();

            // If name starts with YYYY-MM-DD format, use that
            if (session.name && /^\d{4}-\d{2}-\d{2}/.test(session.name)) {
              dateKey = session.name.split(' - ')[0];
            }

            if (!grouped[dateKey]) {
              grouped[dateKey] = [];
            }

            grouped[dateKey].push({
              id: session.id,
              timestamp: new Date(session.created_at || Date.now()).getTime(),
              state: fullSession.editor_state,
              firstLine: session.name
            });
          }

          setCalendarData(grouped);
        } catch (error) {
          console.error('Failed to load calendar from database:', error);
          // Fallback to localStorage
          setCalendarData(getCalendarData());
        }
      } else {
        // Guest mode: load from localStorage
        setCalendarData(getCalendarData());
      }
    };

    loadData();
  }, [isAuthenticated]);

  const today = getTodayKey();
  const datesWithEntries = Object.keys(calendarData);

  // Calculate calendar grid
  const year = currentMonth.getFullYear();
  const month = currentMonth.getMonth();
  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);
  const daysInMonth = lastDay.getDate();
  const startingDayOfWeek = firstDay.getDay(); // 0 = Sunday

  const days: Array<{ date: number; dateKey: string; hasEntries: boolean; isToday: boolean } | null> = [];

  // Add empty slots for days before month starts
  for (let i = 0; i < startingDayOfWeek; i++) {
    days.push(null);
  }

  // Add days of the month
  for (let date = 1; date <= daysInMonth; date++) {
    const dateObj = new Date(year, month, date);
    const dateKey = getDateKey(dateObj);
    days.push({
      date,
      dateKey,
      hasEntries: datesWithEntries.includes(dateKey),
      isToday: dateKey === today
    });
  }

  const handlePrevMonth = () => {
    setCurrentMonth(new Date(year, month - 1));
  };

  const handleNextMonth = () => {
    setCurrentMonth(new Date(year, month + 1));
  };

  const handleDateClick = (dateKey: string) => {
    setSelectedDate(dateKey);
  };

  const handleDeleteEntry = async (dateKey: string, entryId: string) => {
    if (confirm('Delete this entry?')) {
      if (isAuthenticated) {
        try {
          // Delete from database
          const { deleteSession } = await import('../api/voiceApi');
          await deleteSession(entryId);

          // Reload calendar data
          const { listSessions, getSession } = await import('../api/voiceApi');
          const sessions = await listSessions();
          const grouped: Record<string, CalendarEntry[]> = {};

          for (const session of sessions) {
            // @@@ Skip unnamed sessions (same check as initial load)
            if (!session.name) continue;

            const fullSession = await getSession(session.id);
            // @@@ Extract date from created_at timestamp (format: "2025-11-02 10:42:17")
            let dateKey = session.created_at?.substring(0, 10) || getTodayKey();

            // Legacy: if name starts with YYYY-MM-DD format, use that
            if (session.name && /^\d{4}-\d{2}-\d{2}/.test(session.name)) {
              dateKey = session.name.split(' - ')[0];
            }

            if (!grouped[dateKey]) {
              grouped[dateKey] = [];
            }
            grouped[dateKey].push({
              id: session.id,
              timestamp: new Date(session.created_at || Date.now()).getTime(),
              state: fullSession.editor_state,
              firstLine: session.name
            });
          }
          setCalendarData(grouped);
        } catch (error) {
          console.error('Failed to delete from database:', error);
          alert('Failed to delete entry');
        }
      } else {
        // Guest mode: delete from localStorage
        deleteEntry(dateKey, entryId);
        setCalendarData(getCalendarData());
      }
    }
  };

  const selectedEntries = selectedDate ? calendarData[selectedDate] || [] : [];

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(0,0,0,0.3)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 2000,
        backdropFilter: 'blur(2px)'
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: '#fffef9',
          border: '2px solid #d0c4b0',
          borderRadius: '12px',
          width: '90%',
          maxWidth: '600px',
          maxHeight: '80vh',
          overflow: 'auto',
          boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
          fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif"
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{
          padding: '20px',
          borderBottom: '1px solid #e0d4c0',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <h2 style={{
            margin: 0,
            fontSize: '18px',
            fontWeight: 600,
            color: '#333'
          }}>
            Calendar
          </h2>
          <button
            onClick={onClose}
            style={{
              border: 'none',
              background: 'transparent',
              fontSize: '24px',
              cursor: 'pointer',
              color: '#666',
              padding: '0 8px',
              lineHeight: 1
            }}
          >
            ×
          </button>
        </div>

        <div style={{ padding: '20px' }}>
          {/* Month navigation */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '16px'
          }}>
            <button
              onClick={handlePrevMonth}
              style={{
                border: '1px solid #d0c4b0',
                background: '#fff',
                borderRadius: '4px',
                padding: '6px 12px',
                cursor: 'pointer',
                fontSize: '14px',
                fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif"
              }}
            >
              ← Prev
            </button>
            <div style={{
              fontSize: '16px',
              fontWeight: 600,
              color: '#333'
            }}>
              {currentMonth.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
            </div>
            <button
              onClick={handleNextMonth}
              style={{
                border: '1px solid #d0c4b0',
                background: '#fff',
                borderRadius: '4px',
                padding: '6px 12px',
                cursor: 'pointer',
                fontSize: '14px',
                fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif"
              }}
            >
              Next →
            </button>
          </div>

          {/* Calendar grid */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(7, 1fr)',
            gap: '4px',
            marginBottom: '20px'
          }}>
            {/* Day headers */}
            {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(day => (
              <div key={day} style={{
                textAlign: 'center',
                fontSize: '12px',
                fontWeight: 600,
                color: '#888',
                padding: '4px 0'
              }}>
                {day}
              </div>
            ))}

            {/* Days */}
            {days.map((day, idx) => {
              if (!day) {
                return <div key={`empty-${idx}`} />;
              }

              const isSelected = selectedDate === day.dateKey;

              return (
                <button
                  key={day.dateKey}
                  onClick={() => handleDateClick(day.dateKey)}
                  style={{
                    border: day.isToday ? '2px solid #333' : '1px solid #e0d4c0',
                    background: isSelected ? '#e3f2fd' : day.hasEntries ? '#fff' : '#fafafa',
                    borderRadius: '6px',
                    padding: '8px',
                    cursor: 'pointer',
                    fontSize: '14px',
                    fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
                    position: 'relative',
                    minHeight: '40px',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    transition: 'all 0.2s'
                  }}
                  onMouseEnter={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.background = '#f5f5f5';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.background = day.hasEntries ? '#fff' : '#fafafa';
                    }
                  }}
                >
                  <div style={{ fontWeight: day.isToday ? 600 : 400 }}>
                    {day.date}
                  </div>
                  {day.hasEntries && (
                    <div style={{
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      background: '#2196F3',
                      marginTop: '2px'
                    }} />
                  )}
                </button>
              );
            })}
          </div>

          {/* Entry list */}
          {selectedDate && (
            <div>
              <div style={{
                fontSize: '14px',
                fontWeight: 600,
                color: '#666',
                marginBottom: '12px',
                borderBottom: '1px solid #e0d4c0',
                paddingBottom: '8px'
              }}>
                {selectedDate === today ? 'Today' : selectedDate}
                {selectedEntries.length > 0 && ` (${selectedEntries.length} ${selectedEntries.length === 1 ? 'entry' : 'entries'})`}
              </div>

              {selectedEntries.length === 0 ? (
                <div style={{
                  textAlign: 'center',
                  color: '#999',
                  padding: '20px',
                  fontSize: '14px'
                }}>
                  No entries for this date
                </div>
              ) : (
                <div style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                  maxHeight: '200px',
                  overflow: 'auto'
                }}>
                  {selectedEntries.map((entry) => {
                    const time = new Date(entry.timestamp).toLocaleTimeString('en-US', {
                      hour: '2-digit',
                      minute: '2-digit'
                    });

                    return (
                      <div
                        key={entry.id}
                        style={{
                          border: '1px solid #d0c4b0',
                          borderRadius: '6px',
                          padding: '12px',
                          background: '#fff',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          gap: '12px'
                        }}
                      >
                        <button
                          onClick={() => onLoadEntry(entry)}
                          style={{
                            flex: 1,
                            textAlign: 'left',
                            border: 'none',
                            background: 'transparent',
                            cursor: 'pointer',
                            padding: 0,
                            fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif"
                          }}
                        >
                          <div style={{
                            fontSize: '12px',
                            color: '#999',
                            marginBottom: '4px'
                          }}>
                            {time}
                          </div>
                          <div style={{
                            fontSize: '14px',
                            color: '#333'
                          }}>
                            {entry.firstLine}
                          </div>
                        </button>
                        <button
                          onClick={() => handleDeleteEntry(selectedDate, entry.id)}
                          style={{
                            border: '1px solid #d44',
                            background: '#fff',
                            borderRadius: '4px',
                            padding: '4px 8px',
                            cursor: 'pointer',
                            fontSize: '12px',
                            color: '#d44',
                            fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
                            transition: 'all 0.2s'
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.background = '#d44';
                            e.currentTarget.style.color = '#fff';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.background = '#fff';
                            e.currentTarget.style.color = '#d44';
                          }}
                        >
                          Delete
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
