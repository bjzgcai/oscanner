import { useState, useEffect } from 'react';
import {
  listDecks,
  getDeck,
  createDeck,
  updateDeck,
  deleteDeck,
  forkDeck,
  createVoice,
  updateVoice,
  deleteVoice,
  forkVoice,
  type Deck,
  type Voice
} from '../api/voiceApi';
import {
  FaBrain, FaHeart, FaQuestion, FaCloud, FaTheaterMasks, FaEye,
  FaFistRaised, FaLightbulb, FaShieldAlt, FaWind, FaFire, FaCompass,
  FaChevronDown, FaChevronRight
} from 'react-icons/fa';

// @@@ Display mappings (text name → visual)
const COLORS = {
  'blue': { hex: '#4a90e2', label: 'Blue' },
  'purple': { hex: '#9b59b6', label: 'Purple' },
  'pink': { hex: '#e91e63', label: 'Pink' },
  'green': { hex: '#27ae60', label: 'Green' },
  'yellow': { hex: '#f39c12', label: 'Yellow' }
};

// @@@ Icon map with React Icons
const iconMap = {
  brain: FaBrain,
  heart: FaHeart,
  question: FaQuestion,
  cloud: FaCloud,
  masks: FaTheaterMasks,
  eye: FaEye,
  fist: FaFistRaised,
  lightbulb: FaLightbulb,
  shield: FaShieldAlt,
  wind: FaWind,
  fire: FaFire,
  compass: FaCompass,
};

// @@@ Icon labels for dropdown display
const ICON_LABELS = {
  'brain': '🧠 brain',
  'lightbulb': '💡 lightbulb',
  'masks': '🎭 masks',
  'cloud': '☁️ cloud',
  'shield': '🛡️ shield',
  'compass': '🧭 compass',
  'heart': '❤️ heart',
  'fist': '✊ fist',
  'fire': '🔥 fire',
  'wind': '💨 wind',
  'question': '❓ question',
  'eye': '👁️ eye'
};

interface Props {
  onUpdate?: () => void;
}

export default function DeckManager({ onUpdate }: Props) {
  const [decks, setDecks] = useState<Deck[]>([]);
  const [expandedDecks, setExpandedDecks] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingVoice, setEditingVoice] = useState<string | null>(null);

  useEffect(() => {
    loadDecks();
  }, []);

  async function loadDecks() {
    try {
      setLoading(true);
      const fetchedDecks = await listDecks();

      // Load voices for each deck
      const decksWithVoices = await Promise.all(
        fetchedDecks.map(async (deck) => {
          try {
            return await getDeck(deck.id);
          } catch (err) {
            console.error(`Failed to load voices for deck ${deck.id}:`, err);
            return deck;
          }
        })
      );

      setDecks(decksWithVoices);
      setError(null);
    } catch (err: any) {
      console.error('Failed to load decks:', err);
      setError(err.message || 'Failed to load decks');
    } finally {
      setLoading(false);
    }
  }

  function toggleDeck(deckId: string) {
    setExpandedDecks(prev => {
      const next = new Set(prev);
      if (next.has(deckId)) {
        next.delete(deckId);
      } else {
        next.add(deckId);
      }
      return next;
    });
  }

  async function handleForkDeck(deckId: string) {
    try {
      await forkDeck(deckId);
      await loadDecks();
      onUpdate?.();
    } catch (err: any) {
      alert(`Failed to fork deck: ${err.message}`);
    }
  }

  async function handleDeleteDeck(deckId: string) {
    if (!confirm('Delete this deck and all its voices?')) return;

    try {
      await deleteDeck(deckId);
      await loadDecks();
      onUpdate?.();
    } catch (err: any) {
      alert(`Failed to delete deck: ${err.message}`);
    }
  }

  async function handleUpdateVoice(voiceId: string, data: Partial<Voice>) {
    try {
      await updateVoice(voiceId, data);
      await loadDecks();
      setEditingVoice(null);
      onUpdate?.();
    } catch (err: any) {
      alert(`Failed to update voice: ${err.message}`);
    }
  }

  async function handleDeleteVoice(voiceId: string) {
    if (!confirm('Delete this voice?')) return;

    try {
      await deleteVoice(voiceId);
      await loadDecks();
      onUpdate?.();
    } catch (err: any) {
      alert(`Failed to delete voice: ${err.message}`);
    }
  }

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        background: '#f8f0e6'
      }}>
        <div style={{ fontSize: 18, color: '#666' }}>Loading decks...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        background: '#f8f0e6',
        gap: 16
      }}>
        <div style={{ fontSize: 18, color: '#e74c3c' }}>❌ {error}</div>
        <button
          onClick={loadDecks}
          style={{
            padding: '8px 16px',
            background: '#2c2c2c',
            color: '#fff',
            border: 'none',
            borderRadius: 6,
            cursor: 'pointer'
          }}
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: '#f8f0e6', overflow: 'hidden' }}>
      {/* Fixed Header */}
      <div style={{
        padding: '24px 32px',
        background: '#f8f0e6',
        flexShrink: 0,
        borderBottom: '2px solid #d0c4b0'
      }}>
        <h1 style={{
          margin: 0,
          fontSize: 28,
          fontWeight: 700,
          color: '#2c2c2c',
          fontFamily: 'Georgia, serif',
          letterSpacing: '-0.5px'
        }}>
          Voice Decks
        </h1>
        <p style={{
          margin: '6px 0 0',
          fontSize: 14,
          color: '#666',
          fontStyle: 'italic'
        }}>
          Organize your inner voices into thematic collections
        </p>
      </div>

      {/* Scrollable Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '32px' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 24 }}>
          {decks.map(deck => {
            const isExpanded = expandedDecks.has(deck.id);
            const isSystem = deck.is_system;
            const Icon = iconMap[deck.icon as keyof typeof iconMap] || FaBrain;
            const colorHex = COLORS[deck.color as keyof typeof COLORS]?.hex || '#4a90e2';

            return (
              <div
                key={deck.id}
                style={{
                  background: '#fff',
                  border: `2px solid ${isSystem ? '#d0c4b0' : colorHex}`,
                  borderRadius: 12,
                  overflow: 'hidden',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                  transition: 'all 0.3s'
                }}
              >
                {/* Deck Header */}
                <div
                  onClick={() => toggleDeck(deck.id)}
                  style={{
                    padding: 20,
                    background: isSystem ? '#f9f9f9' : '#fafafa',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 16,
                    transition: 'background 0.2s'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = isSystem ? '#f0f0f0' : '#f5f5f5';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = isSystem ? '#f9f9f9' : '#fafafa';
                  }}
                >
                  {/* Expand/Collapse Icon */}
                  <div style={{ fontSize: 20, color: '#666' }}>
                    {isExpanded ? <FaChevronDown /> : <FaChevronRight />}
                  </div>

                  {/* Deck Icon */}
                  <div style={{
                    width: 56,
                    height: 56,
                    borderRadius: 28,
                    background: `linear-gradient(135deg, ${colorHex} 0%, ${colorHex}cc 100%)`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#fff',
                    flexShrink: 0,
                    boxShadow: `0 3px 8px ${colorHex}40`
                  }}>
                    <Icon size={28} />
                  </div>

                  {/* Deck Info */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontSize: 20,
                      fontWeight: 700,
                      color: '#2c2c2c',
                      marginBottom: 4
                    }}>
                      {deck.name}
                      {isSystem && (
                        <span style={{
                          marginLeft: 12,
                          fontSize: 12,
                          fontWeight: 500,
                          color: '#888',
                          background: '#e0e0e0',
                          padding: '2px 8px',
                          borderRadius: 4
                        }}>
                          System
                        </span>
                      )}
                    </div>
                    <div style={{
                      fontSize: 14,
                      color: '#666'
                    }}>
                      {deck.description || 'No description'}
                    </div>
                    <div style={{
                      fontSize: 12,
                      color: '#999',
                      marginTop: 4
                    }}>
                      {deck.voice_count || deck.voices?.length || 0} voices
                    </div>
                  </div>

                  {/* Actions */}
                  <div style={{ display: 'flex', gap: 8 }} onClick={(e) => e.stopPropagation()}>
                    {isSystem ? (
                      <button
                        onClick={() => handleForkDeck(deck.id)}
                        style={{
                          padding: '8px 16px',
                          background: colorHex,
                          color: '#fff',
                          border: 'none',
                          borderRadius: 6,
                          cursor: 'pointer',
                          fontSize: 13,
                          fontWeight: 600,
                          transition: 'all 0.2s'
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.transform = 'translateY(-1px)';
                          e.currentTarget.style.boxShadow = `0 4px 12px ${colorHex}60`;
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.transform = 'translateY(0)';
                          e.currentTarget.style.boxShadow = 'none';
                        }}
                      >
                        Fork to My Collection
                      </button>
                    ) : (
                      <button
                        onClick={() => handleDeleteDeck(deck.id)}
                        style={{
                          padding: '8px 16px',
                          background: '#e74c3c',
                          color: '#fff',
                          border: 'none',
                          borderRadius: 6,
                          cursor: 'pointer',
                          fontSize: 13,
                          fontWeight: 600,
                          transition: 'all 0.2s'
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.transform = 'translateY(-1px)';
                          e.currentTarget.style.boxShadow = '0 4px 12px rgba(231, 76, 60, 0.4)';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.transform = 'translateY(0)';
                          e.currentTarget.style.boxShadow = 'none';
                        }}
                      >
                        Delete Deck
                      </button>
                    )}
                  </div>
                </div>

                {/* Voices List (Expanded) */}
                {isExpanded && deck.voices && deck.voices.length > 0 && (
                  <div style={{ padding: 20, background: '#fafafa' }}>
                    <div style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
                      gap: 16
                    }}>
                      {deck.voices.map(voice => {
                        const VoiceIcon = iconMap[voice.icon as keyof typeof iconMap] || FaBrain;
                        const voiceColor = COLORS[voice.color as keyof typeof COLORS]?.hex || '#4a90e2';
                        const isEditing = editingVoice === voice.id;

                        return (
                          <div
                            key={voice.id}
                            style={{
                              background: '#fff',
                              border: `2px solid ${voice.enabled ? voiceColor : '#ddd'}`,
                              borderRadius: 8,
                              padding: 16,
                              position: 'relative',
                              boxShadow: '0 2px 6px rgba(0,0,0,0.08)',
                              transition: 'all 0.2s',
                              opacity: voice.enabled ? 1 : 0.6
                            }}
                          >
                            {/* Voice Header */}
                            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
                              <div style={{
                                width: 40,
                                height: 40,
                                borderRadius: 20,
                                background: `linear-gradient(135deg, ${voiceColor} 0%, ${voiceColor}cc 100%)`,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                color: '#fff',
                                flexShrink: 0
                              }}>
                                <VoiceIcon size={20} />
                              </div>

                              <div style={{ flex: 1, minWidth: 0 }}>
                                <div style={{
                                  fontSize: 16,
                                  fontWeight: 600,
                                  color: '#2c2c2c',
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                  whiteSpace: 'nowrap'
                                }}>
                                  {voice.name}
                                </div>
                              </div>

                              {!isSystem && (
                                <button
                                  onClick={() => handleDeleteVoice(voice.id)}
                                  style={{
                                    background: 'rgba(255, 255, 255, 0.9)',
                                    border: '1px solid #ddd',
                                    borderRadius: 4,
                                    width: 24,
                                    height: 24,
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    cursor: 'pointer',
                                    fontSize: 12,
                                    transition: 'all 0.2s'
                                  }}
                                  onMouseEnter={(e) => {
                                    e.currentTarget.style.background = '#fee';
                                    e.currentTarget.style.borderColor = '#fcc';
                                  }}
                                  onMouseLeave={(e) => {
                                    e.currentTarget.style.background = 'rgba(255, 255, 255, 0.9)';
                                    e.currentTarget.style.borderColor = '#ddd';
                                  }}
                                  title="Delete"
                                >
                                  ×
                                </button>
                              )}
                            </div>

                            {/* Voice Prompt */}
                            <div style={{
                              fontSize: 12,
                              color: '#666',
                              lineHeight: 1.6,
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              display: '-webkit-box',
                              WebkitLineClamp: 3,
                              WebkitBoxOrient: 'vertical'
                            }}>
                              {voice.system_prompt}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Empty State */}
                {isExpanded && (!deck.voices || deck.voices.length === 0) && (
                  <div style={{
                    padding: 32,
                    textAlign: 'center',
                    color: '#999',
                    fontStyle: 'italic'
                  }}>
                    No voices in this deck yet
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
