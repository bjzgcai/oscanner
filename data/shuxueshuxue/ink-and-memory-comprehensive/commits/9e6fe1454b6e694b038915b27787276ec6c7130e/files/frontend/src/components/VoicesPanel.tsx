import { ReactNode } from 'react';
import BookPage from './BookPage';

interface VoicesPanelProps {
  stackedCards: ReactNode;
  latestCard: ReactNode;
}

export default function VoicesPanel({ stackedCards, latestCard }: VoicesPanelProps) {
  return (
    <BookPage side="right">
      <div className="voices-container">
        <div className="voice-stack">
          {stackedCards}
        </div>
        <div className="latest-card-container">
          {latestCard}
        </div>
      </div>
    </BookPage>
  );
}