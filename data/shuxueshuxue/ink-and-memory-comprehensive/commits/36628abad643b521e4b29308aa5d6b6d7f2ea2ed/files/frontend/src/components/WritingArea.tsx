import { forwardRef } from 'react';
import BookPage from './BookPage';
import EditableTextArea, { type EditableTextAreaRef } from './EditableTextArea';
import type { VoiceTrigger } from '../extensions/VoiceHighlight';

interface WritingAreaProps {
  onChange: (text: string) => void;
  onContentChange?: (html: string) => void;
  triggers: VoiceTrigger[];
  onCursorChange?: (position: number) => void;
  onPhraseHover?: (phrase: string | null) => void;
  content?: string;
}

const WritingArea = forwardRef<EditableTextAreaRef, WritingAreaProps>(({ onChange, onContentChange, triggers, onCursorChange, onPhraseHover, content }, ref) => {
  return (
    <BookPage side="left">
      <EditableTextArea ref={ref} onChange={onChange} onContentChange={onContentChange} triggers={triggers} onCursorChange={onCursorChange} onPhraseHover={onPhraseHover} content={content} />
    </BookPage>
  );
});

WritingArea.displayName = 'WritingArea';

export default WritingArea;