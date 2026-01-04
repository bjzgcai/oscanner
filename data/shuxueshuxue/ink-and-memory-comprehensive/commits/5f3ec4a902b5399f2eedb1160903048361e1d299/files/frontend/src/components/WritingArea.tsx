import BookPage from './BookPage';
import EditableTextArea from './EditableTextArea';
import type { VoiceTrigger } from '../extensions/VoiceHighlight';

interface WritingAreaProps {
  onChange: (text: string) => void;
  triggers: VoiceTrigger[];
  onCursorChange?: (position: number) => void;
}

export default function WritingArea({ onChange, triggers, onCursorChange }: WritingAreaProps) {
  return (
    <BookPage side="left">
      <EditableTextArea onChange={onChange} triggers={triggers} onCursorChange={onCursorChange} />
    </BookPage>
  );
}