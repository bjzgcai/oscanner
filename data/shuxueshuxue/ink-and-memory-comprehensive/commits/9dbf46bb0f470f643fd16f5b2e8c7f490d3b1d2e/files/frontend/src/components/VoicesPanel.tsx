import { ReactNode } from 'react';
import BookPage from './BookPage';

interface VoicesPanelProps {
  children: ReactNode;
}

export default function VoicesPanel({ children }: VoicesPanelProps) {
  return (
    <BookPage side="right">
      <div className="voice-stack">
        {children}
      </div>
    </BookPage>
  );
}