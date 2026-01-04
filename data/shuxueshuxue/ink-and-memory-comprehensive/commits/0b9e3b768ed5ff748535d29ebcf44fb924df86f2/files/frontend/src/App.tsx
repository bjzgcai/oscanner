import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { EditorEngine } from './engine/EditorEngine';
import type { EditorState, Commentor, TextCell } from './engine/EditorEngine';
import { ChatWidget } from './engine/ChatWidget';
import type { ChatWidgetData } from './engine/ChatWidget';
import './App.css';
import {
  FaSync,
  FaBrain, FaHeart, FaQuestion, FaCloud, FaTheaterMasks, FaEye,
  FaFistRaised, FaLightbulb, FaShieldAlt, FaWind, FaFire, FaCompass,
  FaAlignRight
} from 'react-icons/fa';
import LeftSidebar from './components/LeftSidebar';
import VoiceSettings from './components/VoiceSettings';
import CalendarPopup from './components/CalendarPopup';
import { saveEntryToToday, type CalendarEntry } from './utils/calendarStorage';
import CollectionsView from './components/CollectionsView';
import AnalysisView from './components/AnalysisView';
import AboutView from './components/AboutView';
import AgentDropdown from './components/AgentDropdown';
import ChatWidgetUI from './components/ChatWidgetUI';
import StateChooser from './components/StateChooser';
import type { VoiceConfig } from './types/voice';
import { getVoices, getMetaPrompt, getStateConfig } from './utils/voiceStorage';
import { getDefaultVoices, chatWithVoice } from './api/voiceApi';
import { useMobile } from './utils/mobileDetect';
import { CommentGroupCard } from './components/CommentCard';

// @@@ Left Toolbar Component - floating toolbelt within left margin
function LeftToolbar({
  onStartFresh,
  onInsertAgent,
  onToggleAlign,
  onShowCalendar,
  onSaveToday,
  isAligned
}: {
  onStartFresh: () => void;
  onInsertAgent: () => void;
  onToggleAlign: () => void;
  onShowCalendar: () => void;
  onSaveToday: () => void;
  isAligned: boolean;
}) {
  return (
    <div style={{
      position: 'sticky',
      top: '80px',
      width: '40px',
      margin: '30px auto 0',
      backgroundColor: '#fff',
      border: '1px solid #e0e0e0',
      borderRadius: '8px',
      boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      padding: '10px 0',
      gap: '4px'
    }}>
      {/* Calendar button - first */}
      <button
        onClick={onShowCalendar}
        title="Calendar"
        style={{
          width: '36px',
          height: '36px',
          border: 'none',
          borderRadius: '4px',
          backgroundColor: '#fff',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'all 0.2s ease'
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = '#f0f0f0';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = '#fff';
        }}
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
          <line x1="16" y1="2" x2="16" y2="6"></line>
          <line x1="8" y1="2" x2="8" y2="6"></line>
          <line x1="3" y1="10" x2="21" y2="10"></line>
        </svg>
      </button>

      {/* Save button - second */}
      <button
        onClick={onSaveToday}
        title="Save"
        style={{
          width: '36px',
          height: '36px',
          border: 'none',
          borderRadius: '4px',
          backgroundColor: '#fff',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'all 0.2s ease'
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = '#f0f0f0';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = '#fff';
        }}
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
          <polyline points="17 21 17 13 7 13 7 21"></polyline>
          <polyline points="7 3 7 8 15 8"></polyline>
        </svg>
      </button>

      {/* Start Fresh button - third */}
      <button
        onClick={onStartFresh}
        title="Start Fresh"
        style={{
          width: '36px',
          height: '36px',
          border: 'none',
          borderRadius: '4px',
          backgroundColor: '#fff',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'all 0.2s ease'
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = '#f0f0f0';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = '#fff';
        }}
      >
        <FaSync size={18} color="#333" />
      </button>

      {/* Insert Agent button - fourth */}
      <button
        onClick={onInsertAgent}
        title="Insert Agent Chat"
        style={{
          width: '36px',
          height: '36px',
          border: 'none',
          borderRadius: '4px',
          backgroundColor: '#fff',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'all 0.2s ease',
          fontSize: '20px',
          fontWeight: 600,
          color: '#333',
          fontFamily: 'monospace'
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = '#f0f0f0';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = '#fff';
        }}
      >
        @
      </button>

      {/* Align button - last */}
      <button
        onClick={onToggleAlign}
        title={isAligned ? "Unalign Comments" : "Align Comments Right"}
        style={{
          width: '36px',
          height: '36px',
          border: 'none',
          borderRadius: '4px',
          backgroundColor: isAligned ? '#e3f2fd' : '#fff',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'all 0.2s ease'
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = isAligned ? '#bbdefb' : '#f0f0f0';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = isAligned ? '#e3f2fd' : '#fff';
        }}
      >
        <FaAlignRight size={18} color={isAligned ? '#1976d2' : '#333'} />
      </button>
    </div>
  );
}

// @@@ Icon map with React Icons
const iconMap = {
  brain: FaBrain,
  heart: FaHeart,
  question: FaQuestion,
  cloud: FaCloud,
  masks: FaTheaterMasks,
  eye: FaEye,
  fist: FaFistRaised,
  lightbulb: FaLightbulb,
  shield: FaShieldAlt,
  wind: FaWind,
  fire: FaFire,
  compass: FaCompass,
};

// @@@ Color map with gradient colors for watercolor effect
const colorMap: Record<string, { gradient: string; text: string; glow: string }> = {
  blue: {
    gradient: 'linear-gradient(90deg, rgba(77,159,255,0) 0%, rgba(77,159,255,0.05) 30%, rgba(77,159,255,0.12) 60%, rgba(77,159,255,0.25) 100%)',
    text: '#0066cc',
    glow: 'rgba(77,159,255,0.15)'
  },
  pink: {
    gradient: 'linear-gradient(90deg, rgba(255,102,179,0) 0%, rgba(255,102,179,0.05) 30%, rgba(255,102,179,0.12) 60%, rgba(255,102,179,0.25) 100%)',
    text: '#cc0066',
    glow: 'rgba(255,102,179,0.15)'
  },
  yellow: {
    gradient: 'linear-gradient(90deg, rgba(255,221,51,0) 0%, rgba(255,221,51,0.05) 30%, rgba(255,221,51,0.12) 60%, rgba(255,221,51,0.25) 100%)',
    text: '#996600',
    glow: 'rgba(255,221,51,0.15)'
  },
  green: {
    gradient: 'linear-gradient(90deg, rgba(102,255,102,0) 0%, rgba(102,255,102,0.05) 30%, rgba(102,255,102,0.12) 60%, rgba(102,255,102,0.25) 100%)',
    text: '#006600',
    glow: 'rgba(102,255,102,0.15)'
  },
  purple: {
    gradient: 'linear-gradient(90deg, rgba(179,102,255,0) 0%, rgba(179,102,255,0.05) 30%, rgba(179,102,255,0.12) 60%, rgba(179,102,255,0.25) 100%)',
    text: '#6600cc',
    glow: 'rgba(179,102,255,0.15)'
  },
};

// @@@ Main App Component
export default function App() {
  const isMobile = useMobile();
  const [currentView, setCurrentView] = useState<'writing' | 'settings' | 'timeline' | 'analysis' | 'about'>('writing');
  const [showCalendarPopup, setShowCalendarPopup] = useState(false);
  const [voiceConfigs, setVoiceConfigs] = useState<Record<string, VoiceConfig>>({});
  const [defaultVoiceConfigs, setDefaultVoiceConfigs] = useState<Record<string, VoiceConfig>>({});

  const engineRef = useRef<EditorEngine | null>(null);
  const [state, setState] = useState<EditorState | null>(null);
  // @@@ Track local text per cell ID for IME composition
  const [localTexts, setLocalTexts] = useState<Map<string, string>>(new Map());
  const [composingCells, setComposingCells] = useState<Set<string>>(new Set());
  const [groupPages, setGroupPages] = useState<Map<string, number>>(new Map());
  const [cursorPosition, setCursorPosition] = useState<number>(0);
  const [cursorCellId, setCursorCellId] = useState<string | null>(null);

  // @@@ Mobile-specific: Track which comment is at cursor for popup display
  const [mobileActiveComment, setMobileActiveComment] = useState<Commentor | null>(null);

  // @@@ Chat widget state
  const [dropdownVisible, setDropdownVisible] = useState(false);
  const [dropdownPosition, setDropdownPosition] = useState({ x: 0, y: 0 });
  const [dropdownTriggerCellId, setDropdownTriggerCellId] = useState<string | null>(null);
  const [chatProcessing, setChatProcessing] = useState<Set<string>>(new Set());

  // @@@ Warning dialog state
  const [showWarning, setShowWarning] = useState(false);

  // @@@ State chooser
  const [selectedState, setSelectedState] = useState<string | null>(
    () => localStorage.getItem('selected-state')
  );
  const [stateConfig, setStateConfig] = useState(() => getStateConfig());

  // @@@ Per-cell textarea refs for positioning and style calculations
  const textareaRefs = useRef<Map<string, HTMLTextAreaElement>>(new Map());
  const containerRef = useRef<HTMLDivElement>(null);
  // @@@ Force re-render when refs are ready
  const [refsReady, setRefsReady] = useState(0);
  const refsReadyTriggered = useRef(false);

  // @@@ Comment alignment state
  const [commentsAligned, setCommentsAligned] = useState(false);

  // @@@ Comment expansion state (for action toolbar + chat dropdown)
  const [expandedCommentId, setExpandedCommentId] = useState<string | null>(null);
  const [commentChatProcessing, setCommentChatProcessing] = useState<Set<string>>(new Set());

  // @@@ Trigger re-render when returning to writing view to recalculate comment positions
  useEffect(() => {
    if (currentView === 'writing') {
      // Force re-render to recalculate comment positions
      // Don't reset refsReadyTriggered - it should remain true after initial mount
      setRefsReady(prev => prev + 1);
    }
  }, [currentView]);

  // @@@ Fetch default voices from backend
  useEffect(() => {
    getDefaultVoices().then(backendVoices => {
      const converted: Record<string, VoiceConfig> = {};
      for (const [name, data] of Object.entries(backendVoices)) {
        const v = data as any;
        converted[name] = {
          name,
          systemPrompt: v.tagline,
          enabled: true,
          icon: v.icon,
          color: v.color
        };
      }
      setDefaultVoiceConfigs(converted);
      const configs = getVoices() || converted;
      setVoiceConfigs(configs);

      // Update engine with voice configs
      if (engineRef.current) {
        engineRef.current.setVoiceConfigs(configs);
      }
    });
  }, []);

  // @@@ Update engine when voice configs change
  useEffect(() => {
    if (engineRef.current && Object.keys(voiceConfigs).length > 0) {
      engineRef.current.setVoiceConfigs(voiceConfigs);
    }
  }, [voiceConfigs]);

  // @@@ Reload state config when returning to writing view
  useEffect(() => {
    if (currentView === 'writing') {
      setStateConfig(getStateConfig());
    }
  }, [currentView]);

  // Initialize engine
  useEffect(() => {
    const sessionId = crypto.randomUUID ? crypto.randomUUID() : Date.now().toString();
    const engine = new EditorEngine(sessionId);
    engineRef.current = engine;

    engine.subscribe((newState) => {
      setState({ ...newState });
      localStorage.setItem('ink_memory_state', JSON.stringify(newState));
    });

    const saved = localStorage.getItem('ink_memory_state');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        engine.loadState(parsed);
        setState(engine.getState());

        // Initialize localTexts from loaded state
        const texts = new Map<string, string>();
        parsed.cells?.filter((c: any) => c.type === 'text').forEach((c: any) => {
          texts.set(c.id, c.content || '');
        });
        setLocalTexts(texts);
      } catch (e) {
        console.error('Failed to load saved state:', e);
      }
    } else {
      setState(engine.getState());
    }
  }, []);

  // @@@ Sync localTexts from state when not composing
  useEffect(() => {
    if (state) {
      setLocalTexts(prev => {
        const next = new Map(prev);
        state.cells.filter(c => c.type === 'text').forEach(cell => {
          const textCell = cell as TextCell;
          // Only update if not composing in this cell
          if (!composingCells.has(cell.id)) {
            next.set(cell.id, textCell.content || '');
          }
        });
        return next;
      });
    }
  }, [state, composingCells]);

  // @@@ Group comments by 2-row blocks, accounting for widgets between cells
  const commentGroups = useMemo(() => {
    const groups = new Map<string, {
      comments: Commentor[];
      cellId: string;
      blockIndex: number;
      visualLineStart: number;
      visualLineEnd: number;
      maxLineWidth: number;
      centerY: number;
    }>();

    if (!state) return groups;

    // Get any available textarea ref for style calculations
    const anyTextarea = Array.from(textareaRefs.current.values())[0];
    if (!anyTextarea) return groups;

    const maxTextareaWidth = 600;

    const computedStyle = window.getComputedStyle(anyTextarea);
    const fontSize = parseFloat(computedStyle.fontSize) || 18;
    const lineHeightRatio = parseFloat(computedStyle.lineHeight) / fontSize || 1.8;
    const lineHeight = fontSize * lineHeightRatio;

    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    if (ctx) {
      const fontFamily = computedStyle.fontFamily || 'system-ui, -apple-system, sans-serif';
      ctx.font = `${fontSize}px ${fontFamily}`;
    }

    // @@@ Process each text cell separately
    state.cells.forEach(cell => {
      if (cell.type !== 'text') return;

      const textCell = cell as TextCell;
      const text = textCell.content;

      // Calculate visual lines for this cell
      const charToVisualLine: number[] = new Array(text.length);
      let currentVisualLine = 0;
      let currentLineStartIndex = 0;

      for (let i = 0; i < text.length; i++) {
        charToVisualLine[i] = currentVisualLine;

        if (text[i] === '\n') {
          currentVisualLine++;
          currentLineStartIndex = i + 1;
        } else {
          const currentLineText = text.substring(currentLineStartIndex, i + 1);
          const width = ctx ? ctx.measureText(currentLineText).width : currentLineText.length * (fontSize * 0.6);

          if (width > maxTextareaWidth && i > currentLineStartIndex) {
            currentVisualLine++;
            currentLineStartIndex = i;
            charToVisualLine[i] = currentVisualLine;
          }
        }
      }

      // Find comments in this cell
      state.commentors
        .filter(c => c.appliedAt)
        .forEach(commentor => {
          const index = text.toLowerCase().indexOf(commentor.phrase.toLowerCase());
          if (index === -1) return;

          const visualLineNumber = charToVisualLine[index] || 0;
          const blockIndex = Math.floor(visualLineNumber / 2);
          const visualLineStart = blockIndex * 2;
          const visualLineEnd = visualLineStart + 1;

          // Create unique group key per cell
          const groupKey = `${cell.id}-${blockIndex}`;

          if (!groups.has(groupKey)) {
            let maxWidth = 0;

            for (let i = 0; i < text.length; i++) {
              const vLine = charToVisualLine[i];
              if (vLine === visualLineStart || vLine === visualLineEnd) {
                let lineEnd = i;
                while (lineEnd < text.length && charToVisualLine[lineEnd] === vLine) {
                  lineEnd++;
                }
                const lineText = text.substring(i, lineEnd);
                const width = ctx ? ctx.measureText(lineText).width : lineText.length * (fontSize * 0.6);
                maxWidth = Math.max(maxWidth, Math.min(width, maxTextareaWidth));
                i = lineEnd - 1;
              }
            }

            const centerY = (visualLineStart + 1) * lineHeight;

            groups.set(groupKey, {
              comments: [],
              cellId: cell.id,
              blockIndex,
              visualLineStart,
              visualLineEnd,
              maxLineWidth: maxWidth,
              centerY
            });
          }

          groups.get(groupKey)!.comments.push(commentor);
        });
    });

    return groups;
  }, [state?.commentors, state, refsReady]);

  useEffect(() => {
    if (!commentGroups) return;

    setGroupPages(prev => {
      const next = new Map(prev);

      commentGroups.forEach((group, groupKey) => {
        if (group.comments.length === 0) {
          next.delete(groupKey);
          return;
        }

        const currentPage = prev.get(groupKey) || 0;
        const maxPage = group.comments.length - 1;

        if (group.comments.length > 1 && currentPage < maxPage) {
          next.set(groupKey, maxPage);
        } else if (currentPage > maxPage) {
          next.set(groupKey, maxPage);
        }
      });

      prev.forEach((_, groupKey) => {
        if (!commentGroups.has(groupKey)) {
          next.delete(groupKey);
        }
      });

      return next;
    });
  }, [commentGroups]);

  const handleGroupNavigate = useCallback((groupKey: string, newIndex: number) => {
    const group = commentGroups.get(groupKey);
    if (!group) return;

    setGroupPages(prev => {
      const next = new Map(prev);
      next.set(groupKey, newIndex);
      return next;
    });

    // @@@ Update expanded comment ID ONLY if something in this group is already expanded
    // This keeps the card expanded while switching between comments
    const anyExpanded = group.comments.some(c => c.id === expandedCommentId);
    if (anyExpanded && group.comments[newIndex]) {
      setExpandedCommentId(group.comments[newIndex].id);
    }
  }, [commentGroups, expandedCommentId]);

  // @@@ Cursor-based comment navigation (per-cell)
  useEffect(() => {
    if (!state || !cursorCellId) return;

    // Get text for the cell where cursor is
    const cell = state.cells.find(c => c.id === cursorCellId);
    if (!cell || cell.type !== 'text') return;

    const cellText = (cell as TextCell).content;
    const appliedComments = state.commentors.filter(c => c.appliedAt);
    if (appliedComments.length === 0) {
      // Clear mobile comment if no comments exist
      if (isMobile) setMobileActiveComment(null);
      return;
    }

    // Find comment at cursor position within this cell's text
    let foundComment: Commentor | null = null;
    for (const comment of appliedComments) {
      const index = cellText.toLowerCase().indexOf(comment.phrase.toLowerCase());
      if (index !== -1) {
        const start = index;
        const end = index + comment.phrase.length;

        if (cursorPosition >= start && cursorPosition <= end) {
          foundComment = comment;
          break;
        }
      }
    }

    // @@@ Mobile: Set active comment for popup display
    if (isMobile) {
      setMobileActiveComment(foundComment);
    }

    if (!foundComment) return;

    // @@@ Desktop: Navigate to comment at cursor position
    if (!isMobile) {
      commentGroups.forEach((group, groupKey) => {
        // Only update groups in the current cell
        if (group.cellId !== cursorCellId) return;

        const commentIndex = group.comments.findIndex(c => c.id === foundComment!.id);
        if (commentIndex !== -1) {
          // Don't navigate if a comment in this group is expanded
          const groupHasExpanded = group.comments.some(c => c.id === expandedCommentId);
          if (groupHasExpanded) return;

          setGroupPages(prev => {
            const next = new Map(prev);
            if (next.get(groupKey) !== commentIndex) {
              next.set(groupKey, commentIndex);
            }
            return next;
          });
        }
      });
    }
  }, [cursorPosition, cursorCellId, state, commentGroups, isMobile, expandedCommentId]);

  // @@@ Per-cell text change handler
  const handleTextChange = useCallback((cellId: string, newText: string) => {
    setLocalTexts(prev => {
      const next = new Map(prev);
      next.set(cellId, newText);
      return next;
    });

    // @@@ Auto-resize textarea to prevent internal scrolling
    const textarea = textareaRefs.current.get(cellId);
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = textarea.scrollHeight + 'px';
    }

    // Close dropdown if @ was deleted in the trigger cell
    if (dropdownVisible && dropdownTriggerCellId === cellId) {
      if (!newText.includes('@')) {
        setDropdownVisible(false);
        setDropdownTriggerCellId(null);
      }
    }

    if (!composingCells.has(cellId) && engineRef.current) {
      engineRef.current.updateTextCell(cellId, newText);
    }
  }, [composingCells, dropdownVisible, dropdownTriggerCellId]);

  // @@@ Per-cell composition handlers
  const handleCompositionStart = useCallback((cellId: string) => {
    setComposingCells(prev => new Set(prev).add(cellId));
  }, []);

  const handleCompositionEnd = useCallback((cellId: string, e: React.CompositionEvent<HTMLTextAreaElement>) => {
    setComposingCells(prev => {
      const next = new Set(prev);
      next.delete(cellId);
      return next;
    });

    const newText = e.currentTarget.value;
    setLocalTexts(prev => {
      const next = new Map(prev);
      next.set(cellId, newText);
      return next;
    });

    if (engineRef.current) {
      engineRef.current.updateTextCell(cellId, newText);
    }
  }, []);

  const handlePaste = useCallback((cellId: string, e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    setTimeout(() => {
      const newText = e.currentTarget.value;
      setLocalTexts(prev => {
        const next = new Map(prev);
        next.set(cellId, newText);
        return next;
      });
      if (engineRef.current) {
        engineRef.current.updateTextCell(cellId, newText);
      }
    }, 0);
  }, []);

  const handleCursorChange = useCallback((cellId: string, e: React.SyntheticEvent<HTMLTextAreaElement>) => {
    setCursorPosition(e.currentTarget.selectionStart);
    setCursorCellId(cellId);
  }, []);

  const handleStartFresh = useCallback(() => {
    setShowWarning(true);
  }, []);

  const confirmStartFresh = useCallback(() => {
    localStorage.removeItem('ink_memory_state');
    localStorage.removeItem('selected-state');
    window.location.reload();
  }, []);

  const handleSaveToday = useCallback(() => {
    if (!state || !engineRef.current) return;

    // Save and get the entry ID (either new or overwritten)
    const entryId = saveEntryToToday(state);

    // Update current entry ID in engine state
    engineRef.current.setCurrentEntryId(entryId);

    // Show toast notification
    const toast = document.createElement('div');
    toast.textContent = state.currentEntryId ? 'Saved (updated)' : 'Saved';
    toast.style.cssText = `
      position: fixed;
      top: 70px;
      right: 20px;
      background: #4CAF50;
      color: white;
      padding: 12px 20px;
      borderRadius: 6px;
      fontSize: 14px;
      fontFamily: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto;
      zIndex: 10000;
      boxShadow: 0 4px 12px rgba(0,0,0,0.15);
    `;
    document.body.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 0.3s';
      setTimeout(() => document.body.removeChild(toast), 300);
    }, 2000);
  }, [state]);

  const handleLoadEntry = useCallback((entry: CalendarEntry) => {
    if (engineRef.current) {
      engineRef.current.loadState(entry.state);
      // Set the current entry ID so subsequent saves will overwrite this entry
      engineRef.current.setCurrentEntryId(entry.id);
      setShowCalendarPopup(false);
    }
  }, []);

  const handleStateChoose = useCallback((stateId: string) => {
    setSelectedState(stateId);
    localStorage.setItem('selected-state', stateId);
  }, []);

  // @@@ Insert @ character at the end of last text cell
  const handleInsertAgent = useCallback(() => {
    if (!state || !engineRef.current) return;

    // Find last text cell
    const lastTextCell = [...state.cells].reverse().find(c => c.type === 'text');
    if (!lastTextCell) return;

    const textarea = textareaRefs.current.get(lastTextCell.id);
    if (!textarea) return;

    // Insert @ character at the end
    const currentContent = (lastTextCell as TextCell).content;
    const newContent = currentContent + '@';

    // Update the text
    engineRef.current.updateTextCell(lastTextCell.id, newContent);

    // Focus the textarea and position cursor after @
    setTimeout(() => {
      textarea.focus();
      textarea.selectionStart = newContent.length;
      textarea.selectionEnd = newContent.length;

      // Show dropdown
      const rect = textarea.getBoundingClientRect();
      const computedStyle = window.getComputedStyle(textarea);
      const lineHeight = parseFloat(computedStyle.lineHeight) || 32;
      const linesBefore = newContent.substring(0, newContent.length).split('\n').length - 1;

      setDropdownPosition({
        x: rect.left + 10,
        y: rect.top + (linesBefore * lineHeight) + lineHeight + 5
      });
      setDropdownTriggerCellId(lastTextCell.id);
      setDropdownVisible(true);
    }, 0);
  }, [state]);

  // @@@ Toggle comment alignment
  const handleToggleAlign = useCallback(() => {
    setCommentsAligned(prev => !prev);
  }, []);

  // @@@ Comment interaction handlers
  const handleCommentStar = useCallback((commentId: string) => {
    if (!engineRef.current) return;
    const comment = engineRef.current.getComment(commentId);
    if (!comment) return;

    // Toggle star (if already starred, unstar)
    const newFeedback = comment.feedback === 'star' ? undefined : 'star';
    engineRef.current.setCommentFeedback(commentId, newFeedback as any);
  }, []);

  const handleCommentKill = useCallback((commentId: string) => {
    if (!engineRef.current) return;
    engineRef.current.setCommentFeedback(commentId, 'kill');
    // Close expansion after killing
    setExpandedCommentId(null);
  }, []);

  const handleCommentChatSend = useCallback(async (commentId: string, message: string) => {
    if (!engineRef.current || !state) return;

    const comment = engineRef.current.getComment(commentId);
    if (!comment) return;

    // Add user message immediately
    engineRef.current.addCommentChatMessage(commentId, 'user', message);
    setCommentChatProcessing(prev => new Set(prev).add(commentId));

    try {
      // Get all text from text cells
      const allText = state.cells
        .filter(c => c.type === 'text')
        .map(c => (c as TextCell).content)
        .join('');

      // Get the voice config for this comment
      const voiceConfig = voiceConfigs[comment.voice];
      if (!voiceConfig) {
        throw new Error(`Voice config not found for ${comment.voice}`);
      }

      // Get conversation history (excluding the message we just added)
      const chatHistory = comment.chatHistory?.slice(0, -1) || [];

      const metaPrompt = getMetaPrompt();
      const statePrompt = selectedState && stateConfig.states[selectedState]
        ? stateConfig.states[selectedState].prompt
        : '';

      const response = await chatWithVoice(
        comment.voice,
        voiceConfig,
        chatHistory,
        message,
        allText,
        metaPrompt,
        statePrompt
      );

      // Add assistant response
      engineRef.current.addCommentChatMessage(commentId, 'assistant', response);
    } catch (error) {
      console.error('Comment chat failed:', error);
      engineRef.current.addCommentChatMessage(commentId, 'assistant', 'Sorry, I encountered an error.');
    } finally {
      setCommentChatProcessing(prev => {
        const next = new Set(prev);
        next.delete(commentId);
        return next;
      });
    }
  }, [state, voiceConfigs, selectedState, stateConfig]);

  // @@@ Handle @ key press for agent dropdown
  const handleKeyDown = useCallback((cellId: string, e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === '@' && !composingCells.has(cellId)) {
      // @@@ Capture textarea ref before setTimeout (React synthetic events are nullified)
      const textarea = e.currentTarget;
      setTimeout(() => {
        if (textarea) {
          // Get cursor position in textarea
          const cursorPos = textarea.selectionStart;
          const textBeforeCursor = textarea.value.substring(0, cursorPos);

          // Count lines before cursor
          const linesBefore = textBeforeCursor.split('\n').length - 1;

          // Calculate approximate cursor position
          const computedStyle = window.getComputedStyle(textarea);
          const lineHeight = parseFloat(computedStyle.lineHeight) || 32;
          const rect = textarea.getBoundingClientRect();

          // Position dropdown at cursor (with small offset)
          setDropdownPosition({
            x: rect.left + 10,
            y: rect.top + (linesBefore * lineHeight) + lineHeight + 5
          });
          setDropdownTriggerCellId(cellId);
          setDropdownVisible(true);
        }
      }, 0);
    } else if (e.key === 'Escape' && dropdownVisible) {
      setDropdownVisible(false);
      setDropdownTriggerCellId(null);
    }
  }, [composingCells, dropdownVisible]);

  // @@@ Handle agent selection from dropdown
  const handleAgentSelect = useCallback((voiceName: string, voiceConfig: VoiceConfig) => {
    setDropdownVisible(false);

    if (!engineRef.current || !dropdownTriggerCellId) return;

    const textarea = textareaRefs.current.get(dropdownTriggerCellId);
    if (!textarea) {
      setDropdownTriggerCellId(null);
      return;
    }

    const cursorPos = textarea.selectionStart;

    // Create chat widget
    const chatWidget = new ChatWidget(voiceName, voiceConfig);

    // Insert widget at cursor (engine will handle @ removal)
    engineRef.current.insertWidgetAtCursor(dropdownTriggerCellId, cursorPos, 'chat', chatWidget.getData());
    setDropdownTriggerCellId(null);
  }, [dropdownTriggerCellId]);

  // @@@ Handle sending chat message
  const handleChatSend = useCallback(async (widgetId: string, message: string) => {
    if (!engineRef.current || !state) return;

    // Find widget
    const widgetCell = state.cells.find(c => c.type === 'widget' && c.id === widgetId);
    if (!widgetCell || widgetCell.type !== 'widget') return;

    const widgetData = widgetCell.data as ChatWidgetData;
    const chatWidget = ChatWidget.fromData(widgetData);

    // Add user message optimistically
    chatWidget.addUserMessage(message);
    engineRef.current.updateWidgetData(widgetId, chatWidget.getData());

    // Mark as processing
    setChatProcessing(prev => new Set(prev).add(widgetId));

    try {
      // Get ALL text from all text cells as unified context
      const allText = state.cells
        .filter(c => c.type === 'text')
        .map(c => (c as TextCell).content)
        .join('');

      // Call backend - use voiceConfig.name as the voice name for the prompt
      const metaPrompt = getMetaPrompt();
      const statePrompt = selectedState && stateConfig.states[selectedState]
        ? stateConfig.states[selectedState].prompt
        : '';
      const response = await chatWithVoice(
        widgetData.voiceConfig.name,  // Use the display name, not the key
        widgetData.voiceConfig,
        chatWidget.getConversationHistory().slice(0, -1), // Exclude last message (just added)
        message,
        allText,
        metaPrompt,
        statePrompt
      );

      // Add assistant response
      chatWidget.addAssistantMessage(response);
      engineRef.current.updateWidgetData(widgetId, chatWidget.getData());
    } catch (error) {
      console.error('Chat failed:', error);
      chatWidget.addAssistantMessage('Sorry, I encountered an error.');
      engineRef.current.updateWidgetData(widgetId, chatWidget.getData());
    } finally {
      setChatProcessing(prev => {
        const next = new Set(prev);
        next.delete(widgetId);
        return next;
      });
    }
  }, [state, selectedState, stateConfig]);

  // @@@ Handle deleting chat widget
  const handleChatDelete = useCallback((widgetId: string) => {
    if (!engineRef.current) return;
    engineRef.current.deleteCell(widgetId);
  }, []);

  // @@@ Helper to get watercolor background
  const getWatercolorBg = (color: string) => {
    const brushes: Record<string, string> = {
      yellow: 'url(https://s2.svgbox.net/pen-brushes.svg?ic=brush-9&color=ffff43)',
      blue: 'url(https://s2.svgbox.net/pen-brushes.svg?ic=brush-7&color=a3d5ff)',
      pink: 'url(https://s2.svgbox.net/pen-brushes.svg?ic=brush-8&color=ffb3d9)',
      green: 'url(https://s2.svgbox.net/pen-brushes.svg?ic=brush-6&color=b3ffb3)',
      purple: 'url(https://s2.svgbox.net/pen-brushes.svg?ic=brush-5&color=ddb3ff)'
    };
    return brushes[color] || 'none';
  };

  // @@@ Render highlighted text for a specific text content
  const renderHighlightedText = (text: string) => {
    if (!state) return null;

    const appliedComments = state.commentors.filter(c => c.appliedAt);

    if (appliedComments.length === 0) {
      return <div style={{ whiteSpace: 'pre-wrap' }}>{text}</div>;
    }

    // Find highlights in this specific text
    const highlights: Array<{ start: number; end: number; comment: Commentor }> = [];
    appliedComments.forEach(comment => {
      const index = text.toLowerCase().indexOf(comment.phrase.toLowerCase());
      if (index !== -1) {
        highlights.push({
          start: index,
          end: index + comment.phrase.length,
          comment
        });
      }
    });

    highlights.sort((a, b) => a.start - b.start);

    const elements: React.ReactNode[] = [];
    let lastEnd = 0;

    highlights.forEach((highlight, idx) => {
      if (highlight.start > lastEnd) {
        elements.push(
          <span key={`text-${idx}`}>
            {text.substring(lastEnd, highlight.start)}
          </span>
        );
      }

      elements.push(
        <span
          key={`highlight-${idx}`}
          className="voice-highlight"
          data-comment-id={highlight.comment.id}
          style={{
            margin: '-2px -6px',
            padding: '2px 6px',
            background: getWatercolorBg(highlight.comment.color),
            transition: 'all 0.2s ease'
          }}
        >
          {text.substring(highlight.start, highlight.end)}
        </span>
      );

      lastEnd = highlight.end;
    });

    if (lastEnd < text.length) {
      elements.push(
        <span key="text-final">
          {text.substring(lastEnd)}
        </span>
      );
    }

    return <div style={{ whiteSpace: 'pre-wrap' }}>{elements}</div>;
  };

  if (!state || !engineRef.current) {
    return <div>Loading...</div>;
  }

  const lastEntry = state.weightPath[state.weightPath.length - 1];
  const currentEnergy = lastEntry?.energy || 0;
  const usedEnergy = state.commentors.filter(c => c.appliedAt).length * 40;
  const unusedEnergy = currentEnergy - usedEnergy;
  const appliedComments = state.commentors.filter(c => c.appliedAt);

  return (
    <>
      {/* @@@ Hide sidebar on mobile */}
      {!isMobile && <LeftSidebar currentView={currentView} onViewChange={setCurrentView} />}

      {currentView === 'writing' && (
        <div style={{
          display: 'flex',
          height: '100vh',
          paddingTop: isMobile ? '0' : '48px',
          paddingBottom: '41px',  // @@@ Space for fixed stats bar at bottom
          fontFamily: 'system-ui, -apple-system, sans-serif',
          boxSizing: 'border-box'
        }}>
          {/* Left spacer for layout - hide on mobile */}
          {!isMobile && (
            <div style={{
              width: '48px',
              backgroundColor: 'transparent',
              position: 'relative',
              flexShrink: 0,
              marginLeft: '12px'
            }}>
              <LeftToolbar
                onStartFresh={handleStartFresh}
                onInsertAgent={handleInsertAgent}
                onToggleAlign={handleToggleAlign}
                onShowCalendar={() => setShowCalendarPopup(true)}
                onSaveToday={handleSaveToday}
                isAligned={commentsAligned}
              />
            </div>
          )}

          {/* @@@ Mobile floating toolbar - top right corner */}
          {isMobile && (
            <div style={{
              position: 'fixed',
              top: '10px',
              right: '10px',
              display: 'flex',
              gap: '8px',
              zIndex: 1000
            }}>
              <button
                onClick={handleStartFresh}
                title="Start Fresh"
                style={{
                  width: '44px',
                  height: '44px',
                  border: 'none',
                  borderRadius: '50%',
                  backgroundColor: '#fff',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
                  transition: 'all 0.2s ease'
                }}
              >
                <FaSync size={20} color="#333" />
              </button>
              <button
                onClick={handleInsertAgent}
                title="Insert Agent Chat"
                style={{
                  width: '44px',
                  height: '44px',
                  border: 'none',
                  borderRadius: '50%',
                  backgroundColor: '#fff',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
                  transition: 'all 0.2s ease',
                  fontSize: '24px',
                  fontWeight: 600,
                  color: '#333',
                  fontFamily: 'monospace'
                }}
              >
                @
              </button>
            </div>
          )}

          <div
            ref={containerRef}
            style={{
              flex: 1,
              position: 'relative',
              overflow: 'hidden',
              // @@@ Disable horizontal scrolling on mobile
              ...(isMobile ? { overflowX: 'hidden', touchAction: 'pan-y' } : {})
            }}
          >
            <div style={{
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              width: '100%',
              margin: '0 auto'
            }}>
              <div style={{
                flex: 1,
                position: 'relative',
                overflow: 'auto',
                padding: '20px',
                paddingBottom: '80px'  // Extra space for smooth scrolling to bottom
              }}>
                <div style={{
                  position: 'relative',
                  maxWidth: '600px'
                }}>
                  {/* State chooser widget - always shown, collapses when state selected */}
                  <div style={{ marginBottom: 24 }}>
                    <StateChooser
                      stateConfig={stateConfig}
                      selectedState={selectedState}
                      onChoose={handleStateChoose}
                    />
                  </div>

                  {/* Render cells sequentially with per-cell highlights */}
                  {state.cells.map((cell, idx) => {
                    if (cell.type === 'text') {
                      const textCell = cell as TextCell;
                      // Use local text if available, otherwise use engine state
                      const content = localTexts.get(cell.id) ?? textCell.content;

                      return (
                        <div key={cell.id} style={{ position: 'relative' }}>
                          {/* Highlight layer for this cell */}
                          <div style={{
                            position: 'absolute',
                            top: 0,
                            left: 0,
                            right: 0,
                            pointerEvents: 'none',
                            fontSize: '18px',
                            lineHeight: '1.8',
                            color: 'transparent',
                            fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
                            zIndex: 0
                          }}>
                            {renderHighlightedText(content)}
                          </div>

                          {/* Textarea for this cell */}
                          <textarea
                            ref={(el) => {
                              if (el) {
                                const wasEmpty = textareaRefs.current.size === 0;
                                textareaRefs.current.set(cell.id, el);
                                // Trigger re-render when first ref is set (once per mount)
                                if (wasEmpty && !refsReadyTriggered.current) {
                                  refsReadyTriggered.current = true;
                                  setRefsReady(prev => prev + 1);
                                }
                                // @@@ Force height to match scrollHeight to prevent internal scrolling
                                el.style.height = 'auto';
                                el.style.height = el.scrollHeight + 'px';
                              } else {
                                textareaRefs.current.delete(cell.id);
                              }
                            }}
                            value={content}
                            onChange={(e) => handleTextChange(cell.id, e.target.value)}
                            onCompositionStart={() => handleCompositionStart(cell.id)}
                            onCompositionEnd={(e) => handleCompositionEnd(cell.id, e)}
                            onPaste={(e) => handlePaste(cell.id, e)}
                            onSelect={(e) => handleCursorChange(cell.id, e)}
                            onClick={(e) => handleCursorChange(cell.id, e)}
                            onKeyUp={(e) => handleCursorChange(cell.id, e)}
                            onKeyDown={(e) => handleKeyDown(cell.id, e)}
                            onFocus={(e) => {
                              // @@@ Prevent browser from scrolling element into view on focus
                              // This stops the "lift up" effect when clicking after scrolling
                              e.preventDefault();
                            }}
                            placeholder={idx === 0 ? "Start writing..." : "Continue writing..."}
                            style={{
                              width: '100%',
                              border: 'none',
                              outline: 'none',
                              resize: 'none',
                              fontSize: '18px',
                              lineHeight: '1.8',
                              fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
                              background: 'transparent',
                              color: '#333',
                              caretColor: '#333',
                              position: 'relative',
                              zIndex: 1,
                              marginBottom: '0px',
                              overflow: 'hidden',
                              overflowWrap: 'break-word',
                              wordWrap: 'break-word',
                              whiteSpace: 'pre-wrap',
                              minHeight: '32px',
                              height: 'auto'
                            }}
                          />
                        </div>
                      );
                    } else if (cell.type === 'widget' && cell.widgetType === 'chat') {
                      return (
                        <ChatWidgetUI
                          key={cell.id}
                          data={cell.data as ChatWidgetData}
                          onSendMessage={(msg) => handleChatSend(cell.id, msg)}
                          onDelete={() => handleChatDelete(cell.id)}
                          isProcessing={chatProcessing.has(cell.id)}
                        />
                      );
                    }
                    return null;
                  })}
                </div>

                {/* Comments layer (absolute positioned) - hide on mobile */}
                {!isMobile && (() => {
                  // @@@ Calculate global max line width across all groups for alignment
                  const globalMaxLineWidth = Math.max(
                    0,
                    ...Array.from(commentGroups.values()).map(g => g.maxLineWidth)
                  );

                  return Array.from(commentGroups.entries()).map(([groupKey, group]) => {
                    const currentIndex = groupPages.get(groupKey) || 0;

                    // @@@ Get the specific textarea for this group's cell
                    const cellTextarea = textareaRefs.current.get(group.cellId);
                    if (!cellTextarea) return null;

                    // @@@ Use offsetTop relative to the content container (with maxWidth: 600px)
                    // This div is at line 1031 with position: relative
                    const cellWrapper = cellTextarea.parentElement; // The div with position: relative
                    if (!cellWrapper) return null;

                    const cellOffsetTop = cellWrapper.offsetTop;

                    // @@@ Calculate line height from textarea styles
                    const computedStyle = window.getComputedStyle(cellTextarea);
                    const fontSize = parseFloat(computedStyle.fontSize) || 18;
                    const lineHeightRatio = parseFloat(computedStyle.lineHeight) / fontSize || 1.8;
                    const lineHeight = fontSize * lineHeightRatio;

                    const containerPadding = parseFloat(window.getComputedStyle(cellWrapper.parentElement || cellWrapper).paddingLeft) || 20;
                    const gap = Math.max(30, window.innerWidth * 0.02);
                    // @@@ Use global max width when aligned, otherwise use group's max width
                    const lineWidthToUse = commentsAligned ? globalMaxLineWidth : group.maxLineWidth;
                    const leftPosition = containerPadding + lineWidthToUse + gap;

                  // @@@ Position using offsetTop (scroll-independent)
                  // centerY is already relative to cell's top, so just add:
                  // - cellOffsetTop: position relative to content container
                  // - 20px: scroll container padding (line 1028)
                  // - 24px: StateChooser marginBottom (line 1036)
                  // - subtract lineHeight: move up to top of 2-line block
                  const topPosition = cellOffsetTop + group.centerY + 20 + 24 - lineHeight * 2;

                  // @@@ If expanded, use the expanded comment ID (stable), otherwise use current index
                  const isExpanded = group.comments.some(c => c.id === expandedCommentId);
                  const displayedComment = isExpanded
                    ? group.comments.find(c => c.id === expandedCommentId)!
                    : group.comments[currentIndex];
                  const displayedIndex = isExpanded
                    ? group.comments.findIndex(c => c.id === expandedCommentId)
                    : currentIndex;

                  if (!displayedComment) return null;

                  return (
                    <CommentGroupCard
                      key={groupKey}
                      comments={group.comments}
                      currentIndex={displayedIndex}
                      onNavigate={(idx) => handleGroupNavigate(groupKey, idx)}
                      position={{
                        top: topPosition,
                        left: leftPosition
                      }}
                      isExpanded={isExpanded}
                      onToggleExpand={() => {
                        setExpandedCommentId(prev => {
                          const anyExpanded = group.comments.some(c => c.id === prev);
                          if (anyExpanded) return null;
                          return displayedComment.id;
                        });
                      }}
                      onStar={() => handleCommentStar(displayedComment.id)}
                      onKill={() => handleCommentKill(displayedComment.id)}
                      onSendChatMessage={(msg) => handleCommentChatSend(displayedComment.id, msg)}
                      isChatProcessing={commentChatProcessing.has(displayedComment.id)}
                    />
                    );
                  });
                })()}

                {/* @@@ Mobile comment popup - show when cursor is in highlighted area */}
                {isMobile && mobileActiveComment && (
                  <div style={{
                    position: 'fixed',
                    bottom: '20px',
                    left: '10px',
                    right: '10px',
                    background: '#fff',
                    border: '2px solid #ddd',
                    borderRadius: '12px',
                    padding: '16px',
                    boxShadow: '0 8px 24px rgba(0,0,0,0.2)',
                    zIndex: 100,
                    fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
                    animation: 'slideInFromBottom 0.3s ease-out'
                  }}>
                    <div style={{
                      display: 'flex',
                      gap: '12px',
                      alignItems: 'flex-start'
                    }}>
                      {(() => {
                        const Icon = iconMap[mobileActiveComment.icon as keyof typeof iconMap] || FaBrain;
                        const colors = colorMap[mobileActiveComment.color] || colorMap.blue;
                        return (
                          <>
                            <Icon size={20} color={colors.text} style={{ marginTop: '2px', flexShrink: 0 }} />
                            <div style={{ flex: 1 }}>
                              <div style={{ fontWeight: 600, fontSize: '16px', color: colors.text, marginBottom: '8px' }}>
                                {mobileActiveComment.voice}
                              </div>
                              <div style={{ fontSize: '15px', lineHeight: '1.5', color: '#444' }}>
                                {mobileActiveComment.comment}
                              </div>
                            </div>
                          </>
                        );
                      })()}
                    </div>
                  </div>
                )}
              </div>

              {/* Debug stats bar at bottom */}
              <div style={{
                position: 'fixed',
                bottom: 0,
                left: 0,
                right: 0,
                padding: '10px 20px',
                borderTop: '1px solid #e0e0e0',
                fontSize: '12px',
                color: '#666',
                display: 'flex',
                gap: '20px',
                backgroundColor: '#fafafa',
                zIndex: 50
              }}>
                <span>Energy: {unusedEnergy}/{currentEnergy}</span>
                <span>Weight: {lastEntry?.weight || 0}</span>
                <span>Applied: {appliedComments.length}</span>
                <span>Groups: {commentGroups.size}</span>
              </div>
            </div>
          </div>

          {/* Agent dropdown */}
          {dropdownVisible && (
            <AgentDropdown
              voices={voiceConfigs}
              position={dropdownPosition}
              onSelect={handleAgentSelect}
              onClose={() => setDropdownVisible(false)}
            />
          )}
        </div>
      )}
      {currentView === 'settings' && (
        <div style={{
          position: 'fixed',
          top: 48,
          left: 0,
          right: 0,
          bottom: 0,
          background: '#f8f0e6',
          display: 'flex',
          overflow: 'hidden'
        }}>
          <VoiceSettings
            defaultVoices={defaultVoiceConfigs}
            onSave={setVoiceConfigs}
          />
        </div>
      )}
      {currentView === 'timeline' && (
        <div style={{
          position: 'fixed',
          top: 48,
          left: 0,
          right: 0,
          bottom: 0,
          background: '#f8f0e6',
          display: 'flex',
          overflow: 'hidden'
        }}>
          <CollectionsView />
        </div>
      )}
      {currentView === 'analysis' && (
        <div style={{
          position: 'fixed',
          top: 48,
          left: 0,
          right: 0,
          bottom: 0,
          background: '#f8f0e6',
          display: 'flex',
          overflow: 'hidden'
        }}>
          <AnalysisView />
        </div>
      )}
      {currentView === 'about' && (
        <div style={{
          position: 'fixed',
          top: 48,
          left: 0,
          right: 0,
          bottom: 0,
          background: '#f8f0e6',
          display: 'flex',
          overflow: 'hidden'
        }}>
          <AboutView />
        </div>
      )}

      {/* Warning Dialog */}
      {showWarning && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            backgroundColor: '#fffef9',
            border: '2px solid #d0c4b0',
            borderRadius: '8px',
            padding: '32px',
            maxWidth: '400px',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.2)',
            fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif"
          }}>
            <h2 style={{
              margin: '0 0 16px 0',
              fontSize: '20px',
              color: '#333',
              fontWeight: 600
            }}>
              Start Fresh?
            </h2>
            <p style={{
              margin: '0 0 24px 0',
              fontSize: '16px',
              lineHeight: '1.6',
              color: '#555'
            }}>
              This will delete all your current writing and comments. This action cannot be undone.
            </p>
            <div style={{
              display: 'flex',
              gap: '12px',
              justifyContent: 'space-between'
            }}>
              <button
                onClick={confirmStartFresh}
                style={{
                  padding: '8px 20px',
                  border: '1px solid #d44',
                  background: '#d44',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '15px',
                  fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
                  color: '#fff',
                  fontWeight: 600,
                  transition: 'all 0.2s'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#c33';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#d44';
                }}
              >
                Delete All
              </button>
              <button
                onClick={() => setShowWarning(false)}
                style={{
                  padding: '8px 20px',
                  border: '1px solid #d0c4b0',
                  background: '#fff',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '15px',
                  fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
                  color: '#333',
                  transition: 'all 0.2s'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#f5f5f5';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#fff';
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Calendar Popup */}
      {showCalendarPopup && (
        <CalendarPopup
          onLoadEntry={handleLoadEntry}
          onClose={() => setShowCalendarPopup(false)}
        />
      )}
    </>
  );
}
