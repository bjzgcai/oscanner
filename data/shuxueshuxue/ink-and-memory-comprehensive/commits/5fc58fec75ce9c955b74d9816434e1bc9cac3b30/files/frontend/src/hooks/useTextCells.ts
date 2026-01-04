import { useState, useCallback, useRef, useEffect } from 'react';
import type { RefObject, Dispatch, SetStateAction } from 'react';
import type { EditorEngine, EditorState, TextCell } from '../engine/EditorEngine';

export interface UseTextCellsOptions {
  engineRef: RefObject<EditorEngine | null>;
  state: EditorState | null;
  onInspirationTextChange?: (allText: string, selectedState: string | null) => void;
  selectedState?: string | null;
  dropdownVisible?: boolean;
  dropdownTriggerCellId?: string | null;
  onDropdownClose?: () => void;
}

export interface UseTextCellsReturn {
  localTexts: Map<string, string>;
  setLocalTexts: React.Dispatch<React.SetStateAction<Map<string, string>>>;
  composingCells: Set<string>;
  textareaRefs: React.MutableRefObject<Map<string, HTMLTextAreaElement>>;
  refsReady: number;
  refsReadyTriggered: React.MutableRefObject<boolean>;
  setRefsReady: Dispatch<SetStateAction<number>>;
  handleTextChange: (cellId: string, newText: string) => void;
  handleCompositionStart: (cellId: string) => void;
  handleCompositionEnd: (cellId: string, e: React.CompositionEvent<HTMLTextAreaElement>) => void;
  handlePaste: (cellId: string, e: React.ClipboardEvent<HTMLTextAreaElement>) => void;
  handleKeyDown: (cellId: string, e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  createTextareaRef: (cellId: string) => (el: HTMLTextAreaElement | null) => void;
}

// @@@ Text cell management hook: tracks local text, IME composition, and textarea refs
export function useTextCells({
  engineRef,
  state,
  onInspirationTextChange,
  selectedState,
  dropdownVisible,
  dropdownTriggerCellId,
  onDropdownClose,
}: UseTextCellsOptions): UseTextCellsReturn {
  const [localTexts, setLocalTexts] = useState<Map<string, string>>(new Map());
  const [composingCells, setComposingCells] = useState<Set<string>>(new Set());

  const textareaRefs = useRef<Map<string, HTMLTextAreaElement>>(new Map());
  const [refsReady, setRefsReady] = useState(0);
  const refsReadyTriggered = useRef(false);

  useEffect(() => {
    if (state) {
      setLocalTexts(prev => {
        const next = new Map(prev);
        state.cells.filter(c => c.type === 'text').forEach(cell => {
          const textCell = cell as TextCell;
          if (!composingCells.has(cell.id)) {
            next.set(cell.id, textCell.content || '');
          }
        });
        return next;
      });
    }
  }, [state, composingCells]);

  const handleTextChange = useCallback((cellId: string, newText: string) => {
    setLocalTexts(prev => {
      const next = new Map(prev);
      next.set(cellId, newText);
      return next;
    });

    const textarea = textareaRefs.current.get(cellId);
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = textarea.scrollHeight + 'px';
    }

    if (dropdownVisible && dropdownTriggerCellId === cellId && !newText.includes('@')) {
      onDropdownClose?.();
    }

    if (!composingCells.has(cellId) && engineRef.current) {
      engineRef.current.updateTextCell(cellId, newText);
    }

    if (onInspirationTextChange && state) {
      const allText = state.cells
        .filter(c => c.type === 'text')
        .map(c => {
          if (c.id === cellId) return newText;
          return (c as TextCell).content;
        })
        .join('');
      onInspirationTextChange(allText, selectedState ?? null);
    }
  }, [
    composingCells,
    dropdownVisible,
    dropdownTriggerCellId,
    onDropdownClose,
    engineRef,
    state,
    onInspirationTextChange,
    selectedState
  ]);

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
  }, [engineRef]);

  const handlePaste = useCallback((cellId: string, e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const textarea = e.currentTarget;
    setTimeout(() => {
      const newText = textarea.value;
      setLocalTexts(prev => {
        const next = new Map(prev);
        next.set(cellId, newText);
        return next;
      });
      if (engineRef.current) {
        engineRef.current.updateTextCell(cellId, newText);
      }
    }, 0);
  }, [engineRef]);

  const handleKeyDown = useCallback((cellId: string, e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Escape' && dropdownVisible) {
      onDropdownClose?.();
    }

    if (e.key === '@' && composingCells.has(cellId)) {
      e.preventDefault();
    }
  }, [composingCells, dropdownVisible, onDropdownClose]);

  const createTextareaRef = useCallback((cellId: string) => {
    return (el: HTMLTextAreaElement | null) => {
      if (el) {
        const wasEmpty = textareaRefs.current.size === 0;
        textareaRefs.current.set(cellId, el);
        if (wasEmpty && !refsReadyTriggered.current) {
          refsReadyTriggered.current = true;
          setRefsReady(prev => prev + 1);
        }
      } else {
        textareaRefs.current.delete(cellId);
      }
    };
  }, []);

  return {
    localTexts,
    setLocalTexts,
    composingCells,
    textareaRefs,
    refsReady,
    refsReadyTriggered,
    setRefsReady,
    handleTextChange,
    handleCompositionStart,
    handleCompositionEnd,
    handlePaste,
    handleKeyDown,
    createTextareaRef,
  };
}
