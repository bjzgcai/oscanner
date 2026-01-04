import { ReactNode } from 'react';
import BookPage from './BookPage';

interface VoicesPanelProps {
  stackedCards: ReactNode;
  latestCard: ReactNode;
  stackedCount: number;
}

export default function VoicesPanel({ stackedCards, latestCard, stackedCount }: VoicesPanelProps) {
  // Calculate minimum height needed: base card height + offsets
  // Assume ~100px per card, plus 55% offsets
  const stackHeightPx = stackedCount > 0 ? 100 + (stackedCount - 1) * 55 : 0;

  return (
    <BookPage side="right">
      <div className="voices-container">
        {stackedCount > 0 && (
          <div className="voice-stack" style={{ minHeight: `${stackHeightPx}px` }}>
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