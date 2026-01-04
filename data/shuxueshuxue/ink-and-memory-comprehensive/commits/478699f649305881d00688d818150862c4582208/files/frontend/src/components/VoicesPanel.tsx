import { type ReactNode, useRef, useEffect } from 'react';
import BookPage from './BookPage';

interface VoicesPanelProps {
  children: ReactNode;
  focusedVoiceIndex?: number;
}

export default function VoicesPanel({ children, focusedVoiceIndex }: VoicesPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  // @@@ Auto-scroll to focused comment with margin
  useEffect(() => {
    if (focusedVoiceIndex !== undefined && panelRef.current) {
      const comments = panelRef.current.querySelectorAll('.voice-comment');
      const targetComment = comments[focusedVoiceIndex] as HTMLElement;

      if (targetComment) {
        targetComment.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [focusedVoiceIndex]);

  return (
    <BookPage side="right" ref={panelRef}>
      {children}
    </BookPage>
  );
}