import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { EditorEngine } from './engine/EditorEngine';
import type { EditorState, Commentor, TextCell } from './engine/EditorEngine';
import { ChatWidget } from './engine/ChatWidget';
import type { ChatWidgetData } from './engine/ChatWidget';
import './App.css';
import {
  FaSync,
  FaBrain, FaHeart, FaQuestion, FaCloud, FaTheaterMasks, FaEye,
  FaFistRaised, FaLightbulb, FaShieldAlt, FaWind, FaFire, FaCompass
} from 'react-icons/fa';
import LeftSidebar from './components/LeftSidebar';
import VoiceSettings from './components/VoiceSettings';
import CalendarView from './components/CalendarView';
import AnalysisView from './components/AnalysisView';
import AboutView from './components/AboutView';
import AgentDropdown from './components/AgentDropdown';
import ChatWidgetUI from './components/ChatWidgetUI';
import StateChooser from './components/StateChooser';
import type { VoiceConfig } from './types/voice';
import { getVoices, getMetaPrompt, getStateConfig } from './utils/voiceStorage';
import { getDefaultVoices, chatWithVoice } from './api/voiceApi';

// @@@ Left Toolbar Component - floating toolbelt within left margin
function LeftToolbar({ onStartFresh, onInsertAgent }: { onStartFresh: () => void; onInsertAgent: () => void }) {
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

// @@@ Group Comment Card Component
function CommentGroupCard({
  comments,
  currentIndex,
  onNavigate,
  position
}: {
  comments: Commentor[];
  currentIndex: number;
  onNavigate: (index: number) => void;
  position: { top: number; left: number };
}) {
  const [isHovered, setIsHovered] = React.useState(false);

  if (comments.length === 0) return null;

  const safeIndex = Math.min(Math.max(0, currentIndex), comments.length - 1);
  const currentComment = comments[safeIndex];

  if (!currentComment) return null;

  const Icon = iconMap[currentComment.icon as keyof typeof iconMap] || FaBrain;
  const colors = colorMap[currentComment.color] || colorMap.blue;

  return (
    <div
      style={{
        position: 'absolute',
        top: `${position.top}px`,
        left: `${position.left}px`,
        transform: `translateY(-50%) ${isHovered ? 'scale(1.02)' : 'scale(1)'}`,
        minWidth: '200px',
        maxWidth: '400px',
        height: '54px',
        padding: '8px 12px',
        background: colors.gradient,
        borderLeft: `2px solid ${colors.glow}`,
        borderRadius: '4px',
        fontSize: '13px',
        lineHeight: '1.4',
        zIndex: 10,
        cursor: comments.length > 1 ? 'pointer' : 'default',
        transition: 'all 0.2s ease',
        fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
        boxShadow: isHovered ? '0 4px 12px rgba(0,0,0,0.15)' : 'none',
        animation: 'slideInFromRight 0.3s ease-out',
      }}
      onClick={() => {
        if (comments.length > 1) {
          onNavigate((safeIndex + 1) % comments.length);
        }
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div style={{
        display: 'flex',
        gap: '10px',
        height: '100%',
        alignItems: 'center'
      }}>
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          width: '24px'
        }}>
          <Icon size={15} color={colors.text} style={{ opacity: 0.75 }} />
          {comments.length > 1 && (
            <span style={{
              fontSize: '8px',
              color: colors.text,
              opacity: 0.5,
              marginTop: '1px',
              fontWeight: 500
            }}>
              {safeIndex + 1}/{comments.length}
            </span>
          )}
        </div>

        <div style={{
          flex: 1,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          display: '-webkit-box',
          WebkitLineClamp: 3,
          WebkitBoxOrient: 'vertical',
          color: colors.text,
          opacity: 0.85
        }}>
          <strong style={{ fontWeight: 600 }}>{currentComment.voice}:</strong> {currentComment.comment}
        </div>
      </div>
    </div>
  );
}

// @@@ Main App Component
export default function App() {
  const [currentView, setCurrentView] = useState<'writing' | 'settings' | 'calendar' | 'analysis' | 'about'>('writing');
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

  // @@@ Reset refs ready flag when returning to writing view and focus last text cell
  useEffect(() => {
    if (currentView === 'writing') {
      refsReadyTriggered.current = false;

      // Auto-focus last text cell after a short delay to ensure DOM is ready
      setTimeout(() => {
        if (!state) return;
        const lastTextCell = [...state.cells].reverse().find(c => c.type === 'text');
        if (!lastTextCell) return;

        const textarea = textareaRefs.current.get(lastTextCell.id);
        if (textarea) {
          textarea.focus();
          // Move cursor to end
          textarea.selectionStart = textarea.value.length;
          textarea.selectionEnd = textarea.value.length;
        }
      }, 100);
    }
  }, [currentView, state]);

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
    setGroupPages(prev => {
      const next = new Map(prev);
      next.set(groupKey, newIndex);
      return next;
    });
  }, []);

  // @@@ Cursor-based comment navigation (per-cell)
  useEffect(() => {
    if (!state || !cursorCellId) return;

    // Get text for the cell where cursor is
    const cell = state.cells.find(c => c.id === cursorCellId);
    if (!cell || cell.type !== 'text') return;

    const cellText = (cell as TextCell).content;
    const appliedComments = state.commentors.filter(c => c.appliedAt);
    if (appliedComments.length === 0) return;

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

    if (!foundComment) return;

    // Find the group key for this cell and navigate to the comment
    commentGroups.forEach((group, groupKey) => {
      // Only update groups in the current cell
      if (group.cellId !== cursorCellId) return;

      const commentIndex = group.comments.findIndex(c => c.id === foundComment!.id);
      if (commentIndex !== -1) {
        setGroupPages(prev => {
          const next = new Map(prev);
          if (next.get(groupKey) !== commentIndex) {
            next.set(groupKey, commentIndex);
          }
          return next;
        });
      }
    });
  }, [cursorPosition, cursorCellId, state, commentGroups]);

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
      <LeftSidebar currentView={currentView} onViewChange={setCurrentView} />
      {currentView === 'writing' && (
        <div style={{
          display: 'flex',
          height: '100vh',
          paddingTop: '48px',
          fontFamily: 'system-ui, -apple-system, sans-serif'
        }}>
          {/* Left spacer for layout */}
          <div style={{
            width: '48px',
            backgroundColor: 'transparent',
            position: 'relative',
            flexShrink: 0,
            marginLeft: '12px'
          }}>
            <LeftToolbar onStartFresh={handleStartFresh} onInsertAgent={handleInsertAgent} />
          </div>

          <div
            ref={containerRef}
            style={{
              flex: 1,
              position: 'relative',
              overflow: 'hidden'
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
                padding: '20px'
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

                {/* Comments layer (absolute positioned) */}
                {Array.from(commentGroups.entries()).map(([groupKey, group]) => {
                  const currentIndex = groupPages.get(groupKey) || 0;

                  // @@@ Get the specific textarea for this group's cell
                  const cellTextarea = textareaRefs.current.get(group.cellId);
                  if (!cellTextarea) return null;

                  // Calculate position relative to this cell's textarea
                  const cellRect = cellTextarea.getBoundingClientRect();
                  const containerRect = containerRef.current?.getBoundingClientRect();
                  if (!containerRect) return null;

                  const containerPadding = parseFloat(window.getComputedStyle(cellTextarea.parentElement || cellTextarea).paddingLeft) || 20;
                  const gap = Math.max(30, window.innerWidth * 0.02);
                  const leftPosition = containerPadding + group.maxLineWidth + gap;

                  // @@@ Position relative to cell's top, not global document
                  // centerY is already relative to cell's top, so just add cell offset
                  const topPosition = cellRect.top - containerRect.top + group.centerY;

                  return (
                    <CommentGroupCard
                      key={groupKey}
                      comments={group.comments}
                      currentIndex={currentIndex}
                      onNavigate={(idx) => handleGroupNavigate(groupKey, idx)}
                      position={{
                        top: topPosition,
                        left: leftPosition
                      }}
                    />
                  );
                })}
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
      {currentView === 'calendar' && (
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
          <CalendarView />
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
    </>
  );
}
