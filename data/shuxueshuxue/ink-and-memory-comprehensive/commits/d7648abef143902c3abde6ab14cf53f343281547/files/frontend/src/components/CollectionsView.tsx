import { useState, useEffect, useLayoutEffect, useRef, useMemo, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import type { Commentor } from '../engine/EditorEngine';
import { findNormalizedPhrase } from '../utils/textNormalize';
import { useAuth } from '../contexts/AuthContext';
import { STORAGE_KEYS } from '../constants/storageKeys';
import { getDateLocale } from '../i18n';
import type { Friend } from '../api/voiceApi';

// @@@ TypeScript interfaces
interface TimelineDay {
  date: string;
  isPast: boolean;
  isFuture: boolean;
  isToday: boolean;
  daysOffset: number;
}

type TimelinePicture = {
  date: string;
  base64: string;
  full_base64?: string;
  prompt: string;
};

interface TimelineEntryData {
  picture?: TimelinePicture;
  comments: Commentor[];
}

interface CollectionsViewProps {
  isVisible: boolean;
  voiceConfigs: Record<string, any>;
  friendToSelect?: number | null;
  onFriendSelectionHandled?: () => void;
}

export default function CollectionsView({ isVisible, voiceConfigs, friendToSelect, onFriendSelectionHandled }: CollectionsViewProps) {
  const { i18n } = useTranslation();
  const dateLocale = getDateLocale(i18n.language);
  return (
    <div style={{
      width: '100%',
      height: '100%',
      display: 'flex',
      fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
      background: '#f8f0e6',
      overflow: 'hidden'
    }}>
      <TimelinePage
        isVisible={isVisible}
        voiceConfigs={voiceConfigs}
        dateLocale={dateLocale}
        friendToSelect={friendToSelect}
        onFriendSelectionHandled={onFriendSelectionHandled}
      />
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

function formatDate(date: Date | string, locale: string): string {
  return new Date(date).toLocaleDateString(locale, {
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
function getPlaceholderText(t: (key: string, options?: any) => string, daysOffset: number): string {
  if (daysOffset === 0) return t('timelinePlaceholders.today');

  const key = `timelinePlaceholders.${daysOffset}`;
  const translation = t(key, { defaultValue: '' });
  if (translation && translation !== key) {
    return translation;
  }

  return daysOffset < 0 ? t('timelinePlaceholders.default') : t('timelinePlaceholders.default');
}

// @@@ Extract and truncate beginning of text for timeline preview
function getTextPreview(text: string, maxLength: number = 60): string {
  if (!text || text.trim().length === 0) return '';

  // Remove extra whitespace
  const cleaned = text.trim().replace(/\s+/g, ' ');

  // Find first sentence ending
  const sentenceEndings = /[.!?。！？]/;
  const match = cleaned.match(sentenceEndings);

  let preview = '';
  if (match && match.index !== undefined && match.index < maxLength * 1.5) {
    // Use first sentence if it's not too long
    preview = cleaned.substring(0, match.index + 1);
  } else {
    // Otherwise use first N characters
    preview = cleaned.substring(0, maxLength);
  }

  // Truncate if still too long
  if (preview.length > maxLength) {
    preview = preview.substring(0, maxLength).trim() + '...';
  }

  return preview;
}

interface TimelineCardProps {
  day: TimelineDay;
  dayData?: TimelineEntryData;
  hasData: boolean;
  isGenerating: boolean;
  placeholder: string;
  textByDate: Map<string, string>;
  dateLocale: string;
  t: (key: string, options?: any) => string;
  onImageClick: (picture: TimelinePicture) => void;
  onGenerate?: (date: string) => void;
  readOnly?: boolean;
  customDescription?: string;
}

function renderTimelineCard({
  day,
  dayData,
  hasData,
  isGenerating,
  placeholder,
  textByDate,
  dateLocale,
  t,
  onImageClick,
  onGenerate,
  readOnly,
  customDescription
}: TimelineCardProps) {
  const cardCursor = dayData?.picture && !isGenerating ? 'pointer' : 'default';
  const textContent = dayData && textByDate.get(day.date);
  const commentCount = dayData?.comments?.length || 0;

  let description = placeholder;
  if (customDescription) {
    description = customDescription;
  } else if (isGenerating) {
    description = t('timeline.generating');
  } else if (day.isToday && !dayData?.picture) {
    description = placeholder;
  } else if (textContent) {
    description = getTextPreview(textContent);
  } else if (commentCount > 0) {
    description = t('timeline.entryCount', { count: commentCount });
  }

  return (
    <div
      onClick={() => {
        if (dayData?.picture) {
          onImageClick(dayData.picture);
        }
      }}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '1rem',
        padding: '0.5rem 0',
        cursor: cardCursor,
        transition: 'transform 0.2s',
        opacity: day.isPast && !hasData ? 0.4 : 1
      }}
      onMouseEnter={e => {
        if (dayData?.picture && !isGenerating) {
          e.currentTarget.style.transform = 'translateX(8px)';
        }
      }}
      onMouseLeave={e => {
        e.currentTarget.style.transform = 'translateX(0)';
      }}
    >
      <div style={{ flexShrink: 0 }}>
        {dayData?.picture ? (
          <div style={{ position: 'relative' }}>
            <img
              src={`data:image/${dayData.picture.base64?.startsWith('iVBOR') ? 'png' : 'jpeg'};base64,${dayData.picture.base64}`}
              alt={dayData.picture.prompt}
              style={{
                width: '80px',
                height: '80px',
                objectFit: 'cover',
                borderRadius: '6px'
              }}
            />
            {!readOnly && onGenerate && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  if (!isGenerating) onGenerate(day.date);
                }}
                disabled={isGenerating}
                style={{
                  position: 'absolute',
                  top: '4px',
                  right: '4px',
                  width: '24px',
                  height: '24px',
                  borderRadius: '50%',
                  background: 'rgba(255, 255, 255, 0.95)',
                  border: 'none',
                  cursor: isGenerating ? 'wait' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  opacity: 0.9,
                  transition: 'opacity 0.2s'
                }}
                onMouseEnter={e => {
                  if (!isGenerating) e.currentTarget.style.opacity = '1';
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.opacity = '0.9';
                }}
                title="Redraw image"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/>
                </svg>
              </button>
            )}
          </div>
        ) : (
          <div style={{
            width: '80px',
            height: '80px',
            background: day.isFuture ? 'linear-gradient(135deg, #f8f0e6 0%, #ede3d5 100%)' : 'linear-gradient(135deg, #f0e8de 0%, #e5dbc9 100%)',
            border: day.isFuture ? '2px dashed #d0c4b0' : '2px dashed #b8a896',
            borderRadius: '6px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '11px',
            color: '#999',
            fontStyle: 'italic',
            textAlign: 'center',
            padding: '0.5rem'
          }}>
            {isGenerating ? '...' : '?'}
          </div>
        )}
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: '14px',
          fontWeight: 600,
          color: day.isToday ? '#2c2c2c' : '#666',
          marginBottom: '0.25rem'
        }}>
          {day.isToday ? t('timeline.today') : formatDate(day.date, dateLocale)}
        </div>
        <div style={{
          fontSize: '13px',
          color: '#888',
          fontStyle: (!textContent && (day.isToday || !dayData?.comments?.length)) ? 'italic' : 'normal'
        }}>
          {description}
        </div>
      </div>
    </div>
  );
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
const MAX_RECENT_FRIENDS = 6;

const getInitialLetter = (name?: string, fallback: string = '?') => {
  if (!name) return fallback;
  const first = name.trim().charAt(0).toUpperCase();
  return first || fallback;
};

interface TimelinePageProps {
  isVisible: boolean;
  voiceConfigs: Record<string, any>;
  dateLocale: string;
  friendToSelect?: number | null;
  onFriendSelectionHandled?: () => void;
}

function TimelinePage({ isVisible, voiceConfigs, dateLocale, friendToSelect, onFriendSelectionHandled }: TimelinePageProps) {
  const { t } = useTranslation();
  const { isAuthenticated } = useAuth();
  const [starredComments, setStarredComments] = useState<Commentor[]>([]);
  const [allCommentsByDate, setAllCommentsByDate] = useState<Map<string, Commentor[]>>(new Map());
  const [textByDate, setTextByDate] = useState<Map<string, string>>(new Map());
  const [pictures, setPictures] = useState<TimelinePicture[]>([]);
  const [generatingForDate, setGeneratingForDate] = useState<string | null>(null);
  const [viewingImage, setViewingImage] = useState<{ base64: string; full_base64?: string; prompt: string; date: string; origin?: 'self' | 'friend'; friendId?: number } | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);
  const [loadingCommentsForDate, setLoadingCommentsForDate] = useState<string | null>(null);
  const [friends, setFriends] = useState<Friend[]>([]);
  const [selectedFriendId, setSelectedFriendId] = useState<number | null>(() => {
    if (typeof window === 'undefined') return null;
    const stored = localStorage.getItem(STORAGE_KEYS.SELECTED_FRIEND);
    if (!stored) return null;
    const parsed = Number(stored);
    return Number.isFinite(parsed) ? parsed : null;
  });
  const [recentFriendIds, setRecentFriendIds] = useState<number[]>(() => {
    if (typeof window === 'undefined') return [];
    try {
      const stored = localStorage.getItem(STORAGE_KEYS.RECENT_FRIENDS);
      if (!stored) return [];
      const parsed = JSON.parse(stored);
      if (Array.isArray(parsed)) {
        return parsed.filter(id => typeof id === 'number');
      }
      return [];
    } catch {
      return [];
    }
  });
  const [isFriendPickerOpen, setIsFriendPickerOpen] = useState(false);
  const [friendSearchTerm, setFriendSearchTerm] = useState('');
  const [friendPictures, setFriendPictures] = useState<TimelinePicture[]>([]);
  const [, setLoadingFriends] = useState(false);
  const [friendLoadError, setFriendLoadError] = useState<string | null>(null);
  const [, setFriendTimelineError] = useState<string | null>(null);
  const [, setLoadingFriendTimeline] = useState(false);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const emptyTextMap = useMemo(() => new Map<string, string>(), []);
  const allTimelineDays = useMemo(() => generateTimelineDays(), []);
  const filteredFriends = useMemo(() => {
    const term = friendSearchTerm.trim().toLowerCase();
    if (!term) return friends;
    return friends.filter(friend =>
      friend.friend_name?.toLowerCase().includes(term) ||
      friend.friend_email?.toLowerCase().includes(term)
    );
  }, [friends, friendSearchTerm]);
  useEffect(() => {
    setRecentFriendIds(prev =>
      prev.filter(id => friends.some(friend => friend.friend_id === id))
    );
  }, [friends]);

  // @@@ Reset friend selection when auth state changes (guests can't view friends)
  useEffect(() => {
    if (!isAuthenticated) {
      setSelectedFriendId(null);
      localStorage.removeItem(STORAGE_KEYS.SELECTED_FRIEND);
    }
  }, [isAuthenticated]);
  useEffect(() => {
    if (typeof window === 'undefined') return;
    localStorage.setItem(STORAGE_KEYS.RECENT_FRIENDS, JSON.stringify(recentFriendIds));
  }, [recentFriendIds]);
  const friendMap = useMemo(() => {
    const map = new Map<number, Friend>();
    friends.forEach(friend => map.set(friend.friend_id, friend));
    return map;
  }, [friends]);
  const orderedFriendIds = useMemo(() => {
    const recentValid = recentFriendIds.filter(id => friendMap.has(id));
    const prioritized = selectedFriendId && friendMap.has(selectedFriendId)
      ? [selectedFriendId, ...recentValid.filter(id => id !== selectedFriendId)]
      : [...recentValid];

    if (prioritized.length < MAX_RECENT_FRIENDS) {
      for (const friend of friends) {
        if (!friendMap.has(friend.friend_id)) continue;
        if (!prioritized.includes(friend.friend_id)) {
          prioritized.push(friend.friend_id);
        }
        if (prioritized.length >= MAX_RECENT_FRIENDS) {
          break;
        }
      }
    }

    return prioritized.slice(0, MAX_RECENT_FRIENDS);
  }, [recentFriendIds, selectedFriendId, friendMap, friends]);
  const selectedFriend = selectedFriendId ? friendMap.get(selectedFriendId) : null;
  const orderedRecentFriends = orderedFriendIds
    .map(id => friendMap.get(id))
    .filter((friend): friend is Friend => Boolean(friend));

  useEffect(() => {
    const loadTimelineData = async () => {
      // @@@ Load all comments grouped by date from database if authenticated, localStorage if guest
      if (isAuthenticated) {
        try {
          const { listSessions, getSession } = await import('../api/voiceApi');
          const sessions = await listSessions();
          const allStarred: Commentor[] = [];
          const commentsByDate = new Map<string, Commentor[]>();
          const textByDateMap = new Map<string, string>();

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

              // @@@ Extract text from session and group by creation date
              if (fullSession.editor_state?.createdAt && fullSession.editor_state?.cells) {
                const sessionDate = fullSession.editor_state.createdAt; // Already in YYYY-MM-DD format
                const text = fullSession.editor_state.cells
                  .filter((c: any) => c.type === 'text')
                  .map((c: any) => c.content)
                  .join(' ')
                  .trim();

                if (text) {
                  // Append text for this date (sessions can have multiple entries per day)
                  const existingText = textByDateMap.get(sessionDate) || '';
                  textByDateMap.set(sessionDate, existingText ? `${existingText} ${text}` : text);
                }
              }
            } catch (err) {
              console.error(`Failed to load session ${session.id}:`, err);
            }
          }

          setStarredComments(allStarred);
          setAllCommentsByDate(commentsByDate);
          setTextByDate(textByDateMap);
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
            const today = formatDate(new Date(), dateLocale);
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

    const loadFriendsList = async () => {
      if (!isAuthenticated) {
        setFriends([]);
        setFriendLoadError(null);
        setFriendPictures([]);
        setSelectedFriendId(null);
        setFriendTimelineError(null);
        setLoadingFriendTimeline(false);
        setIsFriendPickerOpen(false);
        setFriendSearchTerm('');
        if (typeof window !== 'undefined') {
          localStorage.removeItem(STORAGE_KEYS.SELECTED_FRIEND);
        }
        return;
      }

      setLoadingFriends(true);
      setFriendLoadError(null);
      try {
        const { getFriends } = await import('../api/voiceApi');
        const friendList = await getFriends();
        setFriends(friendList);
        setSelectedFriendId(prev => {
          if (!prev) return prev;
          const exists = friendList.some(friend => friend.friend_id === prev);
          if (!exists) {
            if (typeof window !== 'undefined') {
              localStorage.removeItem(STORAGE_KEYS.SELECTED_FRIEND);
            }
            return null;
          }
          return prev;
        });
      } catch (err) {
        console.error('Failed to load friends:', err);
        setFriendLoadError(err instanceof Error ? err.message : String(err));
      } finally {
        setLoadingFriends(false);
      }
    };

    loadTimelineData();
    loadFriendsList();
  }, [isAuthenticated]);

  // @@@ Group items by date (using YYYY-MM-DD format to match timeline days)
  const timelineByDate = new Map<string, TimelineEntryData>();

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

  const friendTimelineByDate = new Map<string, TimelineEntryData>();
  friendPictures.forEach(pic => {
    friendTimelineByDate.set(pic.date, { picture: pic, comments: [] });
  });

  useEffect(() => {
    if (!isAuthenticated || !selectedFriendId) {
      setFriendPictures([]);
      setFriendTimelineError(null);
      setLoadingFriendTimeline(false);
      return;
    }

    let cancelled = false;
    const loadFriendTimeline = async () => {
      setLoadingFriendTimeline(true);
      setFriendTimelineError(null);
      try {
        const { getFriendTimeline } = await import('../api/voiceApi');
        const friendData = await getFriendTimeline(selectedFriendId, 30);
        const normalized: TimelinePicture[] = friendData.map((pic: any) => ({
          date: pic.date,
          base64: pic.base64,
          prompt: pic.prompt || '',
          full_base64: pic.full_base64
        }));
        if (!cancelled) {
          setFriendPictures(normalized);
        }
      } catch (err) {
        if (!cancelled) {
          console.error('Failed to load friend timeline:', err);
          setFriendTimelineError(err instanceof Error ? err.message : String(err));
          setFriendPictures([]);
        }
      } finally {
        if (!cancelled) {
          setLoadingFriendTimeline(false);
        }
      }
    };

    loadFriendTimeline();
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, selectedFriendId]);

  // @@@ Set initial scroll position to show today's row at top
  // Use useLayoutEffect to position BEFORE browser paints (prevents flash)
  useLayoutEffect(() => {
    if (!isVisible || initialLoading || !scrollContainerRef.current) return;

    const container = scrollContainerRef.current;
    const todayIndex = allTimelineDays.findIndex(day => day.isToday);
    if (todayIndex === -1) return;

    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const rows = container.querySelectorAll('[data-timeline-row]');
        const todayRow = rows[todayIndex] as HTMLElement | undefined;
        if (todayRow) {
          const containerRect = container.getBoundingClientRect();
          const todayRect = todayRow.getBoundingClientRect();
          const offset = todayRect.top - containerRect.top;
          const centerAdjustment = (container.clientHeight / 2) - (todayRect.height / 2);
          container.scrollTop += offset - centerAdjustment;
        }
      });
    });
  }, [isVisible, initialLoading, allTimelineDays]);

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

  const handleImageClick = async (picture: TimelinePicture) => {
    setViewingImage({ ...picture, origin: 'self' });

    // Load full image on-demand if not already loaded
    if (!picture.full_base64 && isAuthenticated) {
      try {
        const { getDailyPictureFull } = await import('../api/voiceApi');
        const fullImage = await getDailyPictureFull(picture.date);

        // Update the picture object with full image
        const updatedPicture = { ...picture, full_base64: fullImage, origin: 'self' as const };
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

  const handleFriendImageClick = async (picture: TimelinePicture) => {
    setViewingImage({ ...picture, origin: 'friend' });

    if (!picture.full_base64 && selectedFriendId) {
      try {
        const { getFriendPictureFull } = await import('../api/voiceApi');
        const fullImage = await getFriendPictureFull(selectedFriendId, picture.date);
        const updatedPicture = { ...picture, full_base64: fullImage };
        setViewingImage({ ...updatedPicture, origin: 'friend' });
        setFriendPictures(prev => prev.map(p =>
          p.date === picture.date ? updatedPicture : p
        ));
      } catch (error) {
        console.error('Failed to load friend full image:', error);
      }
    }
  };

  const handleFriendSelection = useCallback((friendId: number | null) => {
    setSelectedFriendId(friendId);
    if (typeof window !== 'undefined') {
      if (friendId) {
        localStorage.setItem(STORAGE_KEYS.SELECTED_FRIEND, String(friendId));
      } else {
        localStorage.removeItem(STORAGE_KEYS.SELECTED_FRIEND);
      }
    }
    if (friendId) {
      setRecentFriendIds(prev => {
        const without = prev.filter(id => id !== friendId);
        return [friendId, ...without].slice(0, MAX_RECENT_FRIENDS);
      });
    }
    setFriendSearchTerm('');
    setIsFriendPickerOpen(false);
  }, []);

  useEffect(() => {
    if (friendToSelect === undefined || friendToSelect === null) {
      return;
    }

    if (friendToSelect === selectedFriendId) {
      onFriendSelectionHandled?.();
      return;
    }

    handleFriendSelection(friendToSelect);
    onFriendSelectionHandled?.();
  }, [friendToSelect, selectedFriendId, handleFriendSelection, onFriendSelectionHandled]);

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

  return (
    <div
      ref={scrollContainerRef}
      style={{
        width: '100%',
        height: '100%',
        background: '#f8f0e6',
        overflowX: 'hidden',
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center'
      }}>
      <div style={{
        position: 'fixed',
        right: '1rem',
        top: '50%',
        transform: 'translateY(-50%)',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.4rem',
        alignItems: 'center',
        zIndex: 4,
        pointerEvents: isFriendPickerOpen ? 'none' : 'auto',
        opacity: isFriendPickerOpen ? 0.4 : 1
      }}>
        <button
          onClick={() => handleFriendSelection(null)}
          style={{
            width: '42px',
            height: '42px',
            borderRadius: '21px',
            border: selectedFriendId === null ? '2px solid #2c2c2c' : '1px solid #d0c4b0',
            background: selectedFriendId === null ? '#2c2c2c' : '#fff',
            color: selectedFriendId === null ? '#fff' : '#4a433a',
            fontSize: '12px',
            fontWeight: 600,
            cursor: 'pointer'
          }}
          title={t('timeline.friendSelector.personal') || 'You'}
        >
          {t('timeline.friendSelector.personal') || 'Me'}
        </button>
        {orderedRecentFriends.map(friend => {
          const isActive = friend.friend_id === selectedFriendId;
          return (
            <button
              key={friend.id}
              onClick={() => handleFriendSelection(friend.friend_id)}
              style={{
                width: '42px',
                height: '42px',
                borderRadius: '21px',
                border: isActive ? '2px solid #2c2c2c' : '1px solid #d0c4b0',
                background: isActive ? '#2c2c2c' : '#fff',
                color: isActive ? '#fff' : '#4a433a',
                fontSize: '13px',
                fontWeight: 600,
                cursor: 'pointer'
              }}
              title={friend.friend_name || friend.friend_email}
            >
              {getInitialLetter(friend.friend_name, getInitialLetter(friend.friend_email))}
            </button>
          );
        })}
        <button
          onClick={() => {
            setFriendSearchTerm('');
            setIsFriendPickerOpen(true);
          }}
          style={{
            width: '42px',
            height: '42px',
            borderRadius: '21px',
            border: '1px solid #d0c4b0',
            background: '#fff',
            color: '#4a433a',
            fontSize: '18px',
            cursor: 'pointer'
          }}
          title={t('timeline.friendSelector.more') || 'More'}
        >
          …
        </button>
      </div>

      {!selectedFriendId && !isFriendPickerOpen && (
        <div style={{
          position: 'fixed',
          right: '6.5rem',
          top: '50%',
          transform: 'translateY(-50%)',
          width: '260px',
          borderRadius: '16px',
          border: '1px solid #d0c4b0',
          background: '#fffefb',
          padding: '1.5rem',
          boxShadow: '0 20px 60px rgba(0,0,0,0.18)',
          zIndex: 3
        }}>
          <div style={{
            fontSize: '15px',
            fontWeight: 600,
            color: '#3d342a',
            marginBottom: '0.75rem'
          }}>
            {t('timeline.friendSelector.selfOnlyTitle') || 'Your private timeline'}
          </div>
          <div style={{
            fontSize: '13px',
            color: '#5c5145',
            lineHeight: 1.5
          }}>
            {t('timeline.friendSelector.selfOnlyHint') || 'Pick a friend from the badges on the right to compare timelines side by side.'}
          </div>
        </div>
      )}

      {selectedFriendId && !isFriendPickerOpen && friendPictures.length === 0 && (
        <div style={{
          position: 'fixed',
          right: '6.5rem',
          top: '50%',
          transform: 'translateY(-50%)',
          width: '260px',
          borderRadius: '16px',
          border: '1px solid #d0c4b0',
          background: '#fffefb',
          padding: '1.5rem',
          boxShadow: '0 20px 60px rgba(0,0,0,0.18)',
          zIndex: 3
        }}>
          <div style={{
            fontSize: '15px',
            fontWeight: 600,
            color: '#3d342a',
            marginBottom: '0.75rem'
          }}>
            {t('timeline.friendSelector.friendEmptyTitle') || 'No friend timeline yet'}
          </div>
          <div style={{
            fontSize: '13px',
            color: '#5c5145',
            lineHeight: 1.5
          }}>
            {t('timeline.friendSelector.friendEmptyHint', { name: selectedFriend?.friend_name || '' }) || 'They have not shared anything for these days yet.'}
          </div>
        </div>
      )}

      {isFriendPickerOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.45)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 20,
            padding: '2rem'
          }}
          onClick={() => setIsFriendPickerOpen(false)}
        >
          <div
            style={{
              width: '100%',
              maxWidth: '420px',
              background: '#fff',
              borderRadius: '12px',
              border: '1px solid #d0c4b0',
              boxShadow: '0 12px 40px rgba(0,0,0,0.25)',
              padding: '1.5rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '1rem'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ fontSize: '15px', fontWeight: 600, color: '#2c2c2c' }}>
                {t('timeline.friendSelector.label')}
              </div>
              <button
                onClick={() => setIsFriendPickerOpen(false)}
                style={{
                  border: 'none',
                  background: 'transparent',
                  fontSize: '14px',
                  color: '#7a7060',
                  cursor: 'pointer'
                }}
              >
                {t('timeline.friendSelector.close')}
              </button>
            </div>
            {friendLoadError && (
              <div style={{ fontSize: '12px', color: '#b8562e' }}>
                {t('timeline.friendSelector.error')}
              </div>
            )}
            <input
              type="text"
              value={friendSearchTerm}
              onChange={(e) => setFriendSearchTerm(e.target.value)}
              placeholder={t('timeline.friendSelector.searchPlaceholder') || 'Search'}
              style={{
                width: '100%',
                padding: '0.65rem 0.85rem',
                borderRadius: '8px',
                border: '1px solid #c7b9a4',
                background: '#fff',
                fontSize: '14px',
                boxSizing: 'border-box'
              }}
            />
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                onClick={() => handleFriendSelection(null)}
                style={{
                  flex: 1,
                  border: selectedFriendId === null ? '1px solid #2c2c2c' : '1px solid #c7b9a4',
                  background: selectedFriendId === null ? '#f0e8de' : '#fff',
                  borderRadius: '8px',
                  padding: '0.6rem 0.75rem',
                  fontSize: '13px',
                  cursor: 'pointer',
                  color: '#2c2c2c',
                  fontWeight: 600
                }}
              >
                {t('timeline.friendSelector.none')}
              </button>
            </div>
            <div style={{ maxHeight: '260px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {friends.length === 0 && (
                <div style={{ fontSize: '13px', color: '#7a7060' }}>
                  {t('timeline.friendSelector.noFriends')}
                </div>
              )}
              {friends.length > 0 && filteredFriends.length === 0 && (
                <div style={{ fontSize: '13px', color: '#7a7060' }}>
                  {t('timeline.friendSelector.noMatches')}
                </div>
              )}
              {filteredFriends.map((friend) => {
                const isSelected = friend.friend_id === selectedFriendId;
                return (
                  <button
                    key={friend.id}
                    onClick={() => handleFriendSelection(friend.friend_id)}
                    style={{
                      border: isSelected ? '1px solid #2c2c2c' : '1px solid #d0c4b0',
                      borderRadius: '8px',
                      padding: '0.65rem 0.9rem',
                      textAlign: 'left',
                      cursor: 'pointer',
                      background: isSelected ? '#f0e8de' : '#fff'
                    }}
                  >
                    <div style={{ fontWeight: 600, fontSize: '14px', color: '#2c2c2c' }}>
                      {friend.friend_name}
                    </div>
                    <div style={{ fontSize: '12px', color: '#7a7060' }}>
                      {friend.friend_email}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* @@@ Vertical scrolling timeline - rows stacked */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '1.5rem',
        maxWidth: '1200px',
        width: '100%',
        padding: '0 2rem',
        paddingBottom: '5rem'  // @@@ Prevent bottom card cutoff
      }}>
        {allTimelineDays.map((day, index) => {
          const dayData = timelineByDate.get(day.date);
          const friendDayData = friendTimelineByDate.get(day.date);
          const hasData = !!dayData;
          const hasFriendData = !!friendDayData;
          const isGenerating = generatingForDate === day.date;
          const placeholder = getPlaceholderText(t, day.daysOffset);
          const showFriendSide = Boolean(selectedFriendId);

          return (
            <div
              data-timeline-row
              key={day.date}
              style={{
                position: 'relative',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '1.5rem',
                padding: '0 2rem'
              }}>
              <div style={{
                flex: '1',
                display: 'flex',
                justifyContent: 'flex-end',
                paddingRight: '2rem'
              }}>
                {renderTimelineCard({
                  day,
                  dayData,
                  hasData,
                  isGenerating,
                  onImageClick: handleImageClick,
                  onGenerate: handleGenerateForDate,
                  textByDate,
                  t,
                  dateLocale,
                  placeholder
                })}
              </div>

              {/* Center node */}
              <div style={{
                position: 'absolute',
                left: '50%',
                top: '50%',
                transform: 'translate(-50%, -50%)',
                width: '20px',
                height: '20px',
                borderRadius: '50%',
                background: (hasData || hasFriendData) ? '#4CAF50' : (day.isToday ? '#888' : '#ddd'),
                border: '3px solid #f8f0e6',
                boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
                zIndex: 2,
                pointerEvents: 'none'
              }} />

              {index < allTimelineDays.length - 1 && (
                <div style={{
                  position: 'absolute',
                  left: 'calc(50% - 1.5px)',
                  top: '50%',
                  height: 'calc(100% + 1.5rem)',
                  width: '3px',
                  background: '#d0c4b0',
                  zIndex: 1
                }} />
              )}

              <div style={{
                flex: '1',
                display: 'flex',
                justifyContent: 'flex-start',
                paddingLeft: '2rem'
              }}>
                {showFriendSide && friendDayData?.picture ? (
                  renderTimelineCard({
                    day,
                    dayData: friendDayData,
                    hasData: true,
                    isGenerating: false,
                    onImageClick: handleFriendImageClick,
                    textByDate: emptyTextMap,
                    t,
                    dateLocale,
                    placeholder,
                    readOnly: true,
                    customDescription: friendDayData.picture.prompt
                      ? getTextPreview(friendDayData.picture.prompt, 80)
                      : placeholder
                  })
                ) : (
                  <div style={{ width: '80px', height: '80px' }} />
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
                      if (viewingImage.origin === 'friend' && viewingImage.prompt) {
                        return (
                          <div style={{
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '1rem'
                          }}>
                            <div
                              style={{
                                background: '#fff',
                                border: '1px solid #e0d8cc',
                                borderRadius: '8px',
                                padding: '1rem'
                              }}
                            >
                              <div style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '0.5rem',
                                marginBottom: '0.75rem'
                              }}>
                                <span style={{ fontSize: '18px' }}>👥</span>
                                <span style={{ fontWeight: 600, fontSize: '14px', color: '#333' }}>
                                  {t('timeline.friendTimeline.readOnlyShort')}
                                </span>
                              </div>
                              <div style={{
                                fontSize: '13px',
                                color: '#555',
                                lineHeight: '1.7',
                                paddingLeft: '0.5rem',
                                wordBreak: 'break-word',
                                whiteSpace: 'pre-wrap'
                              }}>
                                {viewingImage.prompt}
                              </div>
                            </div>
                          </div>
                        );
                      }

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
                {new Date(viewingImage.date).toLocaleDateString(dateLocale, {
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
                  const commentCount = viewingImage.origin === 'friend'
                    ? (viewingImage.prompt ? 1 : 0)
                    : (timelineByDate.get(viewingImage.date)?.comments?.length || 0);
                  return t('timeline.entryCount', { count: commentCount });
                })()}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
