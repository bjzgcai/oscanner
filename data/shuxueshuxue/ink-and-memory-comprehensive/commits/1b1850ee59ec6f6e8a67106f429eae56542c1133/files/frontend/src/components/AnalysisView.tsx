import { useState, useEffect } from 'react';
import { getCalendarData } from '../utils/calendarStorage';
import { analyzeEchoes, analyzeTraits, analyzePatterns, saveAnalysisReport, getAnalysisReports } from '../api/voiceApi';
import type { TextCell } from '../engine/EditorEngine';
import { useAuth } from '../contexts/AuthContext';
import { STORAGE_KEYS } from '../constants/storageKeys';

// @@@ Constants
const MAX_SAVED_REPORTS = 10;

// @@@ Utility Functions

// @@@ Count words properly for mixed Chinese/English text
function countWords(text: string): number {
  let wordCount = 0;

  // Count CJK characters (each character = 1 word)
  for (let i = 0; i < text.length; i++) {
    const code = text.charCodeAt(i);
    if ((code >= 0x4E00 && code <= 0x9FFF) ||   // CJK Unified Ideographs
        (code >= 0x3400 && code <= 0x4DBF) ||   // CJK Extension A
        (code >= 0x3040 && code <= 0x309F) ||   // Hiragana
        (code >= 0x30A0 && code <= 0x30FF)) {   // Katakana
      wordCount++;
    }
  }

  // Count English words (space-separated)
  const englishWords = text
    .replace(/[\u4E00-\u9FFF\u3400-\u4DBF\u3040-\u309F\u30A0-\u30FF]/g, ' ')
    .split(/\s+/)
    .filter(w => w.length > 0).length;

  return wordCount + englishWords;
}

// @@@ Types
interface Echo {
  title: string;
  description: string;
  examples?: string[];
}

interface Trait {
  trait: string;
  strength: number;
  evidence: string;
}

interface Pattern {
  pattern: string;
  description: string;
  frequency: string;
}

interface AnalysisReport {
  id: number;
  echoes: Echo[];
  traits: Trait[];
  patterns: Pattern[];
  timestamp: number;
  stats: {
    days: number;
    entries: number;
    words: number;
  };
}

export default function AnalysisView() {
  const { isAuthenticated } = useAuth();
  const [allNotes, setAllNotes] = useState('');
  const [echoes, setEchoes] = useState<Echo[]>([]);
  const [traits, setTraits] = useState<Trait[]>([]);
  const [patterns, setPatterns] = useState<Pattern[]>([]);
  const [loading, setLoading] = useState({ echoes: false, traits: false, patterns: false });
  const [error, setError] = useState('');
  const [currentPaper, setCurrentPaper] = useState(0); // @@@ Track which paper is on top
  const [viewMode, setViewMode] = useState<'dashboard' | 'report'>('dashboard'); // @@@ Track dashboard vs report view

  // Stats
  const [stats, setStats] = useState({
    totalDays: 0,
    totalWords: 0,
    totalEntries: 0
  });

  // @@@ Saved reports history
  const [savedReports, setSavedReports] = useState<AnalysisReport[]>([]);

  // Collect all notes when component mounts
  useEffect(() => {
    const loadNotesData = async () => {
      let calendarData: Record<string, any[]> = {};

      // @@@ Load from database if authenticated, localStorage if guest
      if (isAuthenticated) {
        try {
          const { listSessions, getSession } = await import('../api/voiceApi');
          const sessions = await listSessions();

          // Group sessions by date
          const grouped: Record<string, any[]> = {};
          for (const session of sessions) {
            const fullSession = await getSession(session.id);
            let dateKey = session.created_at?.split('T')[0];
            if (session.name && /^\d{4}-\d{2}-\d{2}/.test(session.name)) {
              dateKey = session.name.split(' - ')[0];
            }
            if (!dateKey) continue;

            if (!grouped[dateKey]) {
              grouped[dateKey] = [];
            }
            grouped[dateKey].push({
              id: session.id,
              timestamp: new Date(session.created_at || Date.now()).getTime(),
              state: fullSession.editor_state,
              firstLine: session.name || 'Untitled'
            });
          }
          calendarData = grouped;
        } catch (error) {
          console.error('Failed to load from database:', error);
          calendarData = getCalendarData(); // Fallback
        }
      } else {
        calendarData = getCalendarData();
      }

      const notes: string[] = [];
      let entryCount = 0;
      const uniqueDays = new Set<string>();

      // Collect all text from all entries
      Object.keys(calendarData).forEach(dateKey => {
        uniqueDays.add(dateKey);
        calendarData[dateKey].forEach(entry => {
          entryCount++;
          entry.state.cells
            .filter((cell: any) => cell.type === 'text')
            .forEach((cell: any) => {
              const content = (cell as TextCell).content.trim();
              if (content) {
                notes.push(content);
              }
            });
        });
      });

      const allText = notes.join('\n\n');

      setAllNotes(allText);
      setStats({
        totalDays: uniqueDays.size,
        totalWords: countWords(allText),
        totalEntries: entryCount
      });
    };

    loadNotesData();

    // @@@ Load saved reports history from database if authenticated, localStorage if guest
    const loadReports = async () => {
      if (isAuthenticated) {
        try {
          const dbReports = await getAnalysisReports(MAX_SAVED_REPORTS);
          // Convert database format to app format
          const formattedReports = dbReports.map((r: any) => ({
            id: r.id,
            echoes: r.report_data?.echoes || [],
            traits: r.report_data?.traits || [],
            patterns: r.report_data?.patterns || [],
            timestamp: new Date(r.created_at).getTime(),
            stats: r.report_data?.stats || { days: 0, entries: 0, words: 0 }
          }));
          setSavedReports(formattedReports);

          // Load most recent report into state
          if (formattedReports.length > 0) {
            const mostRecent = formattedReports[0];
            setEchoes(mostRecent.echoes || []);
            setTraits(mostRecent.traits || []);
            setPatterns(mostRecent.patterns || []);
          }
        } catch (e) {
          console.error('Failed to load reports from database:', e);
        }
      } else {
        // Guest mode: load from localStorage
        const savedReportsData = localStorage.getItem(STORAGE_KEYS.ANALYSIS_REPORTS);
        if (savedReportsData) {
          try {
            const reports = JSON.parse(savedReportsData);
            setSavedReports(reports);

            // Load most recent report into state
            if (reports.length > 0) {
              const mostRecent = reports[0];
              setEchoes(mostRecent.echoes || []);
              setTraits(mostRecent.traits || []);
              setPatterns(mostRecent.patterns || []);
            }
          } catch (e) {
            console.error('Failed to load saved reports:', e);
          }
        }
      }
    };

    loadReports();
  }, [isAuthenticated]);

  const handleAnalyzeAll = async () => {
    // @@@ Block analysis for guests
    if (!isAuthenticated) {
      setError('Please log in to use reflections. This feature requires authentication.');
      return;
    }

    if (!allNotes.trim()) {
      setError('No notes found. Save some entries first.');
      return;
    }

    setError('');

    // @@@ Capture results to save to localStorage (state updates are async!)
    let echoesResult: Echo[] = [];
    let traitsResult: Trait[] = [];
    let patternsResult: Pattern[] = [];

    // @@@ Helper to wrap analysis calls with loading state and error handling
    const analyzeWithState = <T,>(
      analyzeFn: () => Promise<T>,
      loadingKey: 'echoes' | 'traits' | 'patterns',
      onSuccess: (result: T) => void
    ) => {
      setLoading(prev => ({ ...prev, [loadingKey]: true }));
      return analyzeFn()
        .then(result => {
          onSuccess(result);
          return result;
        })
        .catch(err => {
          console.error(`Failed to analyze ${loadingKey}:`, err);
          return [] as T;
        })
        .finally(() => setLoading(prev => ({ ...prev, [loadingKey]: false })));
    };

    // Analyze all three in parallel
    [echoesResult, traitsResult, patternsResult] = await Promise.all([
      analyzeWithState(
        () => analyzeEchoes(allNotes),
        'echoes',
        result => setEchoes(result)
      ),
      analyzeWithState(
        () => analyzeTraits(allNotes),
        'traits',
        result => setTraits(result)
      ),
      analyzeWithState(
        () => analyzePatterns(allNotes),
        'patterns',
        result => setPatterns(result)
      )
    ]);

    // @@@ Save report to database if authenticated, localStorage if guest
    const newReport: AnalysisReport = {
      id: Date.now(),
      echoes: echoesResult,
      traits: traitsResult,
      patterns: patternsResult,
      timestamp: Date.now(),
      stats: {
        days: stats.totalDays,
        entries: stats.totalEntries,
        words: stats.totalWords
      }
    };

    if (isAuthenticated) {
      try {
        // Save to database
        await saveAnalysisReport('full_analysis', {
          echoes: echoesResult,
          traits: traitsResult,
          patterns: patternsResult,
          stats: {
            days: stats.totalDays,
            entries: stats.totalEntries,
            words: stats.totalWords
          }
        }, allNotes);

        // Reload reports from database
        const dbReports = await getAnalysisReports(MAX_SAVED_REPORTS);
        const formattedReports = dbReports.map((r: any) => ({
          id: r.id,
          echoes: r.report_data?.echoes || [],
          traits: r.report_data?.traits || [],
          patterns: r.report_data?.patterns || [],
          timestamp: new Date(r.created_at).getTime(),
          stats: r.report_data?.stats || { days: 0, entries: 0, words: 0 }
        }));
        setSavedReports(formattedReports);
      } catch (error) {
        console.error('Failed to save report to database:', error);
      }
    } else {
      // Guest mode: save to localStorage
      const updatedReports = [newReport, ...savedReports];
      const limitedReports = updatedReports.slice(0, MAX_SAVED_REPORTS);
      localStorage.setItem(STORAGE_KEYS.ANALYSIS_REPORTS, JSON.stringify(limitedReports));
      setSavedReports(limitedReports);
    }

    // @@@ Switch to report view after analysis completes
    setViewMode('report');
    setCurrentPaper(0); // Reset to first paper
  };

  const anyLoading = loading.echoes || loading.traits || loading.patterns;
  const hasAnyData = echoes.length > 0 || traits.length > 0 || patterns.length > 0;

  // @@@ Full-page report view
  if (viewMode === 'report' && hasAnyData) {
    return (
      <div style={{
        width: '100%',
        height: '100%',
        background: 'linear-gradient(180deg, #f8f0e6 0%, #ede3d5 100%)',
        fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
        position: 'relative',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column'
      }}>
        {/* Back button - top left corner */}
        <button
          onClick={() => setViewMode('dashboard')}
          style={{
            position: 'absolute',
            top: '2rem',
            left: '2rem',
            padding: '12px 24px',
            borderRadius: '24px',
            background: 'linear-gradient(135deg, rgba(255,255,255,0.95) 0%, rgba(255,250,240,0.9) 100%)',
            border: '2px solid rgba(139,115,85,0.25)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
            fontSize: '14px',
            fontWeight: 500,
            color: '#5d4a3a',
            transition: 'all 0.3s',
            boxShadow: '0 4px 16px rgba(139,115,85,0.2), inset 0 1px 0 rgba(255,255,255,0.8)',
            zIndex: 30,
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            letterSpacing: '0.3px'
          }}
          onMouseEnter={e => {
            e.currentTarget.style.transform = 'translateY(-2px)';
            e.currentTarget.style.boxShadow = '0 8px 24px rgba(139,115,85,0.3), inset 0 1px 0 rgba(255,255,255,0.8)';
            e.currentTarget.style.background = 'linear-gradient(135deg, rgba(255,255,255,1) 0%, rgba(255,248,235,0.95) 100%)';
          }}
          onMouseLeave={e => {
            e.currentTarget.style.transform = 'translateY(0)';
            e.currentTarget.style.boxShadow = '0 4px 16px rgba(139,115,85,0.2), inset 0 1px 0 rgba(255,255,255,0.8)';
            e.currentTarget.style.background = 'linear-gradient(135deg, rgba(255,255,255,0.95) 0%, rgba(255,250,240,0.9) 100%)';
          }}
          title="Back to Dashboard"
        >
          <span style={{ fontSize: '16px' }}>←</span>
          <span>Back</span>
        </button>

        <DecorativeInkSpots />

        {/* Centered paper stack - moved up slightly */}
        <div style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '2rem',
          marginTop: '-60px'
        }}>
          <PaperStack
            echoes={echoes}
            traits={traits}
            patterns={patterns}
            currentPaper={currentPaper}
            onPaperChange={setCurrentPaper}
          />
        </div>
      </div>
    );
  }

  // @@@ Dashboard view
  return (
    <div style={{
      width: '100%',
      height: '100%',
      overflowY: 'auto',
      background: 'linear-gradient(180deg, #f8f0e6 0%, #ede3d5 100%)',
      fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
      padding: '3rem 2rem',
      position: 'relative'
    }}>
      <DecorativeInkSpots />

      <div style={{ maxWidth: '1100px', margin: '0 auto', position: 'relative' }}>
        {/* Header - Hand-drawn style */}
        <div style={{
          marginBottom: '3rem',
          textAlign: 'center',
          position: 'relative'
        }}>
          <h1 style={{
            fontSize: '48px',
            fontWeight: 400,
            color: '#3d3226',
            marginBottom: '0.75rem',
            fontFamily: 'Georgia, serif',
            fontStyle: 'italic',
            letterSpacing: '-0.5px',
            textShadow: '2px 2px 0px rgba(139,115,85,0.1)'
          }}>
            Reflections
          </h1>
          <div style={{
            width: '80px',
            height: '3px',
            background: 'linear-gradient(90deg, transparent, #8B7355, transparent)',
            margin: '0 auto 1rem',
            opacity: 0.4
          }} />
          <p style={{
            fontSize: '15px',
            color: '#6b5d4f',
            lineHeight: 1.8,
            fontStyle: 'italic',
            maxWidth: '500px',
            margin: '0 auto'
          }}>
            Patterns and insights woven through your words
          </p>
        </div>

        {/* Stats - Vintage label style */}
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          gap: '2rem',
          marginBottom: '3rem',
          flexWrap: 'wrap'
        }}>
          <VintageStatLabel label="Days" value={stats.totalDays} />
          <VintageStatLabel label="Entries" value={stats.totalEntries} />
          <VintageStatLabel label="Words" value={stats.totalWords.toLocaleString()} />
        </div>

        {/* Saved Reports History */}
        {savedReports.length > 0 && (
          <div style={{ marginBottom: '3rem' }}>
            <h2 style={{
              fontSize: '20px',
              fontWeight: 500,
              color: '#5d4a3a',
              marginBottom: '1.5rem',
              textAlign: 'center',
              fontFamily: 'Georgia, serif',
              fontStyle: 'italic'
            }}>
              Past Reflections
            </h2>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
              gap: '1.5rem',
              marginBottom: '2rem'
            }}>
              {savedReports.map((report, idx) => (
                <div
                  key={report.id}
                  onClick={() => {
                    setEchoes(report.echoes);
                    setTraits(report.traits);
                    setPatterns(report.patterns);
                    setViewMode('report');
                    setCurrentPaper(0);
                  }}
                  style={{
                    padding: '1.5rem',
                    background: 'rgba(255,248,240,0.6)',
                    borderRadius: '16px',
                    border: '1px solid rgba(139,115,85,0.2)',
                    cursor: 'pointer',
                    transition: 'all 0.3s',
                    backdropFilter: 'blur(10px)'
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.transform = 'translateY(-4px)';
                    e.currentTarget.style.boxShadow = '0 8px 24px rgba(139,115,85,0.2)';
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.transform = 'translateY(0)';
                    e.currentTarget.style.boxShadow = 'none';
                  }}
                >
                  <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start',
                    marginBottom: '1rem'
                  }}>
                    <div style={{
                      fontSize: '13px',
                      color: '#8B7355',
                      fontWeight: 500
                    }}>
                      {new Date(report.timestamp).toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit'
                      })}
                    </div>
                    {idx === 0 && (
                      <div style={{
                        fontSize: '10px',
                        fontWeight: 600,
                        color: '#4CAF50',
                        background: 'rgba(76,175,80,0.1)',
                        padding: '4px 8px',
                        borderRadius: '8px',
                        textTransform: 'uppercase',
                        letterSpacing: '0.5px'
                      }}>
                        Latest
                      </div>
                    )}
                  </div>
                  <div style={{
                    display: 'flex',
                    gap: '1rem',
                    fontSize: '12px',
                    color: '#6b5d4f',
                    marginBottom: '0.75rem'
                  }}>
                    <div>{report.stats?.days || 0} days</div>
                    <div>·</div>
                    <div>{report.stats?.entries || 0} entries</div>
                    <div>·</div>
                    <div>{(report.stats?.words || 0).toLocaleString()} words</div>
                  </div>
                  <div style={{
                    display: 'flex',
                    gap: '0.5rem',
                    flexWrap: 'wrap'
                  }}>
                    {report.echoes?.length > 0 && (
                      <span style={{
                        fontSize: '11px',
                        padding: '4px 10px',
                        background: 'rgba(139,115,85,0.1)',
                        borderRadius: '12px',
                        color: '#5d4a3a'
                      }}>
                        {report.echoes.length} echoes
                      </span>
                    )}
                    {report.traits?.length > 0 && (
                      <span style={{
                        fontSize: '11px',
                        padding: '4px 10px',
                        background: 'rgba(139,115,85,0.1)',
                        borderRadius: '12px',
                        color: '#5d4a3a'
                      }}>
                        {report.traits.length} traits
                      </span>
                    )}
                    {report.patterns?.length > 0 && (
                      <span style={{
                        fontSize: '11px',
                        padding: '4px 10px',
                        background: 'rgba(139,115,85,0.1)',
                        borderRadius: '12px',
                        color: '#5d4a3a'
                      }}>
                        {report.patterns.length} patterns
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Analyze Button - Ink stamp style */}
        <div style={{ marginBottom: '3rem', textAlign: 'center' }}>
          <button
            onClick={handleAnalyzeAll}
            disabled={anyLoading}
            style={{
              padding: '16px 48px',
              background: anyLoading ? 'rgba(139,115,85,0.3)' : 'transparent',
              color: anyLoading ? '#999' : '#5d4a3a',
              border: '2px solid',
              borderColor: anyLoading ? '#ccc' : '#8B7355',
              borderRadius: '30px',
              cursor: anyLoading ? 'not-allowed' : 'pointer',
              fontSize: '15px',
              fontWeight: 500,
              fontFamily: 'Georgia, serif',
              transition: 'all 0.3s',
              letterSpacing: '1px',
              textTransform: 'uppercase',
              position: 'relative',
              overflow: 'hidden'
            }}
            onMouseEnter={e => {
              if (!anyLoading) {
                e.currentTarget.style.background = 'rgba(139,115,85,0.12)';
                e.currentTarget.style.transform = 'translateY(-2px)';
                e.currentTarget.style.boxShadow = '0 6px 20px rgba(139,115,85,0.2)';
              }
            }}
            onMouseLeave={e => {
              if (!anyLoading) {
                e.currentTarget.style.background = 'transparent';
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = 'none';
              }
            }}
          >
            {anyLoading ? 'Reflecting...' : 'Generate New Analysis'}
          </button>
        </div>

        {error && (
          <div style={{
            padding: '1rem',
            background: '#fee',
            border: '1px solid #fcc',
            borderRadius: '8px',
            color: '#c33',
            marginBottom: '2rem',
            textAlign: 'center'
          }}>
            {error}
          </div>
        )}

        {/* Empty State - Journal page aesthetic */}
        {!hasAnyData && !anyLoading && (
          <div style={{
            textAlign: 'center',
            padding: '5rem 2rem',
            position: 'relative'
          }}>
            {/* Decorative watercolor wash */}
            <div style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              width: '300px',
              height: '300px',
              borderRadius: '50%',
              background: 'radial-gradient(circle, rgba(139,115,85,0.06) 0%, transparent 70%)',
              filter: 'blur(40px)',
              pointerEvents: 'none'
            }} />

            <div style={{
              fontSize: '72px',
              marginBottom: '1.5rem',
              opacity: 0.3,
              filter: 'grayscale(100%)'
            }}>
              📖
            </div>
            <p style={{
              fontSize: '20px',
              marginBottom: '0.75rem',
              color: '#5d4a3a',
              fontFamily: 'Georgia, serif',
              fontStyle: 'italic',
              fontWeight: 300
            }}>
              Your story awaits analysis
            </p>
            <p style={{
              fontSize: '14px',
              color: '#8B7355',
              maxWidth: '400px',
              margin: '0 auto',
              lineHeight: 1.7
            }}>
              Begin the journey to discover the patterns, themes, and essence woven through your words
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

// @@@ Reusable Components

// @@@ Decorative ink spot background elements
function DecorativeInkSpots() {
  return (
    <>
      <div style={{
        position: 'absolute',
        top: '10%',
        right: '5%',
        width: '120px',
        height: '120px',
        borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(139,115,85,0.08) 0%, rgba(139,115,85,0) 70%)',
        filter: 'blur(20px)',
        pointerEvents: 'none'
      }} />
      <div style={{
        position: 'absolute',
        bottom: '20%',
        left: '8%',
        width: '150px',
        height: '150px',
        borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(160,130,109,0.06) 0%, rgba(160,130,109,0) 70%)',
        filter: 'blur(25px)',
        pointerEvents: 'none'
      }} />
    </>
  );
}

// @@@ Stacked Paper Component - Realistic paper effect with navigation
function PaperStack({
  echoes,
  traits,
  patterns,
  currentPaper,
  onPaperChange
}: {
  echoes: Echo[];
  traits: Trait[];
  patterns: Pattern[];
  currentPaper: number;
  onPaperChange: (index: number) => void;
}) {
  // @@@ Build papers array (only include non-empty ones)
  const papers = [];

  if (echoes.length > 0) {
    papers.push({
      title: 'Recurring Themes',
      subtitle: 'Echoes',
      icon: '🔄',
      content: (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '1rem',
          maxHeight: '500px',
          overflowY: 'auto',
          paddingRight: '1rem'
        }}>
          {echoes.map((echo, idx) => (
            <EchoCard key={idx} echo={echo} />
          ))}
        </div>
      )
    });
  }

  if (traits.length > 0) {
    papers.push({
      title: 'Character Traits',
      subtitle: 'Personality',
      icon: '⭐',
      content: (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
          gap: '1rem',
          maxHeight: '500px',
          overflowY: 'auto',
          paddingRight: '1rem'
        }}>
          {traits.map((trait, idx) => (
            <TraitCard key={idx} trait={trait} />
          ))}
        </div>
      )
    });
  }

  if (patterns.length > 0) {
    papers.push({
      title: 'Behavioral Patterns',
      subtitle: 'Habits',
      icon: '🌀',
      content: (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '1rem',
          maxHeight: '500px',
          overflowY: 'auto',
          paddingRight: '1rem'
        }}>
          {patterns.map((pattern, idx) => (
            <PatternCard key={idx} pattern={pattern} />
          ))}
        </div>
      )
    });
  }

  const totalPapers = papers.length;
  if (totalPapers === 0) return null;

  return (
    <div style={{
      position: 'relative',
      width: '100%',
      maxWidth: '1100px',
      height: '650px',
      margin: '0 auto',
      perspective: '1200px'
    }}>
      {/* Stack of papers */}
      <div style={{
        position: 'absolute',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        marginLeft: '-30px',
        width: '100%',
        maxWidth: '900px',
        height: '600px'
      }}>
        {papers.map((paper, idx) => {
          const isActive = idx === currentPaper;
          const isBehind = idx < currentPaper;
          const offset = isActive ? 0 : isBehind ? -10 : 10;
          const zIndex = isActive ? 10 : isBehind ? totalPapers - idx : idx;

          return (
            <div
              key={idx}
              style={{
                position: 'absolute',
                top: 0,
                left: '50%',
                transform: `translateX(-50%) translateY(${offset}px) rotate(${isActive ? 0 : isBehind ? -0.5 : 0.5}deg)`,
                width: '100%',
                height: '100%',
                transition: 'all 0.6s cubic-bezier(0.34, 1.56, 0.64, 1)',
                opacity: isActive ? 1 : 0.4,
                pointerEvents: isActive ? 'auto' : 'none',
                zIndex
              }}
            >
              {/* Paper sheet with realistic effects */}
              <div style={{
                width: '100%',
                height: '100%',
                background: `
                  linear-gradient(135deg,
                    rgba(255,255,255,0.95) 0%,
                    rgba(255,250,240,0.92) 50%,
                    rgba(255,248,235,0.9) 100%
                  )
                `,
                borderRadius: '3px',
                boxShadow: `
                  0 1px 3px rgba(139,115,85,0.12),
                  0 4px 12px rgba(139,115,85,0.15),
                  0 10px 30px rgba(139,115,85,0.2),
                  inset 0 1px 0 rgba(255,255,255,0.9),
                  inset 0 -1px 0 rgba(139,115,85,0.08)
                `,
                border: '1px solid rgba(139,115,85,0.15)',
                padding: '3rem',
                overflow: 'hidden',
                position: 'relative'
              }}>
                {/* Paper texture overlay */}
                <div style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  right: 0,
                  bottom: 0,
                  backgroundImage: `
                    repeating-linear-gradient(
                      0deg,
                      rgba(139,115,85,0.01) 0px,
                      rgba(139,115,85,0.015) 1px,
                      transparent 1px,
                      transparent 2px
                    ),
                    repeating-linear-gradient(
                      90deg,
                      rgba(139,115,85,0.008) 0px,
                      rgba(139,115,85,0.012) 1px,
                      transparent 1px,
                      transparent 2px
                    )
                  `,
                  pointerEvents: 'none',
                  opacity: 0.7
                }} />

                {/* Decorative watercolor wash */}
                <div style={{
                  position: 'absolute',
                  top: '10%',
                  right: '5%',
                  width: '150px',
                  height: '150px',
                  borderRadius: '50%',
                  background: 'radial-gradient(circle, rgba(160,130,109,0.06) 0%, transparent 70%)',
                  filter: 'blur(30px)',
                  pointerEvents: 'none'
                }} />

                {/* Paper content */}
                <div style={{ position: 'relative', zIndex: 1 }}>
                  {/* Paper header */}
                  <div style={{
                    marginBottom: '2rem',
                    borderBottom: '2px solid rgba(139,115,85,0.15)',
                    paddingBottom: '1rem'
                  }}>
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.75rem',
                      marginBottom: '0.5rem'
                    }}>
                      <span style={{ fontSize: '32px' }}>{paper.icon}</span>
                      <div>
                        <h2 style={{
                          fontSize: '28px',
                          fontWeight: 400,
                          color: '#3d3226',
                          fontFamily: 'Georgia, serif',
                          fontStyle: 'italic',
                          letterSpacing: '-0.3px',
                          margin: 0,
                          lineHeight: 1.2
                        }}>
                          {paper.title}
                        </h2>
                        <div style={{
                          fontSize: '12px',
                          color: '#8B7355',
                          textTransform: 'uppercase',
                          letterSpacing: '1.5px',
                          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                          fontWeight: 500
                        }}>
                          {paper.subtitle}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Paper body */}
                  {paper.content}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Navigation arrows */}
      {totalPapers > 1 && (
        <>
          <button
            onClick={() => onPaperChange(Math.max(0, currentPaper - 1))}
            disabled={currentPaper === 0}
            style={{
              position: 'absolute',
              left: '50%',
              marginLeft: '-540px',
              top: '50%',
              transform: 'translateY(-50%)',
              width: '48px',
              height: '48px',
              borderRadius: '50%',
              background: currentPaper === 0 ? 'rgba(139,115,85,0.1)' : 'rgba(255,255,255,0.95)',
              border: '2px solid rgba(139,115,85,0.2)',
              cursor: currentPaper === 0 ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '20px',
              color: currentPaper === 0 ? '#ccc' : '#5d4a3a',
              transition: 'all 0.3s',
              boxShadow: currentPaper === 0 ? 'none' : '0 4px 12px rgba(139,115,85,0.15)',
              zIndex: 20
            }}
            onMouseEnter={e => {
              if (currentPaper !== 0) {
                e.currentTarget.style.transform = 'translateY(-50%) scale(1.1)';
                e.currentTarget.style.boxShadow = '0 6px 20px rgba(139,115,85,0.25)';
              }
            }}
            onMouseLeave={e => {
              e.currentTarget.style.transform = 'translateY(-50%) scale(1)';
              e.currentTarget.style.boxShadow = currentPaper === 0 ? 'none' : '0 4px 12px rgba(139,115,85,0.15)';
            }}
          >
            ←
          </button>

          <button
            onClick={() => onPaperChange(Math.min(totalPapers - 1, currentPaper + 1))}
            disabled={currentPaper === totalPapers - 1}
            style={{
              position: 'absolute',
              left: '50%',
              marginLeft: '530px',
              top: '50%',
              transform: 'translateY(-50%)',
              width: '48px',
              height: '48px',
              borderRadius: '50%',
              background: currentPaper === totalPapers - 1 ? 'rgba(139,115,85,0.1)' : 'rgba(255,255,255,0.95)',
              border: '2px solid rgba(139,115,85,0.2)',
              cursor: currentPaper === totalPapers - 1 ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '20px',
              color: currentPaper === totalPapers - 1 ? '#ccc' : '#5d4a3a',
              transition: 'all 0.3s',
              boxShadow: currentPaper === totalPapers - 1 ? 'none' : '0 4px 12px rgba(139,115,85,0.15)',
              zIndex: 20
            }}
            onMouseEnter={e => {
              if (currentPaper !== totalPapers - 1) {
                e.currentTarget.style.transform = 'translateY(-50%) scale(1.1)';
                e.currentTarget.style.boxShadow = '0 6px 20px rgba(139,115,85,0.25)';
              }
            }}
            onMouseLeave={e => {
              e.currentTarget.style.transform = 'translateY(-50%) scale(1)';
              e.currentTarget.style.boxShadow = currentPaper === totalPapers - 1 ? 'none' : '0 4px 12px rgba(139,115,85,0.15)';
            }}
          >
            →
          </button>

          {/* Paper indicators */}
          <div style={{
            position: 'absolute',
            bottom: '-40px',
            left: '50%',
            transform: 'translateX(-50%)',
            display: 'flex',
            gap: '10px',
            zIndex: 20
          }}>
            {papers.map((_, idx) => (
              <button
                key={idx}
                onClick={() => onPaperChange(idx)}
                style={{
                  width: '12px',
                  height: '12px',
                  borderRadius: '50%',
                  background: idx === currentPaper ? '#8B7355' : 'rgba(139,115,85,0.3)',
                  border: 'none',
                  cursor: 'pointer',
                  transition: 'all 0.3s',
                  padding: 0
                }}
                onMouseEnter={e => {
                  if (idx !== currentPaper) {
                    e.currentTarget.style.background = 'rgba(139,115,85,0.5)';
                    e.currentTarget.style.transform = 'scale(1.2)';
                  }
                }}
                onMouseLeave={e => {
                  if (idx !== currentPaper) {
                    e.currentTarget.style.background = 'rgba(139,115,85,0.3)';
                    e.currentTarget.style.transform = 'scale(1)';
                  }
                }}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function VintageStatLabel({ label, value }: { label: string; value: number | string }) {
  return (
    <div style={{
      display: 'inline-flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: '0.5rem'
    }}>
      <div style={{
        fontSize: '36px',
        fontWeight: 300,
        color: '#5d4a3a',
        fontFamily: 'Georgia, serif',
        lineHeight: 1
      }}>
        {value}
      </div>
      <div style={{
        fontSize: '11px',
        color: '#8B7355',
        fontWeight: 500,
        textTransform: 'uppercase',
        letterSpacing: '1.5px',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        borderTop: '1px solid rgba(139,115,85,0.3)',
        paddingTop: '0.5rem'
      }}>
        {label}
      </div>
    </div>
  );
}

function EchoCard({ echo }: { echo: Echo }) {
  return (
    <div style={{
      background: 'rgba(255,248,240,0.6)',
      padding: '1.75rem',
      borderRadius: '16px',
      border: '1px solid rgba(139,115,85,0.2)',
      transition: 'all 0.3s',
      position: 'relative',
      backdropFilter: 'blur(10px)'
    }}>
      <h3 style={{
        fontSize: '19px',
        fontWeight: 500,
        color: '#3d3226',
        marginBottom: '1rem',
        fontFamily: 'Georgia, serif',
        fontStyle: 'italic',
        position: 'relative'
      }}>
        {echo.title}
      </h3>
      <p style={{
        color: '#5d4a3a',
        lineHeight: 1.8,
        marginBottom: '1.25rem',
        fontSize: '14px'
      }}>
        {echo.description}
      </p>
      {echo.examples && echo.examples.length > 0 && (
        <div>
          <div style={{
            fontSize: '10px',
            fontWeight: 600,
            color: '#8B7355',
            marginBottom: '0.75rem',
            textTransform: 'uppercase',
            letterSpacing: '1px',
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
          }}>
            Echoes
          </div>
          {echo.examples.map((ex: string, i: number) => (
            <div
              key={i}
              style={{
                padding: '1rem',
                background: 'rgba(255,255,255,0.7)',
                borderLeft: '4px solid rgba(139,115,85,0.4)',
                marginBottom: '0.75rem',
                fontSize: '13px',
                fontStyle: 'italic',
                color: '#5d4a3a',
                borderRadius: '0 8px 8px 0',
                lineHeight: 1.6
              }}
            >
              "{ex}"
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function TraitCard({ trait }: { trait: Trait }) {
  return (
    <div style={{
      background: 'rgba(255,252,247,0.7)',
      padding: '1.75rem',
      borderRadius: '18px',
      border: '1px solid rgba(139,115,85,0.2)',
      transition: 'all 0.3s',
      position: 'relative',
      backdropFilter: 'blur(8px)'
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        marginBottom: '1.25rem'
      }}>
        <h3 style={{
          fontSize: '18px',
          fontWeight: 500,
          color: '#3d3226',
          fontFamily: 'Georgia, serif',
          fontStyle: 'italic',
          flex: 1
        }}>
          {trait.trait}
        </h3>
        <div style={{
          fontSize: '12px',
          fontWeight: 600,
          color: '#8B7355',
          background: 'rgba(139,115,85,0.1)',
          padding: '6px 12px',
          borderRadius: '20px',
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          border: '1px solid rgba(139,115,85,0.2)',
          marginLeft: '1rem'
        }}>
          {trait.strength}/5
        </div>
      </div>

      {/* Organic strength indicator */}
      <div style={{
        display: 'flex',
        gap: '6px',
        marginBottom: '1.25rem'
      }}>
        {[1, 2, 3, 4, 5].map(i => (
          <div
            key={i}
            style={{
              flex: 1,
              height: '6px',
              borderRadius: '3px',
              background: i <= trait.strength
                ? 'linear-gradient(90deg, rgba(139,115,85,0.6), rgba(160,130,109,0.4))'
                : 'rgba(139,115,85,0.1)',
              transition: 'all 0.4s',
              opacity: i <= trait.strength ? 1 : 0.4
            }}
          />
        ))}
      </div>

      <p style={{
        color: '#5d4a3a',
        lineHeight: 1.8,
        fontSize: '13px'
      }}>
        {trait.evidence}
      </p>
    </div>
  );
}

function PatternCard({ pattern }: { pattern: Pattern }) {
  return (
    <div style={{
      background: 'rgba(255,250,242,0.6)',
      padding: '1.75rem',
      borderRadius: '16px',
      border: '1px solid rgba(139,115,85,0.2)',
      transition: 'all 0.3s',
      position: 'relative',
      backdropFilter: 'blur(10px)'
    }}>
      <h3 style={{
        fontSize: '19px',
        fontWeight: 500,
        color: '#3d3226',
        marginBottom: '1rem',
        fontFamily: 'Georgia, serif',
        fontStyle: 'italic',
        position: 'relative'
      }}>
        {pattern.pattern}
      </h3>
      <p style={{
        color: '#5d4a3a',
        lineHeight: 1.8,
        marginBottom: '1.25rem',
        fontSize: '14px'
      }}>
        {pattern.description}
      </p>
      <div style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.5rem',
        fontSize: '12px',
        color: '#8B7355',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        background: 'rgba(139,115,85,0.08)',
        padding: '6px 14px',
        borderRadius: '20px',
        border: '1px solid rgba(139,115,85,0.15)'
      }}>
        <span style={{ fontWeight: 600 }}>Frequency:</span>
        <span style={{ fontStyle: 'italic' }}>{pattern.frequency}</span>
      </div>
    </div>
  );
}

