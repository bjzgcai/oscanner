export default function CalendarView() {
  // Fake calendar data
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const currentMonth = new Date().getMonth();
  const currentYear = new Date().getFullYear();
  const currentDate = new Date().getDate();

  // Generate days for current month
  const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();
  const firstDayOfMonth = new Date(currentYear, currentMonth, 1).getDay();

  // Fake writing entries (just for display)
  const fakeEntries: Record<number, number> = {
    3: 2, 5: 1, 8: 3, 12: 1, 15: 2, 18: 4, 21: 1, 25: 2
  };

  const days = [];
  // Empty cells for days before month starts
  for (let i = 0; i < firstDayOfMonth; i++) {
    days.push(<div key={`empty-${i}`} style={{ padding: 12 }} />);
  }
  // Actual days
  for (let day = 1; day <= daysInMonth; day++) {
    const isToday = day === currentDate;
    const hasEntries = fakeEntries[day];

    days.push(
      <div
        key={day}
        style={{
          padding: 12,
          textAlign: 'center',
          borderRadius: 8,
          background: isToday ? '#fffef9' : hasEntries ? '#f9f5ed' : 'transparent',
          border: isToday ? '2px solid #333' : hasEntries ? '1px solid #d0c4b0' : '1px solid transparent',
          cursor: hasEntries ? 'pointer' : 'default',
          position: 'relative',
          fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
          fontSize: 16,
          fontWeight: isToday ? 600 : 400,
          color: isToday ? '#333' : hasEntries ? '#555' : '#999',
          transition: 'all 0.2s'
        }}
        onMouseEnter={e => {
          if (hasEntries) {
            e.currentTarget.style.background = '#fff';
            e.currentTarget.style.transform = 'scale(1.05)';
          }
        }}
        onMouseLeave={e => {
          if (hasEntries) {
            e.currentTarget.style.background = '#f9f5ed';
            e.currentTarget.style.transform = 'scale(1)';
          }
        }}
      >
        {day}
        {hasEntries && (
          <div style={{
            position: 'absolute',
            bottom: 4,
            left: '50%',
            transform: 'translateX(-50%)',
            display: 'flex',
            gap: 2
          }}>
            {Array.from({ length: Math.min(hasEntries, 5) }).map((_, i) => (
              <div
                key={i}
                style={{
                  width: 4,
                  height: 4,
                  borderRadius: '50%',
                  background: '#8b7355'
                }}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div style={{
      width: '100%',
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '2rem',
      boxSizing: 'border-box'
    }}>
      <div style={{
        maxWidth: 600,
        width: '100%',
        background: '#fffef9',
        borderRadius: 8,
        padding: '2rem',
        border: '1px solid #d0c4b0',
        boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
      }}>
        {/* Header */}
        <div style={{
          textAlign: 'center',
          marginBottom: '2rem',
          fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
          fontSize: 24,
          fontWeight: 600,
          color: '#333'
        }}>
          {months[currentMonth]} {currentYear}
        </div>

        {/* Day headers */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(7, 1fr)',
          gap: 4,
          marginBottom: 8
        }}>
          {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(day => (
            <div
              key={day}
              style={{
                padding: 8,
                textAlign: 'center',
                fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
                fontSize: 14,
                fontWeight: 600,
                color: '#8b7355'
              }}
            >
              {day}
            </div>
          ))}
        </div>

        {/* Calendar grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(7, 1fr)',
          gap: 4
        }}>
          {days}
        </div>

        {/* Legend */}
        <div style={{
          marginTop: '2rem',
          paddingTop: '1rem',
          borderTop: '1px solid #d0c4b0',
          display: 'flex',
          gap: '1rem',
          justifyContent: 'center',
          fontSize: 14,
          color: '#666',
          fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif"
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 4, height: 4, borderRadius: '50%', background: '#8b7355' }} />
            <span>Writing entry</span>
          </div>
        </div>
      </div>
    </div>
  );
}
