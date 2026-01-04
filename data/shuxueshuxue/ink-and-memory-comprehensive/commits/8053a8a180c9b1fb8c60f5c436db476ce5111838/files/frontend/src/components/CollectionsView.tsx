import { useState, useEffect, useLayoutEffect, useRef } from 'react';
import type { Commentor } from '../engine/EditorEngine';
import { findNormalizedPhrase } from '../utils/textNormalize';
import { useAuth } from '../contexts/AuthContext';
import { STORAGE_KEYS } from '../constants/storageKeys';

// @@@ TypeScript interfaces
interface TimelineDay {
  date: string;
  isPast: boolean;
  isFuture: boolean;
  isToday: boolean;
  daysOffset: number;
}

export default function CollectionsView({ isVisible, voiceConfigs }: { isVisible: boolean; voiceConfigs: Record<string, any> }) {
  return (
    <div style={{
      width: '100%',
      height: '100%',
      display: 'flex',
      fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
      background: '#f8f0e6',
      overflow: 'hidden'
    }}>
      <TimelinePage isVisible={isVisible} voiceConfigs={voiceConfigs} />
    </div>
  );
}

// @@@ Extract complete sentence containing a phrase
function extractCompleteSentence(text: string, phrase: string): string {
  // Find phrase position (with normalization)
  const phraseIndex = findNormalizedPhrase(text, phrase);
  if (phraseIndex === -1) {
    return phrase; // Fallback if phrase not found
  }

  // Sentence ending markers
  const sentenceEndings = '.!?。！？\n';

  // Find sentence start - go backwards to find previous sentence ending or start of text
  let sentenceStart = 0;
  for (let i = phraseIndex - 1; i >= 0; i--) {
    if (sentenceEndings.includes(text[i])) {
      sentenceStart = i + 1;
      break;
    }
  }

  // Find sentence end - go forwards to find next sentence ending
  let sentenceEnd = text.length;
  for (let i = phraseIndex + phrase.length; i < text.length; i++) {
    if (sentenceEndings.includes(text[i])) {
      sentenceEnd = i + 1;
      break;
    }
  }

  // Extract sentence and trim whitespace
  return text.slice(sentenceStart, sentenceEnd).trim();
}

// @@@ Helper to get icon emoji
function getIconForVoice(icon: string): string {
  const iconMap: Record<string, string> = {
    brain: '🧠',
    heart: '❤️',
    question: '❓',
    cloud: '☁️',
    masks: '🎭',
    eye: '👁️',
    fist: '✊',
    lightbulb: '💡',
    shield: '🛡️',
    wind: '💨',
    fire: '🔥',
    compass: '🧭'
  };
  return iconMap[icon] || '💭';
}

// @@@ Helper to format dates consistently
// @@@ Helper to get date in local timezone as YYYY-MM-DD
// Prevents timezone issues where UTC date differs from user's local date
function getLocalDateString(date?: Date | string): string {
  const d = date ? new Date(date) : new Date();
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function formatDate(date: Date | string): string {
  return new Date(date).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });
}

// @@@ Generate timeline days (7 past + today + 7 future)
// Returns dates in YYYY-MM-DD format to match database storage
function generateTimelineDays(): TimelineDay[] {
  const today = new Date();
  const todayStr = getLocalDateString(today);
  const allTimelineDays: TimelineDay[] = [];

  // Add past 7 days
  for (let i = 7; i >= 1; i--) {
    const pastDate = new Date(today);
    pastDate.setDate(today.getDate() - i);
    allTimelineDays.push({
      date: getLocalDateString(pastDate),
      isPast: true,
      isFuture: false,
      isToday: false,
      daysOffset: -i
    });
  }

  // Add today
  allTimelineDays.push({
    date: todayStr,
    isPast: false,
    isFuture: false,
    isToday: true,
    daysOffset: 0
  });

  // Add future 7 days
  for (let i = 1; i <= 7; i++) {
    const futureDate = new Date(today);
    futureDate.setDate(today.getDate() + i);
    allTimelineDays.push({
      date: getLocalDateString(futureDate),
      isPast: false,
      isFuture: true,
      isToday: false,
      daysOffset: i
    });
  }

  return allTimelineDays;
}

// @@@ Helper function for interesting placeholders
function getPlaceholderText(daysOffset: number): string {
  if (daysOffset === 0) return 'Click to generate';

  const placeholders: Record<string, string> = {
    '-7': 'taste buds renew every 10 days',
    '-6': 'the liver regenerates in 6 weeks',
    '-5': 'stomach lining replaces itself every 5 days',
    '-4': 'skin cells shed every 2-4 weeks',
    '-3': 'red blood cells live for 120 days',
    '-2': 'the heart beats 100,000 times a day',
    '-1': 'neurons can form new connections',
    '1': 'tomorrow is unwritten',
    '2': 'the future is a blank page',
    '3': 'time flows forward',
    '4': 'days ahead unknown',
    '5': 'yet to unfold',
    '6': 'still becoming',
    '7': 'awaiting experience'
  };

  return placeholders[daysOffset.toString()] || (daysOffset < 0 ? 'what was has passed' : 'yet to be written');
}

// @@@ Get all notes from all sessions (localStorage for guest, database for authenticated)
async function getAllNotesFromSessions(isAuthenticated: boolean): Promise<string> {
  const allText: string[] = [];

  if (isAuthenticated) {
    // @@@ Load from database for authenticated users
    try {
      const { listSessions, getSession } = await import('../api/voiceApi');
      const sessions = await listSessions();

      for (const session of sessions) {
        try {
          const fullSession = await getSession(session.id);
          if (fullSession.editor_state?.cells) {
            const text = fullSession.editor_state.cells
              .filter((c: any) => c.type === 'text')
              .map((c: any) => c.content)
              .join('\n\n');
            if (text.trim()) {
              allText.push(text);
            }
          }
        } catch (err) {
          console.error(`Failed to load session ${session.id}:`, err);
        }
      }
    } catch (error) {
      console.error('Failed to load sessions from database:', error);
    }
  } else {
    // @@@ Load from localStorage for guests
    const keys = Object.keys(localStorage);
    for (const key of keys) {
      if (key === STORAGE_KEYS.EDITOR_STATE || key.startsWith(`${STORAGE_KEYS.EDITOR_STATE}_`)) {
        try {
          const state = JSON.parse(localStorage.getItem(key) || '{}');
          if (state.cells) {
            const text = state.cells
              .filter((c: any) => c.type === 'text')
              .map((c: any) => c.content)
              .join('\n\n');
            if (text.trim()) {
              allText.push(text);
            }
          }
        } catch (e) {
          console.error('Failed to parse session:', key, e);
        }
      }
    }
  }

  return allText.join('\n\n---\n\n');
}

// @@@ Timeline page - combines pictures and comments by date
function TimelinePage({ isVisible, voiceConfigs }: { isVisible: boolean; voiceConfigs: Record<string, any> }) {
  const { isAuthenticated } = useAuth();
  const [starredComments, setStarredComments] = useState<Commentor[]>([]);
  const [allCommentsByDate, setAllCommentsByDate] = useState<Map<string, Commentor[]>>(new Map());
  const [pictures, setPictures] = useState<Array<{ date: string; base64: string; full_base64?: string; prompt: string }>>([]);
  const [generatingForDate, setGeneratingForDate] = useState<string | null>(null);
  const [viewingImage, setViewingImage] = useState<{ base64: string; full_base64?: string; prompt: string; date: string } | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);
  const [loadingCommentsForDate, setLoadingCommentsForDate] = useState<string | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const loadData = async () => {
      // @@@ Load all comments grouped by date from database if authenticated, localStorage if guest
      if (isAuthenticated) {
        try {
          const { listSessions, getSession } = await import('../api/voiceApi');
          const sessions = await listSessions();
          const allStarred: Commentor[] = [];
          const commentsByDate = new Map<string, Commentor[]>();

          for (const session of sessions) {
            try {
              const fullSession = await getSession(session.id);
              const comments = fullSession.editor_state?.commentors || [];

              // Collect starred comments for timeline cards
              const starred = comments.filter((c: Commentor) => c.feedback === 'star');
              allStarred.push(...starred);

              // Group ALL comments by date (for image modal display)
              // @@@ Use each comment's appliedAt timestamp (not session's created_at) to handle timezone properly
              comments.filter((c: Commentor) => c.appliedAt).forEach((comment: Commentor) => {
                const commentDate = new Date(comment.appliedAt || comment.computedAt);
                const date = getLocalDateString(commentDate);
                if (!commentsByDate.has(date)) {
                  commentsByDate.set(date, []);
                }
                commentsByDate.get(date)!.push(comment);
              });
            } catch (err) {
              console.error(`Failed to load session ${session.id}:`, err);
            }
          }

          setStarredComments(allStarred);
          setAllCommentsByDate(commentsByDate);
        } catch (error) {
          console.error('Failed to load comments from database:', error);
        }
      } else {
        // Guest mode: load from localStorage
        const savedState = localStorage.getItem(STORAGE_KEYS.EDITOR_STATE);
        if (savedState) {
          try {
            const state = JSON.parse(savedState);
            const starred = state.commentors?.filter((c: Commentor) => c.feedback === 'star') || [];
            setStarredComments(starred);

            // For guest mode, all comments are from today
            const today = formatDate(new Date());
            const allComments = state.commentors?.filter((c: Commentor) => c.appliedAt) || [];
            const commentsByDate = new Map<string, Commentor[]>();
            if (allComments.length > 0) {
              commentsByDate.set(today, allComments);
            }
            setAllCommentsByDate(commentsByDate);
          } catch (e) {
            console.error('Failed to load comments:', e);
          }
        }
      }

      // @@@ Load pictures from database if authenticated
      if (isAuthenticated) {
        try {
          const { getDailyPictures } = await import('../api/voiceApi');
          const dbPictures = await getDailyPictures(30);
          // @@@ Backend returns ONLY thumbnails for fast loading (full images loaded on-demand)
          const formattedPictures = dbPictures.map(p => ({
            date: p.date,
            base64: p.base64,  // Thumbnail only
            prompt: p.prompt || ''
          }));
          setPictures(formattedPictures);
        } catch (error) {
          console.error('Failed to load pictures from database:', error);
          // Fallback to localStorage
          const savedPictures = localStorage.getItem(STORAGE_KEYS.DAILY_PICTURES);
          if (savedPictures) {
            try {
              const parsed = JSON.parse(savedPictures);
              // @@@ Strip full_base64 from old cached data (keep only thumbnails)
              const thumbnailsOnly = parsed.map((p: any) => ({
                date: p.date,
                base64: p.base64,
                prompt: p.prompt
              }));
              setPictures(thumbnailsOnly);
            } catch (e) {
              console.error('Failed to load pictures:', e);
            }
          }
        }
      } else {
        // Guest mode: load from localStorage
        const savedPictures = localStorage.getItem(STORAGE_KEYS.DAILY_PICTURES);
        if (savedPictures) {
          try {
            const parsed = JSON.parse(savedPictures);
            // @@@ Strip full_base64 from old cached data (keep only thumbnails)
            const thumbnailsOnly = parsed.map((p: any) => ({
              date: p.date,
              base64: p.base64,
              prompt: p.prompt
            }));
            setPictures(thumbnailsOnly);
          } catch (e) {
            console.error('Failed to load pictures:', e);
          }
        }
      }

      setInitialLoading(false);
    };

    loadData();
  }, [isAuthenticated]);

  // @@@ Group items by date (using YYYY-MM-DD format to match timeline days)
  const timelineByDate = new Map<string, { picture?: any; comments: Commentor[] }>();

  starredComments.forEach(comment => {
    const commentDate = new Date(comment.appliedAt || comment.computedAt);
    const date = getLocalDateString(commentDate);  // Convert to YYYY-MM-DD
    if (!timelineByDate.has(date)) {
      timelineByDate.set(date, { comments: [] });
    }
    timelineByDate.get(date)!.comments.push(comment);
  });

  pictures.forEach(pic => {
    const date = pic.date;  // Already in YYYY-MM-DD format from database
    if (!timelineByDate.has(date)) {
      timelineByDate.set(date, { comments: [] });
    }
    timelineByDate.get(date)!.picture = pic;
  });

  // @@@ Set initial scroll position to center on today's card
  // Use useLayoutEffect to position BEFORE browser paints (prevents flash)
  useLayoutEffect(() => {
    // @@@ Only center when timeline is visible AND data has loaded
    if (!isVisible || initialLoading) return;

    // Double RAF to ensure layout is complete
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        if (scrollContainerRef.current) {
          // Today is at index 7 (after 7 past days)
          // Each card is 500px + 4rem gap (64px) = 564px
          // Plus left padding of 4rem (64px)
          const cardWidth = 500 + 64;
          const todayIndex = 7;
          const leftPadding = 64;
          const containerWidth = scrollContainerRef.current.clientWidth;

          // Center today's card
          const scrollLeft = leftPadding + (todayIndex * cardWidth) - (containerWidth / 2) + (250);
          scrollContainerRef.current.scrollLeft = scrollLeft;
        }
      });
    });
  }, [isVisible, initialLoading]);

  // @@@ Reload comments for a specific date from backend
  const reloadCommentsForDate = async (dateStr: string) => {
    // dateStr is in YYYY-MM-DD format
    setLoadingCommentsForDate(dateStr);

    try {
      if (isAuthenticated) {
        const { listSessions, getSession } = await import('../api/voiceApi');
        const sessions = await listSessions();
        const commentsForDate: Commentor[] = [];

        for (const session of sessions) {
          // @@@ Get all comments from session and group by their appliedAt timestamp
          try {
            const fullSession = await getSession(session.id);
            const comments = fullSession.editor_state?.commentors || [];

            // Filter comments that belong to this date (using appliedAt timestamp, not session created_at)
            comments.filter((c: Commentor) => c.appliedAt).forEach((comment: Commentor) => {
              const commentDate = new Date(comment.appliedAt || comment.computedAt);
              const date = getLocalDateString(commentDate);
              if (date === dateStr) {
                commentsForDate.push(comment);
              }
            });
          } catch (err) {
            console.error(`Failed to load session ${session.id}:`, err);
          }
        }

        // Update allCommentsByDate for this specific date (using YYYY-MM-DD as key)
        setAllCommentsByDate(prev => {
          const next = new Map(prev);
          next.set(dateStr, commentsForDate);
          return next;
        });
      }
    } catch (error) {
      console.error('Failed to reload comments for date:', error);
    } finally {
      setLoadingCommentsForDate(null);
    }
  };

  const handleImageClick = async (picture: { base64: string; full_base64?: string; prompt: string; date: string }) => {
    setViewingImage(picture);

    // Load full image on-demand if not already loaded
    if (!picture.full_base64 && isAuthenticated) {
      try {
        const { getDailyPictureFull } = await import('../api/voiceApi');
        const fullImage = await getDailyPictureFull(picture.date);

        // Update the picture object with full image
        const updatedPicture = { ...picture, full_base64: fullImage };
        setViewingImage(updatedPicture);

        // Also update pictures array so we don't reload next time
        setPictures(prev => prev.map(p =>
          p.date === picture.date ? updatedPicture : p
        ));
      } catch (error) {
        console.error('Failed to load full image:', error);
      }
    }

    await reloadCommentsForDate(picture.date);
  };

  const handleGenerateForDate = async (dateStr: string) => {
    // @@@ Block image generation for guests
    if (!isAuthenticated) {
      alert('Please log in to generate images. Image generation requires authentication.');
      return;
    }

    setGeneratingForDate(dateStr);

    try {
      const allNotes = await getAllNotesFromSessions(isAuthenticated);
      if (!allNotes.trim()) {
        alert('Write some notes first to generate an image!');
        return;
      }

      const { generateDailyPicture, saveDailyPicture } = await import('../api/voiceApi');
      const { image_base64, thumbnail_base64, prompt } = await generateDailyPicture(allNotes);

      // @@@ Use the dateStr parameter passed from the clicked card (already in YYYY-MM-DD format)
      const pictureDate = dateStr;

      const newPicture = {
        date: pictureDate,  // @@@ Use date from clicked card
        base64: thumbnail_base64 || image_base64,  // @@@ Only thumbnail for fast timeline
        prompt: prompt
        // @@@ NO full_base64 - it will be loaded on-demand when clicking
      };

      // @@@ Save to database (requires auth)
      await saveDailyPicture(pictureDate, image_base64, prompt, thumbnail_base64);

      // @@@ Update local state - remove old picture for this date if exists
      const updated = pictures.filter(p => p.date !== pictureDate);

      updated.unshift(newPicture);
      setPictures(updated);
    } catch (error) {
      console.error('Image generation failed:', error);
      alert('Failed to generate image. Please try again.');
    } finally {
      setGeneratingForDate(null);
    }
  };

  if (initialLoading) {
    return null;
  }

  // @@@ Generate all timeline days using helper function (always show timeline structure)
  const allTimelineDays = generateTimelineDays();

  return (
    <div
      ref={scrollContainerRef}
      style={{
        width: '100%',
        height: '100%',
        background: '#f8f0e6',
        overflowX: 'auto',
        overflowY: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        padding: '3rem 0'
      }}>
      {/* @@@ Horizontal scrolling timeline - cards side by side */}
      <div style={{
        display: 'flex',
        flexDirection: 'row',
        gap: '4rem',
        padding: '0 4rem',
        minHeight: 0,
        flex: 1
      }}>
        {allTimelineDays.map((day, index) => {
          const dayData = timelineByDate.get(day.date);
          const hasData = !!dayData;
          const isGenerating = generatingForDate === day.date;

          return (
            <div
              key={day.date}
              style={{
                display: 'flex',
                flexDirection: 'column',
                minWidth: '500px',
                maxWidth: '500px',
                position: 'relative'
              }}>
              {/* Timeline node and line */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                marginBottom: '2rem',
                position: 'relative'
              }}>
                {/* Line before node */}
                {index > 0 && (
                  <div style={{
                    position: 'absolute',
                    right: 'calc(50% + 12px)',
                    width: 'calc(4rem + 50%)',
                    height: '3px',
                    background: '#d0c4b0'
                  }} />
                )}

                {/* Timeline node */}
                <div style={{
                  width: '24px',
                  height: '24px',
                  borderRadius: '50%',
                  background: hasData ? '#4CAF50' : (day.isToday ? '#888' : '#ddd'),
                  border: '3px solid #f8f0e6',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
                  margin: '0 auto',
                  position: 'relative',
                  zIndex: 2
                }} />

                {/* Line after node */}
                {index < allTimelineDays.length - 1 && (
                  <div style={{
                    position: 'absolute',
                    left: 'calc(50% + 12px)',
                    width: 'calc(4rem + 50%)',
                    height: '3px',
                    background: '#d0c4b0'
                  }} />
                )}
              </div>

              {/* Date header */}
              <div style={{
                fontSize: '16px',
                fontWeight: 600,
                color: day.isToday ? '#2c2c2c' : '#666',
                textAlign: 'center',
                marginBottom: '1.5rem'
              }}>
                {day.isToday ? 'Today' : formatDate(day.date)}
              </div>

              {/* Card content */}
              <div style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '1rem',
                flex: 1
              }}>
                {/* Image */}
                <div style={{ flexShrink: 0 }}>
                  {dayData?.picture ? (
                    <div style={{
                      position: 'relative',
                      background: '#fff',
                      border: '1px solid #d0c4b0',
                      borderRadius: '8px',
                      overflow: 'hidden',
                      cursor: 'pointer',
                      transition: 'all 0.2s'
                    }}
                    onClick={() => handleImageClick(dayData.picture)}
                    onMouseEnter={e => {
                      e.currentTarget.style.transform = 'scale(1.02)';
                      e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.transform = 'scale(1)';
                      e.currentTarget.style.boxShadow = 'none';
                    }}
                    >
                      <img
                        src={`data:image/${dayData.picture.base64?.startsWith('iVBOR') ? 'png' : 'jpeg'};base64,${dayData.picture.base64}`}
                        alt={dayData.picture.prompt}
                        style={{
                          width: '100%',
                          aspectRatio: '1',
                          objectFit: 'cover'
                        }}
                      />
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (!isGenerating) handleGenerateForDate(day.date);
                        }}
                        disabled={isGenerating}
                        style={{
                          position: 'absolute',
                          top: '0.75rem',
                          right: '0.75rem',
                          width: '32px',
                          height: '32px',
                          borderRadius: '50%',
                          background: 'rgba(255, 255, 255, 0.95)',
                          border: 'none',
                          cursor: isGenerating ? 'wait' : 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          opacity: 0.9,
                          transition: 'all 0.2s'
                        }}
                        onMouseEnter={e => {
                          if (!isGenerating) e.currentTarget.style.opacity = '1';
                        }}
                        onMouseLeave={e => {
                          e.currentTarget.style.opacity = '0.9';
                        }}
                        title="Redraw image"
                      >
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/>
                        </svg>
                      </button>
                    </div>
                  ) : (
                    <div
                      onClick={() => day.isToday && !isGenerating && handleGenerateForDate(day.date)}
                      style={{
                        width: '100%',
                        aspectRatio: '1',
                        background: day.isFuture ? 'linear-gradient(135deg, #f8f0e6 0%, #ede3d5 100%)' : 'linear-gradient(135deg, #f0e8de 0%, #e5dbc9 100%)',
                        border: day.isFuture ? '2px dashed #d0c4b0' : '2px dashed #b8a896',
                        borderRadius: '8px',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        cursor: day.isToday ? (isGenerating ? 'wait' : 'pointer') : 'default',
                        gap: '0.75rem',
                        opacity: day.isPast || day.isFuture ? 0.4 : 1,
                        transition: 'all 0.2s'
                      }}
                      onMouseEnter={e => {
                        if (day.isToday && !isGenerating) {
                          e.currentTarget.style.opacity = '1';
                        }
                      }}
                      onMouseLeave={e => {
                        if (day.isToday && !isGenerating) {
                          e.currentTarget.style.opacity = '1';
                        } else if (day.isPast) {
                          e.currentTarget.style.opacity = '0.4';
                        }
                      }}
                    >
                      <div style={{
                        fontSize: '15px',
                        color: '#999',
                        fontWeight: 500,
                        fontStyle: 'italic',
                        textAlign: 'center',
                        lineHeight: '1.8',
                        padding: '0 3rem'
                      }}>
                        {isGenerating ? 'Generating...' : getPlaceholderText(day.daysOffset)}
                      </div>
                    </div>
                  )}
                </div>

                {/* Simple metadata */}
                {(dayData?.comments && dayData.comments.length > 0) && (
                  <div style={{
                    textAlign: 'center',
                    padding: '1rem',
                    background: 'rgba(255, 255, 255, 0.5)',
                    borderRadius: '6px',
                    fontSize: '13px',
                    color: '#888',
                    fontStyle: 'italic'
                  }}>
                    {dayData.comments.length} {dayData.comments.length === 1 ? 'entry' : 'entries'}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Image Lightbox Modal */}
      {viewingImage && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.6)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
            padding: '3rem'
          }}
          onClick={() => setViewingImage(null)}
        >
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              maxWidth: '1400px',
              width: '100%',
              maxHeight: '90vh',
              background: '#fff',
              borderRadius: '12px',
              overflow: 'hidden',
              boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
              marginTop: '2rem'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Main content: Image + Comments */}
            <div style={{
              display: 'flex',
              flex: 1,
              minHeight: 0,
              overflow: 'hidden'
            }}>
              {/* Image on left */}
              <div style={{
                flex: '0 0 55%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: '#000',
                position: 'relative'
              }}>
                <img
                  src={`data:image/${(viewingImage.full_base64 || viewingImage.base64)?.startsWith('iVBOR') ? 'png' : 'jpeg'};base64,${viewingImage.full_base64 || viewingImage.base64}`}
                  alt="Generated image"
                  style={{
                    maxWidth: '100%',
                    maxHeight: '100%',
                    objectFit: 'contain'
                  }}
                />
                {/* Close button */}
                <button
                  onClick={() => setViewingImage(null)}
                  style={{
                    position: 'absolute',
                    top: '1.5rem',
                    right: '1.5rem',
                    background: 'rgba(255, 255, 255, 0.95)',
                    border: 'none',
                    borderRadius: '50%',
                    width: '36px',
                    height: '36px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '22px',
                    color: '#333',
                    fontWeight: 'bold',
                    transition: 'all 0.2s',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.2)'
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.background = '#f0f0f0';
                    e.currentTarget.style.transform = 'scale(1.1)';
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.background = 'rgba(255, 255, 255, 0.95)';
                    e.currentTarget.style.transform = 'scale(1)';
                  }}
                >
                  ×
                </button>
              </div>

              {/* Starred comments on right */}
              <div style={{
                flex: '0 0 45%',
                background: '#f9f7f4',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                minWidth: 0
              }}>
                {/* Header */}
                <div style={{
                  padding: '2rem 2rem 1rem',
                  borderBottom: '1px solid #e0d8cc',
                  flexShrink: 0
                }}>
                  <div style={{
                    fontSize: '13px',
                    color: '#aaa',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.1em'
                  }}>
                    Starred Comments
                  </div>
                </div>

                {/* Comments list - scrollable */}
                <div style={{
                  flex: 1,
                  overflowY: 'auto',
                  overflowX: 'hidden',
                  padding: '1.5rem 2rem',
                  minWidth: 0,
                  width: '100%',
                  boxSizing: 'border-box'
                }}>
                  {(() => {
                    // @@@ Priority filtering: starred → chatted → last → none
                    // Use raw YYYY-MM-DD format to match Map keys
                    const imageDate = viewingImage.date;

                    // Show loading state while fetching comments
                    if (loadingCommentsForDate === imageDate) {
                      return (
                        <div style={{
                          textAlign: 'center',
                          color: '#999',
                          fontSize: '14px',
                          fontStyle: 'italic',
                          padding: '2rem 1rem'
                        }}>
                          Loading comments...
                        </div>
                      );
                    }

                    const allCommentsForDate = allCommentsByDate.get(imageDate) || [];

                    let commentsToDisplay: Commentor[] = [];

                    // Priority 1: Starred comments
                    const starredForDate = allCommentsForDate.filter(c => c.feedback === 'star');
                    if (starredForDate.length > 0) {
                      commentsToDisplay = starredForDate;
                    } else {
                      // Priority 2: One chatted comment (has chatHistory)
                      const chattedComments = allCommentsForDate.filter(c => c.chatHistory && c.chatHistory.length > 0);
                      if (chattedComments.length > 0) {
                        // Take the most recent chatted comment
                        const mostRecentChatted = chattedComments.sort((a, b) =>
                          (b.appliedAt || b.computedAt) - (a.appliedAt || a.computedAt)
                        )[0];
                        commentsToDisplay = [mostRecentChatted];
                      } else {
                        // Priority 3: Last comment (by timestamp)
                        if (allCommentsForDate.length > 0) {
                          const lastComment = allCommentsForDate.sort((a, b) =>
                            (b.appliedAt || b.computedAt) - (a.appliedAt || a.computedAt)
                          )[0];
                          commentsToDisplay = [lastComment];
                        }
                      }
                    }

                    if (commentsToDisplay.length === 0) {
                      return (
                        <div style={{
                          textAlign: 'center',
                          color: '#999',
                          fontSize: '14px',
                          fontStyle: 'italic',
                          padding: '2rem 1rem'
                        }}>
                          No comments for this day
                        </div>
                      );
                    }

                    return (
                      <div style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '1rem',
                        minWidth: 0
                      }}>
                        {commentsToDisplay.map((comment) => (
                          <div
                            key={comment.id}
                            style={{
                              background: '#fff',
                              border: '1px solid #e0d8cc',
                              borderRadius: '8px',
                              padding: '1rem',
                              transition: 'all 0.2s',
                              minWidth: 0
                            }}
                          >
                            <div style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.5rem',
                              marginBottom: '0.75rem',
                              minWidth: 0
                            }}>
                              <span style={{ fontSize: '18px', flexShrink: 0 }}>{getIconForVoice(comment.icon)}</span>
                              <span style={{ fontWeight: 600, fontSize: '14px', color: '#333', flexShrink: 0 }}>{voiceConfigs[comment.voice]?.name || comment.voice}</span>
                              {comment.feedback === 'star' && (
                                <span style={{ fontSize: '14px', marginLeft: 'auto', flexShrink: 0 }}>⭐</span>
                              )}
                              {comment.chatHistory && comment.chatHistory.length > 0 && (
                                <span style={{ fontSize: '14px', marginLeft: comment.feedback === 'star' ? '0.5rem' : 'auto', flexShrink: 0 }}>💬</span>
                              )}
                            </div>
                            <div style={{
                              fontSize: '12px',
                              fontStyle: 'italic',
                              color: '#999',
                              marginBottom: '0.75rem',
                              paddingLeft: '1.5rem',
                              borderLeft: '2px solid #e0d8cc',
                              wordBreak: 'break-word',
                              overflowWrap: 'anywhere',
                              minWidth: 0
                            }}>
                              "{extractCompleteSentence(comment.textSnapshot || '', comment.phrase)}"
                            </div>
                            <div style={{
                              fontSize: '13px',
                              color: '#555',
                              lineHeight: '1.7',
                              paddingLeft: '0.5rem',
                              wordBreak: 'break-word',
                              overflowWrap: 'anywhere',
                              whiteSpace: 'pre-wrap',
                              minWidth: 0
                            }}>
                              {comment.comment}
                            </div>
                          </div>
                        ))}
                      </div>
                    );
                  })()}
                </div>
              </div>
            </div>

            {/* Bottom metadata bar */}
            <div style={{
              borderTop: '1px solid #e0d8cc',
              background: '#f0e8de',
              padding: '1rem 2rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexShrink: 0
            }}>
              <div style={{
                fontSize: '13px',
                color: '#666'
              }}>
                {new Date(viewingImage.date).toLocaleDateString('en-US', {
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric'
                })}
              </div>
              <div style={{
                fontSize: '13px',
                color: '#888'
              }}>
                {(() => {
                  const dateData = Array.from(timelineByDate.entries()).find(([_, data]) =>
                    data.picture?.base64 === viewingImage.base64
                  );
                  const commentCount = dateData?.[1]?.comments?.length || 0;
                  return `${commentCount} ${commentCount === 1 ? 'entry' : 'entries'}`;
                })()}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// @@@ Analysis Page (placeholder for echoes/traits/patterns)
