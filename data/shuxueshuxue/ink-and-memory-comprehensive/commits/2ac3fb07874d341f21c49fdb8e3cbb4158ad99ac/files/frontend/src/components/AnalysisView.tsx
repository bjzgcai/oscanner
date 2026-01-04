import { useState, useEffect } from 'react';
import { getCalendarData } from '../utils/calendarStorage';
import { analyzeEchoes, analyzeTraits, analyzePatterns } from '../api/voiceApi';
import type { TextCell } from '../engine/EditorEngine';

export default function AnalysisView() {
  const [currentPage, setCurrentPage] = useState(0);
  const [allNotes, setAllNotes] = useState('');

  const pages = [
    { id: 0, name: 'Adventure' },
    { id: 1, name: 'Patterns' },
    { id: 2, name: 'Traits' },
    { id: 3, name: 'Echoes' }
  ];

  // Collect all notes when component mounts
  useEffect(() => {
    const calendarData = getCalendarData();
    const notes: string[] = [];

    // Collect all text from all entries
    Object.keys(calendarData).forEach(dateKey => {
      calendarData[dateKey].forEach(entry => {
        entry.state.cells
          .filter(cell => cell.type === 'text')
          .forEach(cell => {
            const content = (cell as TextCell).content.trim();
            if (content) {
              notes.push(content);
            }
          });
      });
    });

    setAllNotes(notes.join('\n\n'));
  }, []);

  return (
    <div style={{
      width: '100%',
      height: '100%',
      display: 'flex',
      fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
      paddingTop: '2rem'
    }}>
      {/* Left sidebar - Page tabs */}
      <div style={{
        width: 200,
        background: 'transparent',
        alignSelf: 'stretch',
        paddingTop: '1rem',
        borderRight: '1px solid #d0c4b0'
      }}>
        {pages.map(page => (
          <div
            key={page.id}
            onClick={() => setCurrentPage(page.id)}
            style={{
              padding: '0.75rem 1.5rem',
              cursor: 'pointer',
              background: currentPage === page.id ? 'rgba(44, 44, 44, 0.05)' : 'transparent',
              borderLeft: currentPage === page.id ? '3px solid #333' : '3px solid transparent',
              fontWeight: currentPage === page.id ? 600 : 400,
              color: currentPage === page.id ? '#333' : '#888',
              transition: 'all 0.2s',
              fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
              fontSize: 14
            }}
            onMouseEnter={e => {
              if (currentPage !== page.id) {
                e.currentTarget.style.color = '#555';
                e.currentTarget.style.background = 'rgba(44, 44, 44, 0.03)';
              }
            }}
            onMouseLeave={e => {
              if (currentPage !== page.id) {
                e.currentTarget.style.color = '#888';
                e.currentTarget.style.background = 'transparent';
              }
            }}
          >
            {page.name}
          </div>
        ))}
      </div>

      {/* Right content area */}
      <div style={{
        flex: 1,
        padding: '2rem',
        overflowY: 'auto',
        background: '#f8f0e6'
      }}>
        {currentPage === 0 && <Page0StickyNotes />}
        {currentPage === 1 && <PatternsPage allNotes={allNotes} />}
        {currentPage === 2 && <TraitsPage allNotes={allNotes} />}
        {currentPage === 3 && <EchoesPage allNotes={allNotes} />}
      </div>
    </div>
  );
}

// Page 0: Sticky notes with actionable nudges
function Page0StickyNotes() {
  const notes = [
    { text: '下次点咖啡，试试菜单上从没点过的那一个。', color: '#FFF9BE', rotation: -2 },
    { text: '给一个很久没联系的人发条消息，就说"想起你了"。', color: '#D4EAF1', rotation: 1 },
    { text: '今天走不同的路回家，哪怕只是换一条街。', color: '#F1D4D4', rotation: -1 },
    { text: '在电梯里和陌生人说句话，比如"今天天气不错"。', color: '#FFF9BE', rotation: 2 },
    { text: '把一件拖了很久的小事做掉，5 分钟就够了。', color: '#D4EAF1', rotation: -3 },
    { text: '闭上眼睛吃一口东西，专注地感受味道。', color: '#F1D4D4', rotation: 1 }
  ];

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
      gap: '2rem',
      padding: '2rem'
    }}>
      {notes.map((note, index) => (
        <div
          key={index}
          style={{
            background: note.color,
            padding: '1.5rem',
            borderRadius: '4px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
            transform: `rotate(${note.rotation}deg)`,
            transition: 'all 0.2s',
            cursor: 'pointer',
            minHeight: '120px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            textAlign: 'center',
            lineHeight: 1.6
          }}
          onMouseEnter={e => {
            e.currentTarget.style.transform = `rotate(0deg) scale(1.05)`;
            e.currentTarget.style.boxShadow = '0 4px 16px rgba(0,0,0,0.15)';
          }}
          onMouseLeave={e => {
            e.currentTarget.style.transform = `rotate(${note.rotation}deg) scale(1)`;
            e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.1)';
          }}
        >
          {note.text}
        </div>
      ))}
    </div>
  );
}

// @@@ Echoes Page - Recurring themes
function EchoesPage({ allNotes }: { allNotes: string }) {
  const [echoes, setEchoes] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleAnalyze = async () => {
    if (!allNotes.trim()) {
      setError('No notes found. Save some entries first.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const result = await analyzeEchoes(allNotes);
      setEchoes(result);
    } catch (e: any) {
      setError(e.message || 'Analysis failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto' }}>
      <h2 style={{
        fontSize: '24px',
        fontWeight: 600,
        marginBottom: '1rem'
      }}>
        重复出现的话题 (Echoes)
      </h2>

      <p style={{
        color: '#666',
        marginBottom: '2rem',
        lineHeight: 1.6
      }}>
        Identify recurring themes and topics across all your notes.
      </p>

      <button
        onClick={handleAnalyze}
        disabled={loading}
        style={{
          padding: '12px 24px',
          background: loading ? '#ccc' : '#333',
          color: '#fff',
          border: 'none',
          borderRadius: '6px',
          cursor: loading ? 'not-allowed' : 'pointer',
          fontSize: '14px',
          fontWeight: 600,
          marginBottom: '2rem'
        }}
      >
        {loading ? 'Analyzing...' : 'Analyze Echoes'}
      </button>

      {error && (
        <div style={{
          padding: '1rem',
          background: '#fee',
          border: '1px solid #fcc',
          borderRadius: '6px',
          color: '#c33',
          marginBottom: '2rem'
        }}>
          {error}
        </div>
      )}

      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '1.5rem'
      }}>
        {echoes.map((echo, idx) => (
          <div
            key={idx}
            style={{
              background: '#fff',
              padding: '1.5rem',
              borderRadius: '8px',
              border: '1px solid #d0c4b0',
              boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
            }}
          >
            <h3 style={{
              fontSize: '18px',
              fontWeight: 600,
              marginBottom: '0.75rem',
              color: '#333'
            }}>
              {echo.title}
            </h3>
            <p style={{
              color: '#666',
              lineHeight: 1.6,
              marginBottom: '1rem'
            }}>
              {echo.description}
            </p>
            <div style={{
              borderTop: '1px solid #f0f0f0',
              paddingTop: '1rem'
            }}>
              <div style={{
                fontSize: '12px',
                fontWeight: 600,
                color: '#999',
                marginBottom: '0.5rem'
              }}>
                EXAMPLES:
              </div>
              {echo.examples?.map((ex: string, i: number) => (
                <div
                  key={i}
                  style={{
                    padding: '0.5rem',
                    background: '#f8f0e6',
                    borderLeft: '3px solid #d0c4b0',
                    marginBottom: '0.5rem',
                    fontSize: '13px',
                    fontStyle: 'italic',
                    color: '#666'
                  }}
                >
                  "{ex}"
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// @@@ Traits Page - Personality characteristics
function TraitsPage({ allNotes }: { allNotes: string }) {
  const [traits, setTraits] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleAnalyze = async () => {
    if (!allNotes.trim()) {
      setError('No notes found. Save some entries first.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const result = await analyzeTraits(allNotes);
      setTraits(result);
    } catch (e: any) {
      setError(e.message || 'Analysis failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto' }}>
      <h2 style={{
        fontSize: '24px',
        fontWeight: 600,
        marginBottom: '1rem'
      }}>
        性格特征分析 (Traits)
      </h2>

      <p style={{
        color: '#666',
        marginBottom: '2rem',
        lineHeight: 1.6
      }}>
        Identify personality traits evident from your writing.
      </p>

      <button
        onClick={handleAnalyze}
        disabled={loading}
        style={{
          padding: '12px 24px',
          background: loading ? '#ccc' : '#333',
          color: '#fff',
          border: 'none',
          borderRadius: '6px',
          cursor: loading ? 'not-allowed' : 'pointer',
          fontSize: '14px',
          fontWeight: 600,
          marginBottom: '2rem'
        }}
      >
        {loading ? 'Analyzing...' : 'Analyze Traits'}
      </button>

      {error && (
        <div style={{
          padding: '1rem',
          background: '#fee',
          border: '1px solid #fcc',
          borderRadius: '6px',
          color: '#c33',
          marginBottom: '2rem'
        }}>
          {error}
        </div>
      )}

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
        gap: '1.5rem'
      }}>
        {traits.map((trait, idx) => (
          <div
            key={idx}
            style={{
              background: '#fff',
              padding: '1.5rem',
              borderRadius: '8px',
              border: '1px solid #d0c4b0',
              boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
            }}
          >
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '0.75rem'
            }}>
              <h3 style={{
                fontSize: '18px',
                fontWeight: 600,
                color: '#333'
              }}>
                {trait.trait}
              </h3>
              <div style={{
                fontSize: '14px',
                fontWeight: 600,
                color: '#666',
                background: '#f0f0f0',
                padding: '4px 8px',
                borderRadius: '4px'
              }}>
                {trait.strength}/5
              </div>
            </div>
            {/* Strength bar */}
            <div style={{
              height: '6px',
              background: '#f0f0f0',
              borderRadius: '3px',
              marginBottom: '1rem',
              overflow: 'hidden'
            }}>
              <div style={{
                height: '100%',
                width: `${(trait.strength / 5) * 100}%`,
                background: 'linear-gradient(90deg, #4CAF50, #8BC34A)',
                borderRadius: '3px'
              }} />
            </div>
            <p style={{
              color: '#666',
              lineHeight: 1.6,
              fontSize: '13px'
            }}>
              {trait.evidence}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

// @@@ Patterns Page - Behavioral patterns
function PatternsPage({ allNotes }: { allNotes: string }) {
  const [patterns, setPatterns] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleAnalyze = async () => {
    if (!allNotes.trim()) {
      setError('No notes found. Save some entries first.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const result = await analyzePatterns(allNotes);
      setPatterns(result);
    } catch (e: any) {
      setError(e.message || 'Analysis failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto' }}>
      <h2 style={{
        fontSize: '24px',
        fontWeight: 600,
        marginBottom: '1rem'
      }}>
        行为模式分析 (Patterns)
      </h2>

      <p style={{
        color: '#666',
        marginBottom: '2rem',
        lineHeight: 1.6
      }}>
        Identify behavioral patterns and habits from your notes.
      </p>

      <button
        onClick={handleAnalyze}
        disabled={loading}
        style={{
          padding: '12px 24px',
          background: loading ? '#ccc' : '#333',
          color: '#fff',
          border: 'none',
          borderRadius: '6px',
          cursor: loading ? 'not-allowed' : 'pointer',
          fontSize: '14px',
          fontWeight: 600,
          marginBottom: '2rem'
        }}
      >
        {loading ? 'Analyzing...' : 'Analyze Patterns'}
      </button>

      {error && (
        <div style={{
          padding: '1rem',
          background: '#fee',
          border: '1px solid #fcc',
          borderRadius: '6px',
          color: '#c33',
          marginBottom: '2rem'
        }}>
          {error}
        </div>
      )}

      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '1.5rem'
      }}>
        {patterns.map((pattern, idx) => (
          <div
            key={idx}
            style={{
              background: '#fff',
              padding: '1.5rem',
              borderRadius: '8px',
              border: '1px solid #d0c4b0',
              boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
            }}
          >
            <h3 style={{
              fontSize: '18px',
              fontWeight: 600,
              marginBottom: '0.75rem',
              color: '#333'
            }}>
              {pattern.pattern}
            </h3>
            <p style={{
              color: '#666',
              lineHeight: 1.6,
              marginBottom: '1rem'
            }}>
              {pattern.description}
            </p>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              fontSize: '13px',
              color: '#999'
            }}>
              <span style={{ fontWeight: 600 }}>Frequency:</span>
              <span>{pattern.frequency}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
