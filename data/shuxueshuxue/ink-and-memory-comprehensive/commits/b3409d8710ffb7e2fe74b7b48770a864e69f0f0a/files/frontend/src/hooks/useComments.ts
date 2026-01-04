import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import type { MutableRefObject, Dispatch, SetStateAction, SyntheticEvent } from 'react';
import type { EditorState, Commentor, TextCell, EditorEngine } from '../engine/EditorEngine';
import { findNormalizedPhrase } from '../utils/textNormalize';
import { getMetaPrompt, getStateConfig } from '../utils/voiceStorage';
import { chatWithVoice } from '../api/voiceApi';

export interface CommentGroup {
  comments: Commentor[];
  cellId: string;
  blockIndex: number;
  visualLineStart: number;
  visualLineEnd: number;
  maxLineWidth: number;
  centerY: number;
}

export interface UseCommentsOptions {
  state: EditorState | null;
  textareaRefs: MutableRefObject<Map<string, HTMLTextAreaElement>>;
  refsReady: number;
  selectedState: string | null;
  stateConfig: ReturnType<typeof getStateConfig>;
  isMobile: boolean;
  engineRef: MutableRefObject<EditorEngine | null>;
}

export interface UseCommentsReturn {
  commentGroups: Map<string, CommentGroup>;
  groupPages: Map<string, number>;
  handleGroupNavigate: (groupKey: string, newIndex: number) => void;
  expandedCommentId: string | null;
  setExpandedCommentId: Dispatch<SetStateAction<string | null>>;
  mobileActiveComment: Commentor | null;
  cursorPosition: number;
  cursorCellId: string | null;
  handleCursorChange: (cellId: string, e: SyntheticEvent<HTMLTextAreaElement>) => void;
  handleCommentStar: (commentId: string) => void;
  handleCommentKill: (commentId: string) => void;
  handleCommentChatSend: (commentId: string, message: string) => Promise<void>;
  commentChatProcessing: Set<string>;
}

// @@@ Comment management hook - groups, navigation, and chat handling
export function useComments({
  state,
  textareaRefs,
  refsReady,
  selectedState,
  stateConfig,
  isMobile,
  engineRef,
}: UseCommentsOptions): UseCommentsReturn {
  const [groupPages, setGroupPages] = useState<Map<string, number>>(new Map());
  const prevGroupSignatures = useRef<Map<string, string>>(new Map());
  const manualLockSignatures = useRef<Map<string, string>>(new Map());
  const [cursorPosition, setCursorPosition] = useState<number>(0);
  const [cursorCellId, setCursorCellId] = useState<string | null>(null);
  const [mobileActiveComment, setMobileActiveComment] = useState<Commentor | null>(null);
  const [expandedCommentId, setExpandedCommentId] = useState<string | null>(null);
  const [commentChatProcessing, setCommentChatProcessing] = useState<Set<string>>(new Set());

  const commentGroups = useMemo(() => {
    const groups = new Map<string, CommentGroup>();

    if (!state) return groups;

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

    state.cells.forEach(cell => {
      if (cell.type !== 'text') return;

      const textCell = cell as TextCell;
      const text = textCell.content;

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

      state.commentors
        .filter(c => c.appliedAt)
        .forEach(commentor => {
          const index = findNormalizedPhrase(text, commentor.phrase);
          if (index === -1) return;

          const visualLineNumber = charToVisualLine[index] || 0;
          const blockIndex = Math.floor(visualLineNumber / 2);
          const visualLineStart = blockIndex * 2;
          const visualLineEnd = visualLineStart + 1;
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
  }, [state?.commentors, state, refsReady, selectedState]);

  // @@@ Auto-advance on new comment - jump to latest only when signature changes
  useEffect(() => {
    const currentSignatures = new Map<string, string>();
    commentGroups.forEach((group, groupKey) => {
      const signature = group.comments.map(c => c.id).join("|");
      currentSignatures.set(groupKey, signature);
    });

    setGroupPages(prev => {
      const next = new Map(prev);

      commentGroups.forEach((group, groupKey) => {
        if (group.comments.length === 0) {
          next.delete(groupKey);
          return;
        }

        const currentPage = prev.get(groupKey) ?? 0;
        const maxPage = group.comments.length - 1;
        const isNewGroup = !prev.has(groupKey);
        const currentSignature = currentSignatures.get(groupKey) || "";
        const prevSignature = prevGroupSignatures.current.get(groupKey) || "";
        const signatureChanged = currentSignature !== prevSignature;
        const manualLockSignature = manualLockSignatures.current.get(groupKey) || "";

        if (isNewGroup) {
          next.set(groupKey, maxPage);
        } else if (signatureChanged && manualLockSignature !== currentSignature) {
          next.set(groupKey, maxPage);
        } else if (currentPage < maxPage && manualLockSignature !== currentSignature) {
          next.set(groupKey, maxPage);
        } else if (currentPage > maxPage) {
          next.set(groupKey, maxPage);
        }
      });

      prev.forEach((_, groupKey) => {
        if (!commentGroups.has(groupKey)) {
          next.delete(groupKey);
          manualLockSignatures.current.delete(groupKey);
        }
      });

      return next;
    });

    prevGroupSignatures.current = currentSignatures;
  }, [commentGroups]);

  const handleGroupNavigate = useCallback((groupKey: string, newIndex: number) => {
    const group = commentGroups.get(groupKey);
    if (!group) return;

    setGroupPages(prev => {
      const next = new Map(prev);
      next.set(groupKey, newIndex);
      return next;
    });

    const anyExpanded = group.comments.some(c => c.id === expandedCommentId);
    if (anyExpanded && group.comments[newIndex]) {
      setExpandedCommentId(group.comments[newIndex].id);
    }

    const signature = group.comments.map(c => c.id).join("|");
    manualLockSignatures.current.set(groupKey, signature);
  }, [commentGroups, expandedCommentId]);

  useEffect(() => {
    if (!state || !cursorCellId) return;

    const cell = state.cells.find(c => c.id === cursorCellId);
    if (!cell || cell.type !== 'text') return;

    const cellText = (cell as TextCell).content;
    const appliedComments = state.commentors.filter(c => c.appliedAt);
    if (appliedComments.length === 0) {
      if (isMobile) setMobileActiveComment(null);
      return;
    }

    let foundComment: Commentor | null = null;
    for (const comment of appliedComments) {
      const index = findNormalizedPhrase(cellText, comment.phrase);
      if (index !== -1) {
        const start = index;
        const end = index + comment.phrase.length;

        if (cursorPosition >= start && cursorPosition <= end) {
          foundComment = comment;
          break;
        }
      }
    }

    if (isMobile) {
      setMobileActiveComment(foundComment);
    }

    if (!foundComment || isMobile) return;

    commentGroups.forEach((group, groupKey) => {
      if (group.cellId !== cursorCellId) return;

      const commentIndex = group.comments.findIndex(c => c.id === foundComment!.id);
      if (commentIndex !== -1) {
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
  }, [cursorPosition, cursorCellId, state, commentGroups, isMobile, expandedCommentId]);

  const handleCursorChange = useCallback((cellId: string, e: SyntheticEvent<HTMLTextAreaElement>) => {
    setCursorPosition(e.currentTarget.selectionStart);
    setCursorCellId(cellId);
  }, []);

  const handleCommentStar = useCallback((commentId: string) => {
    if (!engineRef.current) return;
    const comment = engineRef.current.getComment(commentId);
    if (!comment) return;

    const newFeedback = comment.feedback === 'star' ? undefined : 'star';
    engineRef.current.setCommentFeedback(commentId, newFeedback as any);
  }, [engineRef]);

  const handleCommentKill = useCallback((commentId: string) => {
    if (!engineRef.current) return;
    engineRef.current.setCommentFeedback(commentId, 'kill');
    setExpandedCommentId(null);
  }, [engineRef]);

  const handleCommentChatSend = useCallback(async (commentId: string, message: string) => {
    if (!engineRef.current || !state) return;

    const comment = engineRef.current.getComment(commentId);
    if (!comment) return;

    engineRef.current.addCommentChatMessage(commentId, 'user', message);
    setCommentChatProcessing(prev => new Set(prev).add(commentId));

    try {
      const allText = state.cells
        .filter(c => c.type === 'text')
        .map(c => (c as TextCell).content)
        .join('');

      const chatHistory = comment.chatHistory?.slice(0, -1) || [];

      const metaPrompt = getMetaPrompt();
      const statePrompt = selectedState && stateConfig.states[selectedState]
        ? stateConfig.states[selectedState].prompt
        : '';

      const voiceId = comment.voiceId || comment.voice;

      const response = await chatWithVoice(
        voiceId,
        chatHistory,
        message,
        allText,
        metaPrompt,
        statePrompt
      );

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
  }, [state, selectedState, stateConfig, engineRef]);

  return {
    commentGroups,
    groupPages,
    handleGroupNavigate,
    expandedCommentId,
    setExpandedCommentId,
    mobileActiveComment,
    cursorPosition,
    cursorCellId,
    handleCursorChange,
    handleCommentStar,
    handleCommentKill,
    handleCommentChatSend,
    commentChatProcessing,
  };
}
