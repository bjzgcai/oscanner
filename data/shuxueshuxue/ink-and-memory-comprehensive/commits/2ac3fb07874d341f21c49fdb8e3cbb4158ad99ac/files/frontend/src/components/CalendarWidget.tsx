import { useState, useEffect } from 'react';
import { getCalendarData, getDateKey, getTodayKey, type CalendarEntry } from '../utils/calendarStorage';

interface CalendarWidgetProps {
  onLoadEntry: (entry: CalendarEntry) => void;
}

export default function CalendarWidget({ onLoadEntry }: CalendarWidgetProps) {
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [entriesForDate, setEntriesForDate] = useState<CalendarEntry[]>([]);

  const calendarData = getCalendarData();
  const datesWithEntries = new Set(Object.keys(calendarData));
  const todayKey = getTodayKey();

  useEffect(() => {
    if (selectedDate) {
      setEntriesForDate(calendarData[selectedDate] || []);
    } else {
      setEntriesForDate([]);
    }
  }, [selectedDate, calendarData]);

  const getDaysInMonth = (date: Date) => {
    const year = date.getFullYear();
    const month = date.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);

    const days: (Date | null)[] = [];

    // Add empty slots for days before month starts
    const startDay = firstDay.getDay();
    for (let i = 0; i < startDay; i++) {
      days.push(null);
    }

    // Add all days in month
    for (let i = 1; i <= lastDay.getDate(); i++) {
      days.push(new Date(year, month, i));
    }

    return days;
  };

  const formatMonthYear = (date: Date) => {
    return date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
  };

  const formatTime = (timestamp: number) => {
    return new Date(timestamp).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    });
  };

  const prevMonth = () => {
    setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1));
    setSelectedDate(null);
  };

  const nextMonth = () => {
    setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1));
    setSelectedDate(null);
  };

  const days = getDaysInMonth(currentMonth);

  return (
    <div style={{
      padding: '20px',
      fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
    }}>
      {/* Month navigation */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '16px',
      }}>
        <button
          onClick={prevMonth}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            fontSize: '18px',
            padding: '4px 8px',
          }}
        >
          ←
        </button>
        <div style={{ fontSize: '16px', fontWeight: 600 }}>
          {formatMonthYear(currentMonth)}
        </div>
        <button
          onClick={nextMonth}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            fontSize: '18px',
            padding: '4px 8px',
          }}
        >
          →
        </button>
      </div>

      {/* Calendar grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(7, 1fr)',
        gap: '4px',
        marginBottom: '16px',
      }}>
        {/* Day headers */}
        {['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].map(day => (
          <div key={day} style={{
            textAlign: 'center',
            fontSize: '12px',
            color: '#666',
            fontWeight: 600,
            padding: '4px',
          }}>
            {day}
          </div>
        ))}

        {/* Days */}
        {days.map((day, idx) => {
          if (!day) {
            return <div key={`empty-${idx}`} />;
          }

          const dateKey = getDateKey(day);
          const hasEntries = datesWithEntries.has(dateKey);
          const isToday = dateKey === todayKey;
          const isSelected = dateKey === selectedDate;

          return (
            <button
              key={dateKey}
              onClick={() => setSelectedDate(isSelected ? null : dateKey)}
              style={{
                padding: '8px',
                border: isToday ? '2px solid #333' : '1px solid #ddd',
                background: isSelected ? '#f0f0f0' : 'white',
                cursor: 'pointer',
                borderRadius: '4px',
                fontSize: '14px',
                position: 'relative',
                textAlign: 'center',
              }}
            >
              {day.getDate()}
              {hasEntries && (
                <div style={{
                  position: 'absolute',
                  bottom: '2px',
                  left: '50%',
                  transform: 'translateX(-50%)',
                  width: '4px',
                  height: '4px',
                  borderRadius: '50%',
                  background: '#4a90e2',
                }} />
              )}
            </button>
          );
        })}
      </div>

      {/* Entries list */}
      {selectedDate && entriesForDate.length > 0 && (
        <div>
          <div style={{
            fontSize: '14px',
            fontWeight: 600,
            marginBottom: '8px',
            color: '#333',
          }}>
            Entries for {selectedDate}
          </div>
          <div style={{
            borderTop: '1px solid #ddd',
            paddingTop: '8px',
          }}>
            {entriesForDate.map(entry => (
              <button
                key={entry.id}
                onClick={() => onLoadEntry(entry)}
                style={{
                  width: '100%',
                  padding: '8px',
                  marginBottom: '4px',
                  border: '1px solid #e0e0e0',
                  borderRadius: '4px',
                  background: 'white',
                  cursor: 'pointer',
                  textAlign: 'left',
                  display: 'flex',
                  gap: '8px',
                  fontSize: '13px',
                }}
              >
                <span style={{ color: '#666', minWidth: '45px' }}>
                  {formatTime(entry.timestamp)}
                </span>
                <span style={{ color: '#333', flex: 1 }}>
                  {entry.firstLine}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
