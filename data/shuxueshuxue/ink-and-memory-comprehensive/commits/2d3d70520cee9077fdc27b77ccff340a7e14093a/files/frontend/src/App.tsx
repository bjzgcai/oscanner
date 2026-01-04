import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { EditorEngine } from './engine/EditorEngine';
import type { EditorState, Commentor, TextCell } from './engine/EditorEngine';
import './App.css';
import {
  FaSync, FaBold, FaItalic, FaUnderline, FaAlignLeft, FaAlignCenter,
  FaAlignRight, FaListUl, FaListOl, FaQuoteRight, FaTable, FaLink, FaImage,
  FaBrain, FaHeart, FaQuestion, FaCloud, FaTheaterMasks, FaEye,
  FaFistRaised, FaLightbulb, FaShieldAlt, FaWind, FaFire, FaCompass
} from 'react-icons/fa';

// @@@ Left Toolbar Component
function LeftToolbar({ onStartFresh }: { onStartFresh: () => void }) {
  const tools = [
    { icon: FaSync, tooltip: 'Start Fresh', action: onStartFresh, functional: true, separator: true },
    { icon: FaBold, tooltip: 'Bold', functional: false, separator: false },
    { icon: FaItalic, tooltip: 'Italic', functional: false, separator: false },
    { icon: FaUnderline, tooltip: 'Underline', functional: false, separator: true },
    { icon: FaAlignLeft, tooltip: 'Align Left', functional: false, separator: false },
    { icon: FaAlignCenter, tooltip: 'Align Center', functional: false, separator: false },
    { icon: FaAlignRight, tooltip: 'Align Right', functional: false, separator: true },
    { icon: FaListUl, tooltip: 'Bullet List', functional: false, separator: false },
    { icon: FaListOl, tooltip: 'Numbered List', functional: false, separator: true },
    { icon: FaQuoteRight, tooltip: 'Quote', functional: false, separator: false },
    { icon: FaTable, tooltip: 'Insert Table', functional: false, separator: false },
    { icon: FaLink, tooltip: 'Insert Link', functional: false, separator: false },
    { icon: FaImage, tooltip: 'Insert Image', functional: false, separator: false },
  ];

  return (
    <div style={{
      width: '48px',
      borderRight: '1px solid #e0e0e0',
      backgroundColor: '#fafafa',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      paddingTop: '10px',
      gap: '4px'
    }}>
      {tools.map((tool, idx) => (
        <React.Fragment key={idx}>
          <button
            onClick={tool.functional ? tool.action : undefined}
            disabled={!tool.functional}
            title={tool.tooltip}
            style={{
              width: '36px',
              height: '36px',
              border: 'none',
              borderRadius: '4px',
              backgroundColor: tool.functional ? '#fff' : 'transparent',
              cursor: tool.functional ? 'pointer' : 'not-allowed',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              opacity: tool.functional ? 1 : 0.3,
              transition: 'all 0.2s ease',
              ...(tool.functional && {
                ':hover': {
                  backgroundColor: '#f0f0f0'
                }
              })
            }}
            onMouseEnter={tool.functional ? (e) => {
              e.currentTarget.style.backgroundColor = '#f0f0f0';
            } : undefined}
            onMouseLeave={tool.functional ? (e) => {
              e.currentTarget.style.backgroundColor = '#fff';
            } : undefined}
          >
            <tool.icon size={18} color={tool.functional ? '#333' : '#999'} />
          </button>
          {tool.separator && idx < tools.length - 1 && (
            <div style={{
              width: '30px',
              height: '1px',
              backgroundColor: '#e0e0e0',
              margin: '4px 0'
            }} />
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

// @@@ Icon map with React Icons (matching original)
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

// @@@ Color map with gradient colors for watercolor effect (right to left fade)
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

// @@@ Group Comment Card Component - elegant gradient watercolor style
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

  // @@@ Bounds check - ensure currentIndex is valid
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
        height: '54px', // Fixed 3 rows: ~18px per row
        padding: '8px 12px',
        background: colors.gradient,
        borderLeft: `2px solid ${colors.glow}`,
        borderRadius: '4px',
        fontSize: '13px',
        lineHeight: '1.4',
        zIndex: 10,
        cursor: comments.length > 1 ? 'pointer' : 'default',
        transition: 'all 0.2s ease',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        boxShadow: isHovered ? '0 4px 12px rgba(0,0,0,0.15)' : 'none',
        animation: 'slideInFromRight 0.3s ease-out',
      }}
      onClick={() => {
        // Click to cycle through comments (only if multiple)
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
        {/* Icon with pagination counter below */}
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

        {/* Voice name inline with comment */}
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
  const engineRef = useRef<EditorEngine | null>(null);
  const [state, setState] = useState<EditorState | null>(null);
  const [localText, setLocalText] = useState(''); // Local text for textarea
  const [isComposing, setIsComposing] = useState(false);
  const [groupPages, setGroupPages] = useState<Map<number, number>>(new Map());
  const [cursorPosition, setCursorPosition] = useState<number>(0);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Initialize engine
  useEffect(() => {
    const sessionId = crypto.randomUUID ? crypto.randomUUID() : Date.now().toString();
    const engine = new EditorEngine(sessionId);
    engineRef.current = engine;

    // Subscribe to state changes
    engine.subscribe((newState) => {
      setState({ ...newState });
      // Save to localStorage
      localStorage.setItem('ink_memory_state', JSON.stringify(newState));
    });

    // Load saved state if exists
    const saved = localStorage.getItem('ink_memory_state');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        engine.loadState(parsed);

        // Load initial text and state together
        const textCell = parsed.cells?.find((c: any) => c.type === 'text');
        const initialText = textCell?.content || '';

        setLocalText(initialText);
        setState(engine.getState());

        // Double-check: force re-render after a tick to ensure everything is initialized
        setTimeout(() => {
          setLocalText(initialText);
          setState({ ...engine.getState() });
        }, 10);
      } catch (e) {
        console.error('Failed to load saved state:', e);
      }
    } else {
      setState(engine.getState());
    }
  }, []);

  // Sync local text with state (when not composing)
  useEffect(() => {
    if (!isComposing && state) {
      const textCell = state.cells.find(c => c.type === 'text') as TextCell;
      if (textCell) {
        setLocalText(textCell.content || '');
      }
    }
  }, [state, isComposing]);

  // @@@ Group comments by 2-row blocks using visual lines (accounting for wrapping)
  const commentGroups = useMemo(() => {
    const groups = new Map<number, {
      comments: Commentor[];
      blockIndex: number;
      visualLineStart: number;
      visualLineEnd: number;
      maxLineWidth: number;
      centerY: number;
    }>();

    if (!textareaRef.current || !state) return groups;

    const text = localText;
    const maxTextareaWidth = 600;

    // Get actual line height from computed styles
    const computedStyle = window.getComputedStyle(textareaRef.current);
    const fontSize = parseFloat(computedStyle.fontSize) || 18;
    const lineHeightRatio = parseFloat(computedStyle.lineHeight) / fontSize || 1.8;
    const lineHeight = fontSize * lineHeightRatio;

    // Create a temporary canvas to measure text width
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    if (ctx) {
      // Use actual font from computed styles
      const fontFamily = computedStyle.fontFamily || 'system-ui, -apple-system, sans-serif';
      ctx.font = `${fontSize}px ${fontFamily}`;
    }

    // @@@ Build a map from character index to visual line number
    const charToVisualLine: number[] = new Array(text.length);
    let currentVisualLine = 0;
    let currentLineStartIndex = 0;

    for (let i = 0; i < text.length; i++) {
      charToVisualLine[i] = currentVisualLine;

      if (text[i] === '\n') {
        // Hard line break - move to next visual line
        currentVisualLine++;
        currentLineStartIndex = i + 1;
      } else {
        // Check if we need to wrap
        const currentLineText = text.substring(currentLineStartIndex, i + 1);
        const width = ctx ? ctx.measureText(currentLineText).width : currentLineText.length * (fontSize * 0.6);

        if (width > maxTextareaWidth && i > currentLineStartIndex) {
          // This character causes a wrap - move to next visual line
          currentVisualLine++;
          currentLineStartIndex = i;
          charToVisualLine[i] = currentVisualLine;
        }
      }
    }

    // Process each commentor
    state.commentors
      .filter(c => c.appliedAt)
      .forEach(commentor => {
        const index = text.toLowerCase().indexOf(commentor.phrase.toLowerCase());
        if (index === -1) return;

        // Get visual line number for this character position
        const visualLineNumber = charToVisualLine[index] || 0;

        // Determine which 2-row block this belongs to (0-1, 2-3, 4-5, etc.)
        const blockIndex = Math.floor(visualLineNumber / 2);
        const visualLineStart = blockIndex * 2;
        const visualLineEnd = visualLineStart + 1;

        if (!groups.has(blockIndex)) {
          // For visual lines, we can assume they're all ~700px wide (or less)
          // So maxWidth is just the width of the longer of the two visual lines in this block
          let maxWidth = 0;

          // Find all text on these two visual lines
          for (let i = 0; i < text.length; i++) {
            const vLine = charToVisualLine[i];
            if (vLine === visualLineStart || vLine === visualLineEnd) {
              // Find the end of this visual line
              let lineEnd = i;
              while (lineEnd < text.length && charToVisualLine[lineEnd] === vLine) {
                lineEnd++;
              }
              const lineText = text.substring(i, lineEnd);
              const width = ctx ? ctx.measureText(lineText).width : lineText.length * (fontSize * 0.6);
              maxWidth = Math.max(maxWidth, Math.min(width, maxTextareaWidth));
              i = lineEnd - 1; // Skip to end of this visual line
            }
          }

          // Calculate vertical center of the 2-row block
          const centerY = (visualLineStart + 1) * lineHeight;

          groups.set(blockIndex, {
            comments: [],
            blockIndex,
            visualLineStart,
            visualLineEnd,
            maxLineWidth: maxWidth,
            centerY
          });
        }

        groups.get(blockIndex)!.comments.push(commentor);
      });

    return groups;
  }, [state?.commentors, localText, state]);

  // @@@ Auto-switch to newest comment when group size changes
  useEffect(() => {
    if (!commentGroups) return;

    setGroupPages(prev => {
      const next = new Map(prev);

      // For each group, ensure the page index is valid
      commentGroups.forEach((group, blockIndex) => {
        if (group.comments.length === 0) {
          next.delete(blockIndex);
          return;
        }

        const currentPage = prev.get(blockIndex) || 0;
        const maxPage = group.comments.length - 1;

        // If we're on an old page and there are new comments, switch to the newest
        if (group.comments.length > 1 && currentPage < maxPage) {
          next.set(blockIndex, maxPage); // Show the newest comment
        } else if (currentPage > maxPage) {
          // Current page is out of bounds, reset to last valid page
          next.set(blockIndex, maxPage);
        }
      });

      // Remove pages for groups that no longer exist
      prev.forEach((_, blockIndex) => {
        if (!commentGroups.has(blockIndex)) {
          next.delete(blockIndex);
        }
      });

      return next;
    });
  }, [commentGroups]);

  // @@@ Handle page navigation for comment groups
  const handleGroupNavigate = useCallback((blockIndex: number, newIndex: number) => {
    setGroupPages(prev => {
      const next = new Map(prev);
      next.set(blockIndex, newIndex);
      return next;
    });
  }, []);

  // @@@ Detect which comment the cursor is inside and switch to it
  useEffect(() => {
    if (!state || !localText) return;

    const appliedComments = state.commentors.filter(c => c.appliedAt);
    if (appliedComments.length === 0) return;

    // Find which comment contains the cursor
    let foundComment: Commentor | null = null;
    for (const comment of appliedComments) {
      const index = localText.toLowerCase().indexOf(comment.phrase.toLowerCase());
      if (index !== -1) {
        const start = index;
        const end = index + comment.phrase.length;

        // Check if cursor is inside this phrase
        if (cursorPosition >= start && cursorPosition <= end) {
          foundComment = comment;
          break;
        }
      }
    }

    if (!foundComment) return;

    // Find which group this comment belongs to
    commentGroups.forEach((group, blockIndex) => {
      const commentIndex = group.comments.findIndex(c => c.id === foundComment!.id);
      if (commentIndex !== -1) {
        // Switch to this comment in the group
        setGroupPages(prev => {
          const next = new Map(prev);
          if (next.get(blockIndex) !== commentIndex) {
            next.set(blockIndex, commentIndex);
          }
          return next;
        });
      }
    });
  }, [cursorPosition, state, localText, commentGroups]);

  // @@@ Handle text changes (with IME support)
  const handleTextChange = useCallback((newText: string) => {
    // Always update local text for the textarea
    setLocalText(newText);
    // Only update the engine when not composing
    if (!isComposing && engineRef.current) {
      engineRef.current.updateText(newText);
    }
  }, [isComposing]);

  const handleCompositionStart = useCallback(() => {
    setIsComposing(true);
  }, []);

  const handleCompositionEnd = useCallback((e: React.CompositionEvent<HTMLTextAreaElement>) => {
    setIsComposing(false);
    const newText = e.currentTarget.value;
    setLocalText(newText);
    if (engineRef.current) {
      engineRef.current.updateText(newText);
    }
  }, []);

  // @@@ Handle paste events to ensure highlighting is triggered
  const handlePaste = useCallback((e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    // Let the default paste happen, then update the engine
    setTimeout(() => {
      const newText = e.currentTarget.value;
      setLocalText(newText);
      if (engineRef.current) {
        engineRef.current.updateText(newText);
      }
    }, 0);
  }, []);

  // @@@ Handle cursor position changes
  const handleCursorChange = useCallback(() => {
    if (textareaRef.current) {
      setCursorPosition(textareaRef.current.selectionStart);
    }
  }, []);

  // @@@ Handle Start Fresh
  const handleStartFresh = useCallback(() => {
    if (confirm('Clear everything and start fresh? This will delete all your current writing and comments.')) {
      localStorage.removeItem('ink_memory_state');
      window.location.reload();
    }
  }, []);

  // @@@ Render text with highlights
  const renderHighlightedText = () => {
    if (!state) return null;

    const appliedComments = state.commentors.filter(c => c.appliedAt);

    if (appliedComments.length === 0) {
      return <div style={{ whiteSpace: 'pre-wrap' }}>{localText}</div>;
    }

    // Create highlight ranges
    const highlights: Array<{ start: number; end: number; comment: Commentor }> = [];
    appliedComments.forEach(comment => {
      const index = localText.toLowerCase().indexOf(comment.phrase.toLowerCase());
      if (index !== -1) {
        highlights.push({
          start: index,
          end: index + comment.phrase.length,
          comment
        });
      }
    });

    // Sort by start position
    highlights.sort((a, b) => a.start - b.start);

    // Build highlighted text
    const elements: React.ReactNode[] = [];
    let lastEnd = 0;

    // Get watercolor brush URL for color
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

    highlights.forEach((highlight, idx) => {
      // Add text before highlight
      if (highlight.start > lastEnd) {
        elements.push(
          <span key={`text-${idx}`}>
            {localText.substring(lastEnd, highlight.start)}
          </span>
        );
      }

      // Add highlighted text with watercolor effect
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
          {localText.substring(highlight.start, highlight.end)}
        </span>
      );

      lastEnd = highlight.end;
    });

    // Add remaining text
    if (lastEnd < localText.length) {
      elements.push(
        <span key="text-final">
          {localText.substring(lastEnd)}
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
    <div style={{
      display: 'flex',
      height: '100vh',
      fontFamily: 'system-ui, -apple-system, sans-serif'
    }}>
      {/* Left Toolbar */}
      <LeftToolbar onStartFresh={handleStartFresh} />

      {/* Main Editor Area with Inline Comments */}
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
          {/* Status Bar */}
          <div style={{
            padding: '10px 20px',
            borderBottom: '1px solid #e0e0e0',
            fontSize: '12px',
            color: '#666',
            display: 'flex',
            gap: '20px',
            backgroundColor: '#fafafa'
          }}>
            <span>Energy: {unusedEnergy}/{currentEnergy}</span>
            <span>Weight: {lastEntry?.weight || 0}</span>
            <span>Applied: {appliedComments.length}</span>
            <span>Groups: {commentGroups.size}</span>
          </div>

          {/* Writing Area with Comments */}
          <div style={{
            flex: 1,
            position: 'relative',
            overflow: 'auto',
            padding: '40px'
          }}>
            {/* Highlighted text overlay */}
            <div style={{
              position: 'absolute',
              top: '40px',
              left: '40px',
              right: '40px',
              maxWidth: '600px',
              pointerEvents: 'none',
              fontSize: '18px',
              lineHeight: '1.8',
              color: 'transparent',
              fontFamily: 'inherit'
            }}>
              {renderHighlightedText()}
            </div>

            {/* Textarea */}
            <textarea
              ref={textareaRef}
              value={localText}
              onChange={(e) => handleTextChange(e.target.value)}
              onCompositionStart={handleCompositionStart}
              onCompositionEnd={handleCompositionEnd}
              onPaste={handlePaste}
              onSelect={handleCursorChange}
              onClick={handleCursorChange}
              onKeyUp={handleCursorChange}
              placeholder="Start writing..."
              style={{
                width: '100%',
                maxWidth: '600px',
                minHeight: '100%',
                border: 'none',
                outline: 'none',
                resize: 'none',
                fontSize: '18px',
                lineHeight: '1.8',
                fontFamily: 'inherit',
                background: 'transparent',
                color: '#333',
                caretColor: '#333',
                position: 'relative',
                zIndex: 1
              }}
            />

            {/* Comment Groups - positioned absolutely based on 2-row blocks */}
            {Array.from(commentGroups.entries()).map(([blockIndex, group]) => {
              const currentIndex = groupPages.get(blockIndex) || 0;

              // Get actual padding values from the container
              const containerPadding = textareaRef.current?.parentElement ?
                parseFloat(window.getComputedStyle(textareaRef.current.parentElement).paddingLeft) || 40 : 40;

              // Dynamic gap based on viewport size
              const gap = Math.max(30, window.innerWidth * 0.02); // Min 30px, scales with viewport

              const leftPosition = containerPadding + group.maxLineWidth + gap;

              return (
                <CommentGroupCard
                  key={blockIndex}
                  comments={group.comments}
                  currentIndex={currentIndex}
                  onNavigate={(idx) => handleGroupNavigate(blockIndex, idx)}
                  position={{
                    top: group.centerY + containerPadding,
                    left: leftPosition
                  }}
                />
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}