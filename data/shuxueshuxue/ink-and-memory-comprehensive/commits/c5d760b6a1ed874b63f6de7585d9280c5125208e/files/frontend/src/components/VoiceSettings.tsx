import { useState, useEffect, useRef } from 'react';
import type { VoiceConfig, StateConfig, UserState } from '../types/voice';
import { getVoices, saveVoices, clearVoices, getMetaPrompt, saveMetaPrompt, getStateConfig, saveStateConfig } from '../utils/voiceStorage';
import {
  FaBrain, FaHeart, FaQuestion, FaCloud, FaTheaterMasks, FaEye,
  FaFistRaised, FaLightbulb, FaShieldAlt, FaWind, FaFire, FaCompass
} from 'react-icons/fa';

// @@@ Display mappings (text name → visual)
const COLORS = {
  'blue': { hex: '#4a90e2', label: 'Blue' },
  'purple': { hex: '#9b59b6', label: 'Purple' },
  'pink': { hex: '#e91e63', label: 'Pink' },
  'green': { hex: '#27ae60', label: 'Green' },
  'yellow': { hex: '#f39c12', label: 'Yellow' }
};

// @@@ Icon map with React Icons (matching App.tsx)
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

// @@@ Icon labels for dropdown display (emoji for visual reference)
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
  defaultVoices: Record<string, VoiceConfig>;
  onSave: (voices: Record<string, VoiceConfig>) => void;
}

export default function VoiceSettings({ defaultVoices, onSave }: Props) {
  const [voices, setVoices] = useState<Record<string, VoiceConfig>>({});
  const [metaPrompt, setMetaPrompt] = useState<string>('');
  const [stateConfig, setStateConfig] = useState<StateConfig>(getStateConfig());
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saved'>('idle');
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // @@@ Sync with defaultVoices prop (handles async fetch + Use Default button)
  useEffect(() => {
    if (Object.keys(defaultVoices).length > 0) {
      const stored = getVoices();
      setVoices(stored || defaultVoices);
    }
  }, [defaultVoices]);

  // @@@ Load meta prompt from localStorage
  useEffect(() => {
    setMetaPrompt(getMetaPrompt());
  }, []);

  const handleSave = () => {
    saveVoices(voices);
    saveMetaPrompt(metaPrompt);
    saveStateConfig(stateConfig);
    onSave(voices);
    setSaveStatus('saved');
    setTimeout(() => setSaveStatus('idle'), 2000);
  };

  const handleDefault = () => {
    clearVoices();
    localStorage.removeItem('meta-prompt');
    localStorage.removeItem('state-config');
    // Deep copy to force React to re-render
    const freshDefaults = JSON.parse(JSON.stringify(defaultVoices));
    setVoices(freshDefaults);
    setMetaPrompt(getMetaPrompt());
    setStateConfig(getStateConfig());
    onSave(freshDefaults);
  };

  const handleAdd = () => {
    const newId = `voice_${Date.now()}`;
    setVoices({
      ...voices,
      [newId]: {
        name: 'New Voice',
        systemPrompt: 'Describe this voice...',
        enabled: true,
        icon: 'masks',
        color: 'blue'
      }
    });

    // Scroll to bottom after adding
    setTimeout(() => {
      if (scrollContainerRef.current) {
        scrollContainerRef.current.scrollTo({
          top: scrollContainerRef.current.scrollHeight,
          behavior: 'smooth'
        });
      }
    }, 100);
  };

  const handleDelete = (id: string) => {
    const { [id]: _, ...rest } = voices;
    setVoices(rest);
  };

  const handleRename = (id: string, newName: string) => {
    // Just update the name, keep the ID stable
    setVoices({ ...voices, [id]: { ...voices[id], name: newName } });
  };

  const handleUpdate = (id: string, field: keyof VoiceConfig, value: any) => {
    setVoices({ ...voices, [id]: { ...voices[id], [field]: value } });
  };

  const handleExport = () => {
    // @@@ Export voices, meta prompt, and state config
    const data = {
      voices,
      metaPrompt,
      stateConfig
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `voices-${Date.now()}.json`;
    a.click();
  };

  const handleImport = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (file) {
        file.text().then(text => {
          const imported = JSON.parse(text);
          // @@@ Support old format (just voices) and new format (voices + metaPrompt + stateConfig)
          const importedVoices = imported.voices || imported;
          const importedMetaPrompt = imported.metaPrompt || '';
          const importedStateConfig = imported.stateConfig || getStateConfig();
          setVoices(importedVoices);
          setMetaPrompt(importedMetaPrompt);
          setStateConfig(importedStateConfig);
          saveVoices(importedVoices);
          saveMetaPrompt(importedMetaPrompt);
          saveStateConfig(importedStateConfig);
          onSave(importedVoices);
        });
      }
    };
    input.click();
  };

  const handleAddState = () => {
    const newId = `state_${Date.now()}`;
    setStateConfig({
      ...stateConfig,
      states: {
        ...stateConfig.states,
        [newId]: { name: 'New State', prompt: '' }
      }
    });
  };

  const handleDeleteState = (id: string) => {
    const { [id]: _, ...rest } = stateConfig.states;
    setStateConfig({ ...stateConfig, states: rest });
  };

  const handleUpdateState = (id: string, field: keyof UserState, value: string) => {
    setStateConfig({
      ...stateConfig,
      states: {
        ...stateConfig.states,
        [id]: { ...stateConfig.states[id], [field]: value }
      }
    });
  };

  const [activeTab, setActiveTab] = useState<'voices' | 'meta' | 'states'>('voices');

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: '#f8f0e6', overflow: 'hidden' }}>
      {/* Fixed Header */}
      <div style={{
        padding: '24px 32px 0',
        background: '#f8f0e6',
        flexShrink: 0
      }}>
        {/* Title */}
        <div style={{ marginBottom: 20 }}>
          <h1 style={{
            margin: 0,
            fontSize: 28,
            fontWeight: 700,
            color: '#2c2c2c',
            fontFamily: 'Georgia, serif',
            letterSpacing: '-0.5px'
          }}>
            The Voice Council
          </h1>
          <p style={{
            margin: '6px 0 0',
            fontSize: 14,
            color: '#666',
            fontStyle: 'italic'
          }}>
            Configure your inner voices, the ones that comment on everything you write
          </p>
        </div>

        {/* Tabs */}
        <div style={{
          display: 'flex',
          gap: 8,
          borderBottom: '2px solid #d0c4b0'
        }}>
          {['voices', 'meta', 'states'].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab as any)}
              style={{
                padding: '12px 24px',
                border: 'none',
                background: activeTab === tab ? '#fff' : 'transparent',
                borderRadius: '8px 8px 0 0',
                cursor: 'pointer',
                fontSize: 14,
                fontWeight: activeTab === tab ? 600 : 400,
                color: activeTab === tab ? '#2c2c2c' : '#888',
                transition: 'all 0.2s',
                borderBottom: activeTab === tab ? '2px solid #2c2c2c' : 'none',
                marginBottom: '-2px'
              }}
              onMouseEnter={(e) => {
                if (activeTab !== tab) {
                  e.currentTarget.style.background = 'rgba(255, 255, 255, 0.5)';
                }
              }}
              onMouseLeave={(e) => {
                if (activeTab !== tab) {
                  e.currentTarget.style.background = 'transparent';
                }
              }}
            >
              {tab === 'voices' && '🎭 Voices'}
              {tab === 'meta' && '📜 Meta Prompt'}
              {tab === 'states' && '💭 User States'}
            </button>
          ))}

          {/* Action buttons on the right */}
          <div style={{ flex: 1 }} />
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end', paddingBottom: 8 }}>
            {activeTab === 'voices' && (
              <>
                <button onClick={handleAdd} style={{
                  padding: '6px 14px',
                  border: '1px solid #d0c4b0',
                  background: '#fff',
                  borderRadius: 6,
                  cursor: 'pointer',
                  fontSize: 12,
                  fontWeight: 500,
                  transition: 'all 0.2s',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.08)'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'translateY(-1px)';
                  e.currentTarget.style.boxShadow = '0 2px 6px rgba(0,0,0,0.12)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'translateY(0)';
                  e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.08)';
                }}
                >+ Add Voice</button>
                <button onClick={handleImport} style={{
                  padding: '6px 14px',
                  border: '1px solid #d0c4b0',
                  background: '#fff',
                  borderRadius: 6,
                  cursor: 'pointer',
                  fontSize: 12,
                  transition: 'all 0.2s',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.08)'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'translateY(-1px)';
                  e.currentTarget.style.boxShadow = '0 2px 6px rgba(0,0,0,0.12)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'translateY(0)';
                  e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.08)';
                }}
                >Import</button>
                <button onClick={handleExport} style={{
                  padding: '6px 14px',
                  border: '1px solid #d0c4b0',
                  background: '#fff',
                  borderRadius: 6,
                  cursor: 'pointer',
                  fontSize: 12,
                  transition: 'all 0.2s',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.08)'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'translateY(-1px)';
                  e.currentTarget.style.boxShadow = '0 2px 6px rgba(0,0,0,0.12)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'translateY(0)';
                  e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.08)';
                }}
                >Export</button>
                <button onClick={handleDefault} style={{
                  padding: '6px 14px',
                  border: '1px solid #d0c4b0',
                  background: '#fff',
                  borderRadius: 6,
                  cursor: 'pointer',
                  fontSize: 12,
                  transition: 'all 0.2s',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.08)'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'translateY(-1px)';
                  e.currentTarget.style.boxShadow = '0 2px 6px rgba(0,0,0,0.12)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'translateY(0)';
                  e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.08)';
                }}
                >Reset to Default</button>
              </>
            )}
            {activeTab === 'states' && (
              <button onClick={handleAddState} style={{
                padding: '6px 14px',
                border: '1px solid #d0c4b0',
                background: '#fff',
                borderRadius: 6,
                cursor: 'pointer',
                fontSize: 12,
                fontWeight: 500,
                transition: 'all 0.2s',
                boxShadow: '0 1px 3px rgba(0,0,0,0.08)'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'translateY(-1px)';
                e.currentTarget.style.boxShadow = '0 2px 6px rgba(0,0,0,0.12)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.08)';
              }}
              >+ Add State</button>
            )}
            <button
              onClick={handleSave}
              style={{
                padding: '6px 18px',
                border: 'none',
                background: saveStatus === 'saved' ? '#27ae60' : '#2c2c2c',
                color: '#fff',
                borderRadius: 6,
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: 12,
                transition: 'all 0.3s',
                boxShadow: '0 2px 6px rgba(0,0,0,0.15)'
              }}
              onMouseEnter={(e) => {
                if (saveStatus !== 'saved') {
                  e.currentTarget.style.transform = 'translateY(-1px)';
                  e.currentTarget.style.boxShadow = '0 3px 8px rgba(0,0,0,0.2)';
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = '0 2px 6px rgba(0,0,0,0.15)';
              }}
            >
              {saveStatus === 'saved' ? '✓ Saved!' : 'Save Changes'}
            </button>
          </div>
        </div>
      </div>

      {/* Scrollable Content Area */}
      <div ref={scrollContainerRef} style={{ flex: 1, overflowY: 'auto', padding: '32px', background: '#f8f0e6' }}>

        {/* VOICES TAB */}
        {activeTab === 'voices' && (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))',
            gap: 24,
            alignContent: 'start'
          }}>
            {Object.entries(voices).map(([id, voice]) => {
              const colorHex = COLORS[voice.color as keyof typeof COLORS]?.hex || '#4a90e2';
              const Icon = iconMap[voice.icon as keyof typeof iconMap] || FaBrain;

              return (
                <div
                  key={id}
                  style={{
                    background: '#fff',
                    border: `2px solid ${voice.enabled ? colorHex : '#ddd'}`,
                    borderRadius: 12,
                    padding: 20,
                    position: 'relative',
                    boxShadow: voice.enabled ? '0 4px 12px rgba(0,0,0,0.1)' : '0 2px 6px rgba(0,0,0,0.05)',
                    transition: 'all 0.3s',
                    opacity: voice.enabled ? 1 : 0.6
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.transform = 'translateY(-2px)';
                    e.currentTarget.style.boxShadow = voice.enabled ? '0 6px 16px rgba(0,0,0,0.15)' : '0 3px 8px rgba(0,0,0,0.08)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.transform = 'translateY(0)';
                    e.currentTarget.style.boxShadow = voice.enabled ? '0 4px 12px rgba(0,0,0,0.1)' : '0 2px 6px rgba(0,0,0,0.05)';
                  }}
                >
                  {/* Delete button */}
                  <button
                    onClick={() => handleDelete(id)}
                    style={{
                      position: 'absolute',
                      top: 12,
                      right: 12,
                      background: 'rgba(255, 255, 255, 0.9)',
                      border: '1px solid #ddd',
                      borderRadius: 6,
                      width: 28,
                      height: 28,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      cursor: 'pointer',
                      fontSize: 14,
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

                  {/* Voice Header */}
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 16 }}>
                    {/* Icon Circle */}
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

                    {/* Name + Toggle */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                        <input
                          type="checkbox"
                          checked={voice.enabled}
                          onChange={e => handleUpdate(id, 'enabled', e.target.checked)}
                          style={{
                            width: 18,
                            height: 18,
                            cursor: 'pointer',
                            accentColor: colorHex
                          }}
                        />
                        <input
                          type="text"
                          value={voice.name}
                          onChange={e => handleRename(id, e.target.value)}
                          placeholder="Voice Name"
                          style={{
                            flex: 1,
                            border: 'none',
                            borderBottom: '2px solid transparent',
                            fontSize: 18,
                            fontWeight: 700,
                            background: 'transparent',
                            padding: '4px 0',
                            color: '#2c2c2c',
                            outline: 'none',
                            transition: 'border-color 0.2s'
                          }}
                          onFocus={(e) => {
                            e.currentTarget.style.borderBottomColor = colorHex;
                          }}
                          onBlur={(e) => {
                            e.currentTarget.style.borderBottomColor = 'transparent';
                          }}
                        />
                      </div>

                      {/* Icon + Color Selectors */}
                      <div style={{ display: 'flex', gap: 8 }}>
                        <select
                          value={voice.icon}
                          onChange={e => handleUpdate(id, 'icon', e.target.value)}
                          style={{
                            flex: 1,
                            padding: '6px 8px',
                            border: '1px solid #e0e0e0',
                            borderRadius: 6,
                            background: '#f9f9f9',
                            fontSize: 12,
                            cursor: 'pointer'
                          }}
                        >
                          {Object.entries(ICON_LABELS).map(([name, label]) => (
                            <option key={name} value={name}>{label}</option>
                          ))}
                        </select>
                        <select
                          value={voice.color}
                          onChange={e => handleUpdate(id, 'color', e.target.value)}
                          style={{
                            flex: 1,
                            padding: '6px 8px',
                            border: '1px solid #e0e0e0',
                            borderRadius: 6,
                            background: '#f9f9f9',
                            fontSize: 12,
                            cursor: 'pointer'
                          }}
                        >
                          {Object.entries(COLORS).map(([name, { label }]) => (
                            <option key={name} value={name}>
                              {label}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  </div>

                  {/* System Prompt */}
                  <div>
                    <label style={{
                      display: 'block',
                      fontSize: 11,
                      fontWeight: 600,
                      color: '#666',
                      marginBottom: 6,
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px'
                    }}>
                      Personality Prompt
                    </label>
                    <textarea
                      value={voice.systemPrompt}
                      onChange={e => handleUpdate(id, 'systemPrompt', e.target.value)}
                      placeholder="Describe this voice's personality, tone, and perspective..."
                      style={{
                        width: '100%',
                        minHeight: 120,
                        padding: 12,
                        fontSize: 13,
                        fontFamily: 'monospace',
                        border: '1px solid #e0e0e0',
                        borderRadius: 6,
                        background: '#fafafa',
                        resize: 'vertical',
                        boxSizing: 'border-box',
                        lineHeight: 1.6,
                        transition: 'all 0.2s'
                      }}
                      onFocus={(e) => {
                        e.currentTarget.style.borderColor = colorHex;
                        e.currentTarget.style.background = '#fff';
                      }}
                      onBlur={(e) => {
                        e.currentTarget.style.borderColor = '#e0e0e0';
                        e.currentTarget.style.background = '#fafafa';
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* META TAB */}
        {activeTab === 'meta' && (
          <div style={{ maxWidth: 800, margin: '0 auto' }}>
            <div style={{
              padding: 24,
              background: '#fff',
              border: '2px solid #d0c4b0',
              borderRadius: 12,
              boxShadow: '0 4px 12px rgba(0,0,0,0.08)'
            }}>
              <h3 style={{
                margin: '0 0 8px 0',
                fontSize: 20,
                fontWeight: 600,
                color: '#2c2c2c'
              }}>
                Meta Prompt
              </h3>
              <p style={{
                margin: '0 0 20px 0',
                fontSize: 14,
                color: '#666',
                lineHeight: 1.6
              }}>
                Global instructions applied to all voice personas. These instructions affect both voice comments and chat conversations. Use this to set a consistent tone or add context that all voices should be aware of.
              </p>
              <textarea
                value={metaPrompt}
                onChange={e => setMetaPrompt(e.target.value)}
                placeholder="e.g., Be honest and pragmatic. Prioritize mental well-being over theatrical commentary. Focus on actionable insights rather than abstract philosophizing..."
                style={{
                  width: '100%',
                  minHeight: 200,
                  padding: 16,
                  fontSize: 14,
                  fontFamily: 'monospace',
                  border: '2px solid #e0e0e0',
                  borderRadius: 8,
                  background: '#fafafa',
                  resize: 'vertical',
                  boxSizing: 'border-box',
                  lineHeight: 1.7,
                  transition: 'all 0.2s'
                }}
                onFocus={(e) => {
                  e.currentTarget.style.borderColor = '#2c2c2c';
                  e.currentTarget.style.background = '#fff';
                }}
                onBlur={(e) => {
                  e.currentTarget.style.borderColor = '#e0e0e0';
                  e.currentTarget.style.background = '#fafafa';
                }}
              />
            </div>
          </div>
        )}

        {/* STATES TAB */}
        {activeTab === 'states' && (
          <div style={{ maxWidth: 900, margin: '0 auto' }}>
            {/* Greeting Section */}
            <div style={{
              marginBottom: 24,
              padding: 24,
              background: '#fff',
              border: '2px solid #d0c4b0',
              borderRadius: 12,
              boxShadow: '0 4px 12px rgba(0,0,0,0.08)'
            }}>
              <h3 style={{
                margin: '0 0 8px 0',
                fontSize: 20,
                fontWeight: 600,
                color: '#2c2c2c'
              }}>
                Greeting Message
              </h3>
              <p style={{
                margin: '0 0 16px 0',
                fontSize: 14,
                color: '#666',
                lineHeight: 1.6
              }}>
                The message shown when you start writing. This appears at the top of the page.
              </p>
              <input
                type="text"
                value={stateConfig.greeting}
                onChange={e => setStateConfig({ ...stateConfig, greeting: e.target.value })}
                placeholder="e.g., How are you feeling today?"
                style={{
                  width: '100%',
                  padding: 12,
                  fontSize: 15,
                  border: '2px solid #e0e0e0',
                  borderRadius: 8,
                  background: '#fafafa',
                  boxSizing: 'border-box',
                  transition: 'all 0.2s'
                }}
                onFocus={(e) => {
                  e.currentTarget.style.borderColor = '#2c2c2c';
                  e.currentTarget.style.background = '#fff';
                }}
                onBlur={(e) => {
                  e.currentTarget.style.borderColor = '#e0e0e0';
                  e.currentTarget.style.background = '#fafafa';
                }}
              />
            </div>

            {/* States List */}
            <div style={{
              padding: 24,
              background: '#fff',
              border: '2px solid #d0c4b0',
              borderRadius: 12,
              boxShadow: '0 4px 12px rgba(0,0,0,0.08)'
            }}>
              <h3 style={{
                margin: '0 0 8px 0',
                fontSize: 20,
                fontWeight: 600,
                color: '#2c2c2c'
              }}>
                User States
              </h3>
              <p style={{
                margin: '0 0 24px 0',
                fontSize: 14,
                color: '#666',
                lineHeight: 1.6
              }}>
                Define emotional states that users can select. Each state has a prompt that influences how AI voices respond.
              </p>

              {/* States Grid */}
              <div style={{ display: 'grid', gap: 16 }}>
                {Object.entries(stateConfig.states).map(([id, state]) => (
                  <div key={id} style={{
                    padding: 16,
                    background: '#f9f9f9',
                    border: '2px solid #e0e0e0',
                    borderRadius: 8,
                    position: 'relative',
                    transition: 'all 0.2s'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = '#d0c4b0';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = '#e0e0e0';
                  }}
                  >
                    <button
                      onClick={() => handleDeleteState(id)}
                      style={{
                        position: 'absolute',
                        top: 12,
                        right: 12,
                        background: 'rgba(255, 255, 255, 0.9)',
                        border: '1px solid #ddd',
                        borderRadius: 6,
                        width: 28,
                        height: 28,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        cursor: 'pointer',
                        fontSize: 14,
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

                    <div style={{ marginBottom: 12 }}>
                      <label style={{
                        display: 'block',
                        fontSize: 11,
                        fontWeight: 600,
                        color: '#666',
                        marginBottom: 6,
                        textTransform: 'uppercase',
                        letterSpacing: '0.5px'
                      }}>
                        State Name
                      </label>
                      <input
                        type="text"
                        value={state.name}
                        onChange={e => handleUpdateState(id, 'name', e.target.value)}
                        placeholder="e.g., Happy, Anxious, Reflective..."
                        style={{
                          width: '100%',
                          padding: 10,
                          fontSize: 15,
                          fontWeight: 600,
                          border: '2px solid #e0e0e0',
                          borderRadius: 6,
                          background: '#fff',
                          boxSizing: 'border-box',
                          transition: 'all 0.2s'
                        }}
                        onFocus={(e) => {
                          e.currentTarget.style.borderColor = '#2c2c2c';
                        }}
                        onBlur={(e) => {
                          e.currentTarget.style.borderColor = '#e0e0e0';
                        }}
                      />
                    </div>

                    <div>
                      <label style={{
                        display: 'block',
                        fontSize: 11,
                        fontWeight: 600,
                        color: '#666',
                        marginBottom: 6,
                        textTransform: 'uppercase',
                        letterSpacing: '0.5px'
                      }}>
                        State Prompt
                      </label>
                      <textarea
                        value={state.prompt}
                        onChange={e => handleUpdateState(id, 'prompt', e.target.value)}
                        placeholder="e.g., The user is feeling anxious and overthinking things. Be gentle and help them ground themselves in the present moment..."
                        style={{
                          width: '100%',
                          minHeight: 80,
                          padding: 10,
                          fontSize: 13,
                          fontFamily: 'monospace',
                          border: '2px solid #e0e0e0',
                          borderRadius: 6,
                          background: '#fff',
                          resize: 'vertical',
                          boxSizing: 'border-box',
                          lineHeight: 1.6,
                          transition: 'all 0.2s'
                        }}
                        onFocus={(e) => {
                          e.currentTarget.style.borderColor = '#2c2c2c';
                        }}
                        onBlur={(e) => {
                          e.currentTarget.style.borderColor = '#e0e0e0';
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
