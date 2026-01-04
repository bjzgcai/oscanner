import { useState, useEffect, useRef } from 'react';
import {
  listDecks,
  getDeck,
  createDeck,
  updateDeck,
  deleteDeck,
  forkDeck,
  syncDeck,
  createVoice,
  updateVoice,
  deleteVoice,
  forkVoice,
  publishDeck,
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
  const [communityDecks, setCommunityDecks] = useState<Deck[]>([]);
  const [expandedDecks, setExpandedDecks] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingVoice, setEditingVoice] = useState<string | null>(null);
  const [editingField, setEditingField] = useState<'name' | 'prompt' | null>(null);
  const [creatingDeck, setCreatingDeck] = useState(false);
  const [creatingVoice, setCreatingVoice] = useState<string | null>(null);
  const [publishWarning, setPublishWarning] = useState<string | null>(null);

  // @@@ Scroll position preservation
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadDecks();
    loadCommunityDecks();
  }, []);

  async function loadDecks(preserveScroll = false) {
    // @@@ Save scroll position before reload
    const savedScrollTop = preserveScroll && scrollContainerRef.current
      ? scrollContainerRef.current.scrollTop
      : 0;

    try {
      if (!preserveScroll) {
        setLoading(true);
      }
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

      // @@@ Restore scroll position after render
      if (preserveScroll && scrollContainerRef.current) {
        setTimeout(() => {
          if (scrollContainerRef.current) {
            scrollContainerRef.current.scrollTop = savedScrollTop;
          }
        }, 0);
      }
    } catch (err: any) {
      console.error('Failed to load decks:', err);
      setError(err.message || 'Failed to load decks');
    } finally {
      if (!preserveScroll) {
        setLoading(false);
      }
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
      await loadDecks(true);
      onUpdate?.();
    } catch (err: any) {
      alert(`Failed to fork deck: ${err.message}`);
    }
  }

  async function handleToggleDeck(deckId: string, currentEnabled: boolean) {
    try {
      await updateDeck(deckId, { enabled: !currentEnabled });
      await loadDecks(true);
      onUpdate?.();
    } catch (err: any) {
      alert(`Failed to toggle deck: ${err.message}`);
    }
  }

  async function handleDeleteDeck(deckId: string) {
    if (!confirm('Delete this deck and all its voices?')) return;

    try {
      await deleteDeck(deckId);
      await loadDecks(true);
      onUpdate?.();
    } catch (err: any) {
      alert(`Failed to delete deck: ${err.message}`);
    }
  }

  async function handleSyncDeck(deckId: string) {
    if (!confirm('Sync with original template? This will overwrite any changes you made to this deck.')) return;

    try {
      const result = await syncDeck(deckId);
      alert(`✅ Synced ${result.synced_voices} voices with original template`);
      await loadDecks(true);
      onUpdate?.();
    } catch (err: any) {
      alert(`Failed to sync deck: ${err.message}`);
    }
  }

  async function handleToggleVoice(voiceId: string, currentEnabled: boolean) {
    try {
      await updateVoice(voiceId, { enabled: !currentEnabled });
      await loadDecks(true);
      onUpdate?.();
    } catch (err: any) {
      alert(`Failed to toggle voice: ${err.message}`);
    }
  }

  async function handleUpdateVoice(voiceId: string, data: Partial<Voice>) {
    try {
      await updateVoice(voiceId, data);
      await loadDecks(true);
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
      await loadDecks(true);
      onUpdate?.();
    } catch (err: any) {
      alert(`Failed to delete voice: ${err.message}`);
    }
  }

  async function loadCommunityDecks() {
    try {
      const published = await listDecks(true);
      setCommunityDecks(published);
    } catch (err: any) {
      console.error('Failed to load community decks:', err);
    }
  }

  async function handleCreateDeck() {
    setCreatingDeck(true);
    try {
      const newDeck = await createDeck({
        name: 'New Deck',
        description: 'Describe your deck here',
        icon: 'brain',
        color: 'blue'
      });
      await loadDecks(true);
      setExpandedDecks(prev => new Set([...prev, newDeck.id]));
      onUpdate?.();
    } catch (err: any) {
      alert(`Failed to create deck: ${err.message}`);
    } finally {
      setCreatingDeck(false);
    }
  }

  async function handleAddVoice(deckId: string) {
    setCreatingVoice(deckId);
    try {
      await createVoice({
        deck_id: deckId,
        name: 'New Voice',
        system_prompt: 'You are a helpful assistant.',
        icon: 'brain',
        color: 'blue'
      });
      await loadDecks(true);
      onUpdate?.();
    } catch (err: any) {
      alert(`Failed to create voice: ${err.message}`);
    } finally {
      setCreatingVoice(null);
    }
  }

  async function handlePublishClick(deck: Deck) {
    if (deck.published) {
      handlePublishToggle(deck.id, false);
    } else {
      setPublishWarning(deck.id);
    }
  }

  async function handlePublishToggle(deckId: string, shouldPublish: boolean) {
    try {
      const result = await publishDeck(deckId);
      alert(result.published ? '✅ Deck published to community!' : '✅ Deck unpublished');
      await loadDecks(true);
      await loadCommunityDecks();
      onUpdate?.();
    } catch (err: any) {
      alert(`Failed: ${err.message}`);
    } finally {
      setPublishWarning(null);
    }
  }

  async function handleInstallDeck(deckId: string) {
    try {
      await forkDeck(deckId);
      alert('✅ Deck installed to your collection!');
      await loadDecks(true);
      await loadCommunityDecks();
      onUpdate?.();
    } catch (err: any) {
      alert(`Failed to install deck: ${err.message}`);
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
      <div ref={scrollContainerRef} style={{ flex: 1, overflowY: 'auto', padding: '32px' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 24 }}>
          {/* Create New Deck Button */}
          <button
            onClick={handleCreateDeck}
            disabled={creatingDeck}
            style={{
              padding: '12px 24px',
              marginBottom: '8px',
              background: '#4a90e2',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              cursor: creatingDeck ? 'not-allowed' : 'pointer',
              fontSize: '14px',
              fontWeight: '500',
              opacity: creatingDeck ? 0.6 : 1,
              transition: 'all 0.2s ease',
              alignSelf: 'flex-start'
            }}
            onMouseEnter={(e) => {
              if (!creatingDeck) e.currentTarget.style.background = '#357abd';
            }}
            onMouseLeave={(e) => {
              if (!creatingDeck) e.currentTarget.style.background = '#4a90e2';
            }}
          >
            {creatingDeck ? 'Creating...' : '+ Create New Deck'}
          </button>

          {/* My Decks Section Header */}
          <h3 style={{
            margin: '8px 0',
            fontSize: '16px',
            fontWeight: '500',
            color: '#2c2c2c'
          }}>
            My Decks
          </h3>

          {/* User's Decks */}
          {decks.map(deck => {
            const isExpanded = expandedDecks.has(deck.id);
            const isSystem = !!deck.is_system; // @@@ Convert to boolean to prevent React from rendering "0"
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
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }} onClick={(e) => e.stopPropagation()}>
                    {/* @@@ Deck-level toggle switch */}
                    <div
                      onClick={() => handleToggleDeck(deck.id, deck.enabled)}
                      style={{
                        width: 50,
                        height: 26,
                        borderRadius: 13,
                        background: deck.enabled ? colorHex : '#ccc',
                        position: 'relative',
                        cursor: 'pointer',
                        transition: 'background 0.3s',
                        flexShrink: 0
                      }}
                      title={deck.enabled ? 'Disable deck' : 'Enable deck'}
                    >
                      <div style={{
                        position: 'absolute',
                        top: 3,
                        left: deck.enabled ? 26 : 3,
                        width: 20,
                        height: 20,
                        borderRadius: 10,
                        background: '#fff',
                        transition: 'left 0.3s',
                        boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
                      }} />
                    </div>

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
                      <>
                        {/* @@@ Show sync button if deck has a parent */}
                        {deck.parent_id && (
                          <button
                            onClick={() => handleSyncDeck(deck.id)}
                            style={{
                              padding: '8px 16px',
                              background: '#3498db',
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
                              e.currentTarget.style.boxShadow = '0 4px 12px rgba(52, 152, 219, 0.4)';
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.transform = 'translateY(0)';
                              e.currentTarget.style.boxShadow = 'none';
                            }}
                          >
                            Sync with Original
                          </button>
                        )}
                        {/* @@@ Publish button for user-owned decks */}
                        <button
                          onClick={() => handlePublishClick(deck)}
                          style={{
                            padding: '8px 16px',
                            background: deck.published ? '#e74c3c' : '#9b59b6',
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
                            const color = deck.published ? 'rgba(231, 76, 60, 0.4)' : 'rgba(155, 89, 182, 0.4)';
                            e.currentTarget.style.boxShadow = `0 4px 12px ${color}`;
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.transform = 'translateY(0)';
                            e.currentTarget.style.boxShadow = 'none';
                          }}
                        >
                          {deck.published ? 'Unpublish' : 'Publish to Community'}
                        </button>
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
                      </>
                    )}
                  </div>
                </div>

                {/* Voices List (Expanded) */}
                {isExpanded && (
                  <div style={{ padding: 20, background: '#fafafa' }}>
                    {deck.voices && deck.voices.length > 0 && (
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
                                {/* @@@ Inline editing for voice name */}
                                {!isEditing || editingField !== 'name' ? (
                                  <div
                                    onClick={() => {
                                      if (!isSystem) {
                                        setEditingVoice(voice.id);
                                        setEditingField('name');
                                      }
                                    }}
                                    style={{
                                      fontSize: 16,
                                      fontWeight: 600,
                                      color: '#2c2c2c',
                                      overflow: 'hidden',
                                      textOverflow: 'ellipsis',
                                      whiteSpace: 'nowrap',
                                      cursor: isSystem ? 'default' : 'pointer',
                                      transition: 'opacity 0.2s'
                                    }}
                                    onMouseEnter={(e) => {
                                      if (!isSystem) e.currentTarget.style.opacity = '0.7';
                                    }}
                                    onMouseLeave={(e) => {
                                      if (!isSystem) e.currentTarget.style.opacity = '1';
                                    }}
                                  >
                                    {voice.name}
                                  </div>
                                ) : (
                                  <input
                                    autoFocus
                                    defaultValue={voice.name}
                                    onBlur={(e) => {
                                      handleUpdateVoice(voice.id, { name: e.target.value });
                                      setEditingVoice(null);
                                      setEditingField(null);
                                    }}
                                    onKeyDown={(e) => {
                                      if (e.key === 'Enter') {
                                        e.currentTarget.blur();
                                      } else if (e.key === 'Escape') {
                                        setEditingVoice(null);
                                        setEditingField(null);
                                      }
                                    }}
                                    style={{
                                      width: '100%',
                                      fontSize: 16,
                                      fontWeight: 600,
                                      color: '#2c2c2c',
                                      padding: '4px 8px',
                                      border: '2px solid #4a90e2',
                                      borderRadius: 4,
                                      background: '#f0f8ff'
                                    }}
                                  />
                                )}
                              </div>

                              {/* @@@ Voice-level toggle switch */}
                              <div
                                onClick={() => handleToggleVoice(voice.id, voice.enabled)}
                                style={{
                                  width: 40,
                                  height: 22,
                                  borderRadius: 11,
                                  background: voice.enabled ? voiceColor : '#ccc',
                                  position: 'relative',
                                  cursor: 'pointer',
                                  transition: 'background 0.3s',
                                  flexShrink: 0
                                }}
                                title={voice.enabled ? 'Disable voice' : 'Enable voice'}
                              >
                                <div style={{
                                  position: 'absolute',
                                  top: 3,
                                  left: voice.enabled ? 21 : 3,
                                  width: 16,
                                  height: 16,
                                  borderRadius: 8,
                                  background: '#fff',
                                  transition: 'left 0.3s',
                                  boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
                                }} />
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

                            {/* Voice Prompt with inline editing */}
                            {!isEditing || editingField !== 'prompt' ? (
                              <div
                                onClick={() => {
                                  if (!isSystem) {
                                    setEditingVoice(voice.id);
                                    setEditingField('prompt');
                                  }
                                }}
                                style={{
                                  fontSize: 12,
                                  color: '#666',
                                  lineHeight: 1.6,
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                  display: '-webkit-box',
                                  WebkitLineClamp: 3,
                                  WebkitBoxOrient: 'vertical',
                                  cursor: isSystem ? 'default' : 'pointer',
                                  transition: 'opacity 0.2s'
                                }}
                                onMouseEnter={(e) => {
                                  if (!isSystem) e.currentTarget.style.opacity = '0.7';
                                }}
                                onMouseLeave={(e) => {
                                  if (!isSystem) e.currentTarget.style.opacity = '1';
                                }}
                              >
                                {voice.system_prompt}
                              </div>
                            ) : (
                              <>
                                <textarea
                                  autoFocus
                                  defaultValue={voice.system_prompt}
                                  onBlur={(e) => {
                                    handleUpdateVoice(voice.id, { system_prompt: e.target.value });
                                    setEditingVoice(null);
                                    setEditingField(null);
                                  }}
                                  onKeyDown={(e) => {
                                    if (e.key === 'Escape') {
                                      setEditingVoice(null);
                                      setEditingField(null);
                                    }
                                  }}
                                  style={{
                                    width: '100%',
                                    minHeight: '100px',
                                    fontSize: 12,
                                    color: '#2c2c2c',
                                    padding: '8px',
                                    border: '2px solid #4a90e2',
                                    borderRadius: 4,
                                    background: '#f0f8ff',
                                    fontFamily: 'inherit',
                                    lineHeight: 1.6,
                                    resize: 'vertical',
                                    boxSizing: 'border-box'
                                  }}
                                />
                                <div style={{
                                  fontSize: 11,
                                  color: '#999',
                                  marginTop: 4
                                }}>
                                  {voice.system_prompt.length} chars · Press Esc to cancel
                                </div>
                              </>
                            )}
                          </div>
                        );
                        })}
                      </div>
                    )}

                    {/* @@@ Add Voice button */}
                    {!isSystem && (
                      <button
                        onClick={() => handleAddVoice(deck.id)}
                        disabled={creatingVoice === deck.id}
                        style={{
                          padding: '8px 16px',
                          marginTop: '16px',
                          background: 'transparent',
                          color: '#4a90e2',
                          border: '1px dashed #4a90e2',
                          borderRadius: '4px',
                          cursor: creatingVoice === deck.id ? 'not-allowed' : 'pointer',
                          fontSize: '12px',
                          opacity: creatingVoice === deck.id ? 0.6 : 1,
                          transition: 'all 0.2s',
                          alignSelf: 'flex-start'
                        }}
                        onMouseEnter={(e) => {
                          if (creatingVoice !== deck.id) {
                            e.currentTarget.style.background = '#f0f8ff';
                          }
                        }}
                        onMouseLeave={(e) => {
                          if (creatingVoice !== deck.id) {
                            e.currentTarget.style.background = 'transparent';
                          }
                        }}
                      >
                        {creatingVoice === deck.id ? 'Adding...' : '+ Add Voice to this Deck'}
                      </button>
                    )}

                    {/* Empty State */}
                    {(!deck.voices || deck.voices.length === 0) && (
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
                )}
              </div>
            );
          })}

          {/* @@@ Community Decks Section */}
          <hr style={{ margin: '32px 0', border: '1px solid #d0c4b0' }} />

          <h3 style={{
            margin: '16px 0',
            fontSize: '16px',
            fontWeight: '500',
            color: '#2c2c2c'
          }}>
            Community Decks ({communityDecks.length})
          </h3>

          {communityDecks.length === 0 ? (
            <p style={{
              color: '#999',
              fontSize: '14px',
              fontStyle: 'italic',
              textAlign: 'center',
              padding: '32px 0'
            }}>
              No published decks yet. Be the first to share!
            </p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {communityDecks.map(deck => {
                const Icon = iconMap[deck.icon as keyof typeof iconMap] || FaBrain;
                const colorHex = COLORS[deck.color as keyof typeof COLORS]?.hex || '#4a90e2';

                return (
                  <div
                    key={deck.id}
                    style={{
                      background: '#fff',
                      border: `2px solid ${colorHex}`,
                      borderRadius: 12,
                      padding: 20,
                      boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                      transition: 'all 0.3s'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 16, flex: 1 }}>
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

                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{
                            fontSize: 18,
                            fontWeight: 700,
                            color: '#2c2c2c',
                            marginBottom: 4
                          }}>
                            {deck.name}
                          </div>
                          <div style={{
                            fontSize: 14,
                            color: '#666',
                            marginBottom: 4
                          }}>
                            {deck.description || 'No description'}
                          </div>
                          <div style={{
                            fontSize: 12,
                            color: '#999'
                          }}>
                            by {deck.author_name || 'Anonymous'} · {deck.voice_count || 0} voices · {deck.install_count || 0} installs
                          </div>
                        </div>
                      </div>

                      <button
                        onClick={() => handleInstallDeck(deck.id)}
                        style={{
                          padding: '8px 16px',
                          background: '#27ae60',
                          color: '#fff',
                          border: 'none',
                          borderRadius: 6,
                          fontSize: 13,
                          fontWeight: 600,
                          cursor: 'pointer',
                          transition: 'all 0.2s',
                          flexShrink: 0
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.transform = 'translateY(-1px)';
                          e.currentTarget.style.boxShadow = '0 4px 12px rgba(39, 174, 96, 0.4)';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.transform = 'translateY(0)';
                          e.currentTarget.style.boxShadow = 'none';
                        }}
                      >
                        Install
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* @@@ Publish Warning Modal */}
      {publishWarning && (
        <div
          className="modal-overlay"
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999
          }}
          onClick={() => setPublishWarning(null)}
        >
          <div
            className="modal-content"
            style={{
              background: 'white',
              padding: '24px',
              borderRadius: '8px',
              maxWidth: '400px',
              boxShadow: '0 4px 12px rgba(0,0,0,0.15)'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ marginBottom: '16px', fontSize: '18px', fontWeight: 600 }}>
              ⚠️ Publish Deck Warning
            </h3>

            <p style={{ marginBottom: '16px', lineHeight: '1.5', fontSize: '14px' }}>
              Publishing will <strong>break the parent link</strong>. This deck will become
              a standalone deck in the community store.
            </p>

            <p style={{ marginBottom: '16px', color: '#e74c3c', fontSize: '13px', lineHeight: '1.5' }}>
              This action cannot be undone. You can unpublish later, but the parent
              link will remain broken.
            </p>

            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setPublishWarning(null)}
                style={{
                  padding: '8px 16px',
                  background: '#ccc',
                  color: '#2c2c2c',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: 500
                }}
              >
                Cancel
              </button>
              <button
                onClick={() => handlePublishToggle(publishWarning, true)}
                style={{
                  padding: '8px 16px',
                  background: '#9b59b6',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: 500
                }}
              >
                Publish Anyway
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
