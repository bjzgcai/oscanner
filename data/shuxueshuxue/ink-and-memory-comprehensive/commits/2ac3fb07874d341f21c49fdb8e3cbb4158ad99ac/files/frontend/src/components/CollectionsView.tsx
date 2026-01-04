import { useState, useEffect } from 'react';
import type { Commentor } from '../engine/EditorEngine';

export default function CollectionsView() {
  const [currentPage, setCurrentPage] = useState(0);

  const pages = [
    { id: 0, name: 'Starred Comments' },
    { id: 1, name: 'Daily Pictures' }
  ];

  return (
    <div style={{
      width: '100%',
      height: '100%',
      display: 'flex',
      fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
      paddingTop: '2rem'
    }}>
      {/* Left sidebar - Page tabs */}
      <div style={{
        width: 200,
        background: 'transparent',
        alignSelf: 'stretch',
        paddingTop: '1rem',
        borderRight: '1px solid #d0c4b0'
      }}>
        {pages.map(page => (
          <div
            key={page.id}
            onClick={() => setCurrentPage(page.id)}
            style={{
              padding: '0.75rem 1.5rem',
              cursor: 'pointer',
              background: currentPage === page.id ? 'rgba(44, 44, 44, 0.05)' : 'transparent',
              borderLeft: currentPage === page.id ? '3px solid #333' : '3px solid transparent',
              fontWeight: currentPage === page.id ? 600 : 400,
              color: currentPage === page.id ? '#333' : '#888',
              transition: 'all 0.2s',
              fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
              fontSize: 14
            }}
            onMouseEnter={e => {
              if (currentPage !== page.id) {
                e.currentTarget.style.color = '#555';
                e.currentTarget.style.background = 'rgba(44, 44, 44, 0.03)';
              }
            }}
            onMouseLeave={e => {
              if (currentPage !== page.id) {
                e.currentTarget.style.color = '#888';
                e.currentTarget.style.background = 'transparent';
              }
            }}
          >
            {page.name}
          </div>
        ))}
      </div>

      {/* Right content area */}
      <div style={{
        flex: 1,
        padding: '2rem',
        overflowY: 'auto',
        background: '#f8f0e6'
      }}>
        {currentPage === 0 && <StarredCommentsPage />}
        {currentPage === 1 && <DailyPicturesPage />}
      </div>
    </div>
  );
}

// @@@ Starred Comments Page
function StarredCommentsPage() {
  const [starredComments, setStarredComments] = useState<Commentor[]>([]);

  useEffect(() => {
    // Load starred comments from localStorage
    const savedState = localStorage.getItem('ink_memory_state');
    if (savedState) {
      try {
        const state = JSON.parse(savedState);
        const starred = state.commentors?.filter((c: Commentor) => c.feedback === 'star') || [];
        setStarredComments(starred);
      } catch (e) {
        console.error('Failed to load starred comments:', e);
      }
    }
  }, []);

  if (starredComments.length === 0) {
    return (
      <div style={{
        textAlign: 'center',
        padding: '4rem 2rem',
        color: '#999'
      }}>
        <div style={{ fontSize: '48px', marginBottom: '1rem' }}>⭐</div>
        <div style={{ fontSize: '18px', marginBottom: '0.5rem' }}>No starred comments yet</div>
        <div style={{ fontSize: '14px' }}>Star comments in your writing to collect them here</div>
      </div>
    );
  }

  return (
    <div style={{
      maxWidth: '800px',
      margin: '0 auto'
    }}>
      <h2 style={{
        fontSize: '24px',
        fontWeight: 600,
        color: '#333',
        marginBottom: '1.5rem',
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem'
      }}>
        <span>⭐</span>
        <span>Starred Comments</span>
        <span style={{ fontSize: '14px', fontWeight: 400, color: '#999' }}>
          ({starredComments.length})
        </span>
      </h2>

      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '1rem'
      }}>
        {starredComments.map((comment) => (
          <div
            key={comment.id}
            style={{
              background: '#fff',
              border: '1px solid #d0c4b0',
              borderRadius: '8px',
              padding: '1.5rem',
              boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
              transition: 'all 0.2s'
            }}
            onMouseEnter={e => {
              e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
            }}
            onMouseLeave={e => {
              e.currentTarget.style.boxShadow = '0 2px 4px rgba(0,0,0,0.05)';
            }}
          >
            {/* Header */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
              marginBottom: '0.75rem',
              paddingBottom: '0.75rem',
              borderBottom: '1px solid #f0f0f0'
            }}>
              <div style={{
                fontSize: '20px'
              }}>
                {getIconForVoice(comment.icon)}
              </div>
              <div style={{
                flex: 1,
                fontSize: '16px',
                fontWeight: 600,
                color: '#333'
              }}>
                {comment.voice}
              </div>
              <div style={{
                fontSize: '12px',
                color: '#999'
              }}>
                {new Date(comment.appliedAt || comment.computedAt).toLocaleDateString()}
              </div>
            </div>

            {/* Phrase */}
            <div style={{
              padding: '0.75rem',
              background: '#f8f0e6',
              borderLeft: '3px solid #d0c4b0',
              marginBottom: '0.75rem',
              fontSize: '14px',
              fontStyle: 'italic',
              color: '#666'
            }}>
              "{comment.phrase}"
            </div>

            {/* Comment */}
            <div style={{
              fontSize: '15px',
              lineHeight: '1.6',
              color: '#333'
            }}>
              {comment.comment}
            </div>

            {/* Chat history preview if exists */}
            {comment.chatHistory && comment.chatHistory.length > 1 && (
              <div style={{
                marginTop: '0.75rem',
                paddingTop: '0.75rem',
                borderTop: '1px solid #f0f0f0',
                fontSize: '13px',
                color: '#999'
              }}>
                💬 {comment.chatHistory.length - 1} conversation{comment.chatHistory.length - 1 === 1 ? '' : 's'}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// @@@ Daily Pictures Page (Placeholder)
function DailyPicturesPage() {
  return (
    <div style={{
      maxWidth: '1000px',
      margin: '0 auto'
    }}>
      <h2 style={{
        fontSize: '24px',
        fontWeight: 600,
        color: '#333',
        marginBottom: '1.5rem',
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem'
      }}>
        <span>📷</span>
        <span>Daily Pictures</span>
      </h2>

      {/* Placeholder gallery grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
        gap: '1rem'
      }}>
        {[1, 2, 3, 4, 5, 6].map(i => (
          <div
            key={i}
            style={{
              aspectRatio: '1',
              background: 'linear-gradient(135deg, #f8f0e6 0%, #e8e0d6 100%)',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: '2px dashed #d0c4b0',
              fontSize: '48px',
              cursor: 'pointer',
              transition: 'all 0.2s'
            }}
            onMouseEnter={e => {
              e.currentTarget.style.transform = 'scale(1.05)';
              e.currentTarget.style.borderStyle = 'solid';
            }}
            onMouseLeave={e => {
              e.currentTarget.style.transform = 'scale(1)';
              e.currentTarget.style.borderStyle = 'dashed';
            }}
          >
            📷
          </div>
        ))}
      </div>

      <div style={{
        textAlign: 'center',
        padding: '3rem 2rem',
        color: '#999',
        fontSize: '14px'
      }}>
        This feature will allow you to save daily snapshots and memories
      </div>
    </div>
  );
}

// @@@ Helper to get icon emoji
function getIconForVoice(icon: string): string {
  const iconMap: Record<string, string> = {
    brain: '🧠',
    heart: '❤️',
    question: '❓',
    cloud: '☁️',
    masks: '🎭',
    eye: '👁️',
    fist: '✊',
    lightbulb: '💡',
    shield: '🛡️',
    wind: '💨',
    fire: '🔥',
    compass: '🧭'
  };
  return iconMap[icon] || '💭';
}
