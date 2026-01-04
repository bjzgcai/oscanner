import { ReactNode } from 'react';
import BookPage from './BookPage';

interface VoicesPanelProps {
  stackedCards: ReactNode;
  latestCard: ReactNode;
  stackedCount: number;
}

export default function VoicesPanel({ stackedCards, latestCard, stackedCount }: VoicesPanelProps) {
  return (
    <BookPage side="right">
      <div className="voices-container">
        {stackedCount > 0 && (
          <div className="voice-stack">
            {stackedCards}
          </div>
        )}
        <div className="latest-card-container">
          {latestCard}
        </div>
      </div>
    </BookPage>
  );
}