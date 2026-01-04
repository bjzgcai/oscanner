import { useState } from 'react';

export default function CalendarView() {
  const [hoveredDay, setHoveredDay] = useState<number | null>(null);

  // Fake calendar data
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const currentMonth = new Date().getMonth();
  const currentYear = new Date().getFullYear();
  const currentDate = new Date().getDate();

  // Generate days for current month
  const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();
  const firstDayOfMonth = new Date(currentYear, currentMonth, 1).getDay();

  // Fake writing entries with summaries
  const fakeEntries: Record<number, { count: number; summary: string }> = {
    3: { count: 2, summary: '今天写了关于记忆与时间的思考。源代码会贬值，但是思想不会。' },
    5: { count: 1, summary: '记录了一个有趣的想法：如何用代码表达情感？' },
    8: { count: 3, summary: '探索了人工智能与创造力的边界。写作是一种对话。' },
    12: { count: 1, summary: '关于阅读和写作的关系。输入决定输出。' },
    15: { count: 2, summary: '思考了知识管理的本质。笔记不是目的，理解才是。' },
    18: { count: 4, summary: '深入分析了设计模式在实际项目中的应用。理论与实践的结合。' },
    21: { count: 1, summary: '今天的心情有点低落，但写作帮助我理清了思绪。' }
  };

  const days = [];
  // Empty cells for days before month starts
  for (let i = 0; i < firstDayOfMonth; i++) {
    days.push(<div key={`empty-${i}`} style={{ padding: 12 }} />);
  }
  // Actual days
  for (let day = 1; day <= daysInMonth; day++) {
    const isToday = day === currentDate;
    const entry = fakeEntries[day];
    const hasEntries = !!entry;

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
        onMouseEnter={() => {
          if (hasEntries) {
            setHoveredDay(day);
          }
        }}
        onMouseLeave={() => {
          if (hasEntries) {
            setHoveredDay(null);
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
            {Array.from({ length: Math.min(entry.count, 5) }).map((_, i) => (
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

  const currentEntry = hoveredDay ? fakeEntries[hoveredDay] : null;

  return (
    <div style={{
      width: '100%',
      height: '100%',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '2rem',
      boxSizing: 'border-box'
    }}>
      {/* Center container for both panels */}
      <div style={{
        display: 'flex',
        gap: '2.5rem',
        alignItems: 'stretch'
      }}>
        {/* Left: Calendar Grid */}
        <div style={{
          flex: '0 0 auto',
          width: 600,
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

        {/* Right: Preview Panel */}
        <div style={{
          flex: '0 0 auto',
          width: 480,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#fffef9',
          borderRadius: 8,
          padding: '2rem',
          border: '1px solid #d0c4b0',
          boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
          transition: 'opacity 0.3s ease',
          opacity: hoveredDay ? 1 : 0.6
        }}>
        {hoveredDay && currentEntry ? (
          <>
            {/* Polaroid-style photo */}
            <div style={{
              background: 'white',
              padding: '12px 12px 40px 12px',
              boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
              transform: 'rotate(-2deg)',
              marginBottom: '1.5rem',
              position: 'relative'
            }}>
              <img
                src="/ink-and-memory/placeholder-memory.png"
                alt="Memory"
                style={{
                  width: '100%',
                  maxWidth: 280,
                  aspectRatio: '1',
                  objectFit: 'cover',
                  display: 'block'
                }}
              />
              {/* Date label at bottom of polaroid */}
              <div style={{
                position: 'absolute',
                bottom: 12,
                left: 0,
                right: 0,
                textAlign: 'center',
                fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
                fontSize: 15,
                color: '#666'
              }}>
                {currentYear}年{currentMonth + 1}月{hoveredDay}日
              </div>
            </div>

            {/* Text summary */}
            <div style={{
              fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
              fontSize: 16,
              lineHeight: 1.6,
              color: '#333',
              textAlign: 'center',
              maxWidth: 320,
              padding: '0 1rem'
            }}>
              {currentEntry.summary}
            </div>
          </>
        ) : (
          <div style={{
            textAlign: 'center',
            color: '#999',
            fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif"
          }}>
            <div style={{ fontSize: 48, marginBottom: '1rem' }}>📔</div>
            <div style={{ fontSize: 16 }}>Hover over a date</div>
            <div style={{ fontSize: 16 }}>to see its memory</div>
          </div>
        )}
        </div>
      </div>
    </div>
  );
}
