import { useState, useEffect, useRef } from 'react';
import type { VoiceConfig, StateConfig, UserState } from '../types/voice';
import { getVoices, saveVoices, clearVoices, getMetaPrompt, saveMetaPrompt, getStateConfig, saveStateConfig } from '../utils/voiceStorage';

// @@@ Display mappings (text name → visual)
const COLORS = {
  'blue': { hex: '#4a90e2', label: 'Blue' },
  'purple': { hex: '#9b59b6', label: 'Purple' },
  'pink': { hex: '#e91e63', label: 'Pink' },
  'green': { hex: '#27ae60', label: 'Green' },
  'yellow': { hex: '#f39c12', label: 'Yellow' }
};

const ICONS = {
  'brain': '🧠', 'lightbulb': '💡', 'masks': '🎭', 'cloud': '☁️',
  'shield': '🛡️', 'compass': '🧭', 'heart': '❤️', 'fist': '✊',
  'fire': '🔥', 'wind': '💨', 'question': '❓', 'eye': '👁️'
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
    console.log('🔄 Use Default clicked');
    console.log('Current voices:', voices);
    console.log('Default voices:', defaultVoices);
    clearVoices();
    localStorage.removeItem('meta-prompt');
    localStorage.removeItem('state-config');
    // Deep copy to force React to re-render
    const freshDefaults = JSON.parse(JSON.stringify(defaultVoices));
    console.log('Fresh defaults:', freshDefaults);
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

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: '#f8f0e6', overflow: 'hidden' }}>
      {/* Fixed Header - Function Bar */}
      <div style={{
        padding: '16px 24px',
        background: '#fff',
        borderBottom: '2px solid #d0c4b0',
        boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
        flexShrink: 0
      }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button onClick={handleAdd} style={{ padding: '8px 16px', border: '1px solid #ccc', background: '#fffef9', borderRadius: 4, cursor: 'pointer', fontSize: 13 }}>+ Add Voice</button>
          <button onClick={handleImport} style={{ padding: '8px 16px', border: '1px solid #ccc', background: '#fffef9', borderRadius: 4, cursor: 'pointer', fontSize: 13 }}>Import</button>
          <button onClick={handleExport} style={{ padding: '8px 16px', border: '1px solid #ccc', background: '#fffef9', borderRadius: 4, cursor: 'pointer', fontSize: 13 }}>Export</button>
          <button onClick={handleDefault} style={{ padding: '8px 16px', border: '1px solid #ccc', background: '#fffef9', borderRadius: 4, cursor: 'pointer', fontSize: 13 }}>Use Default</button>
          <div style={{ flex: 1 }} />
          <button
            onClick={handleSave}
            style={{
              padding: '8px 20px',
              border: saveStatus === 'saved' ? '1px solid #27ae60' : '1px solid #666',
              background: saveStatus === 'saved' ? '#27ae60' : '#333',
              color: '#fff',
              borderRadius: 4,
              cursor: 'pointer',
              fontWeight: 'bold',
              fontSize: 13,
              transition: 'all 0.3s'
            }}
          >
            {saveStatus === 'saved' ? '✓ Saved!' : 'Save'}
          </button>
        </div>
      </div>

      {/* Scrollable Content Area */}
      <div ref={scrollContainerRef} style={{ flex: 1, overflowY: 'auto', padding: '24px', background: '#f8f0e6' }}>
        {/* Meta Prompt Section */}
        <div style={{
          marginBottom: 24,
          padding: 20,
          background: '#fffef9',
          border: '1px solid #d0c4b0',
          borderRadius: 6,
          boxShadow: '0 1px 3px rgba(0,0,0,0.08)'
        }}>
          <h3 style={{
            margin: '0 0 12px 0',
            fontSize: 15,
            fontWeight: 600,
            color: '#333',
            letterSpacing: '-0.01em'
          }}>
            Meta Prompt
          </h3>
          <p style={{
            margin: '0 0 12px 0',
            fontSize: 12,
            color: '#666',
            lineHeight: 1.5
          }}>
            Global instructions applied to all voice personas (affects both comments and chat)
          </p>
          <textarea
            value={metaPrompt}
            onChange={e => setMetaPrompt(e.target.value)}
            placeholder="e.g., Be honest and pragmatic. Prioritize mental well-being over theatrical commentary..."
            style={{
              width: '100%',
              minHeight: 100,
              padding: 12,
              fontSize: 13,
              fontFamily: 'monospace',
              border: '1px solid #d0c4b0',
              borderRadius: 4,
              background: '#fff',
              resize: 'vertical',
              boxSizing: 'border-box',
              lineHeight: 1.6
            }}
          />
        </div>

        {/* User States Section */}
        <div style={{
          marginBottom: 24,
          padding: 20,
          background: '#fffef9',
          border: '1px solid #d0c4b0',
          borderRadius: 6,
          boxShadow: '0 1px 3px rgba(0,0,0,0.08)'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h3 style={{
              margin: 0,
              fontSize: 15,
              fontWeight: 600,
              color: '#333',
              letterSpacing: '-0.01em'
            }}>
              User States
            </h3>
            <button
              onClick={handleAddState}
              style={{
                padding: '4px 12px',
                fontSize: 12,
                border: '1px solid #d0c4b0',
                background: '#fff',
                borderRadius: 4,
                cursor: 'pointer'
              }}
            >
              + Add State
            </button>
          </div>
          <p style={{
            margin: '0 0 16px 0',
            fontSize: 12,
            color: '#666',
            lineHeight: 1.5
          }}>
            Configure states shown at startup, each with a specific prompt context
          </p>

          {/* Greeting */}
          <div style={{ marginBottom: 16 }}>
            <label style={{
              display: 'block',
              fontSize: 12,
              fontWeight: 600,
              color: '#333',
              marginBottom: 6
            }}>
              Greeting Message
            </label>
            <input
              type="text"
              value={stateConfig.greeting}
              onChange={e => setStateConfig({ ...stateConfig, greeting: e.target.value })}
              placeholder="e.g., How are you feeling today?"
              style={{
                width: '100%',
                padding: 8,
                fontSize: 13,
                border: '1px solid #d0c4b0',
                borderRadius: 4,
                background: '#fff',
                boxSizing: 'border-box'
              }}
            />
          </div>

          {/* States */}
          <div style={{ display: 'grid', gap: 12 }}>
            {Object.entries(stateConfig.states).map(([id, state]) => (
              <div key={id} style={{
                padding: 12,
                background: '#f8f0e6',
                border: '1px solid #d0c4b0',
                borderRadius: 4,
                position: 'relative'
              }}>
                <button
                  onClick={() => handleDeleteState(id)}
                  style={{
                    position: 'absolute',
                    top: 8,
                    right: 8,
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    fontSize: 14
                  }}
                  title="Delete"
                >
                  🗑️
                </button>

                <div style={{ marginBottom: 8 }}>
                  <label style={{
                    display: 'block',
                    fontSize: 11,
                    fontWeight: 600,
                    color: '#666',
                    marginBottom: 4
                  }}>
                    State Name (shown to user)
                  </label>
                  <input
                    type="text"
                    value={state.name}
                    onChange={e => handleUpdateState(id, 'name', e.target.value)}
                    placeholder="e.g., Happy"
                    style={{
                      width: '100%',
                      padding: 6,
                      fontSize: 13,
                      border: '1px solid #d0c4b0',
                      borderRadius: 4,
                      background: '#fff',
                      boxSizing: 'border-box'
                    }}
                  />
                </div>

                <div>
                  <label style={{
                    display: 'block',
                    fontSize: 11,
                    fontWeight: 600,
                    color: '#666',
                    marginBottom: 4
                  }}>
                    State Prompt (added to voice context)
                  </label>
                  <textarea
                    value={state.prompt}
                    onChange={e => handleUpdateState(id, 'prompt', e.target.value)}
                    placeholder="e.g., The user is feeling positive and energized..."
                    style={{
                      width: '100%',
                      minHeight: 60,
                      padding: 8,
                      fontSize: 12,
                      fontFamily: 'monospace',
                      border: '1px solid #d0c4b0',
                      borderRadius: 4,
                      background: '#fff',
                      resize: 'vertical',
                      boxSizing: 'border-box',
                      lineHeight: 1.4
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Voice Personas Grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
          gap: 20,
          alignContent: 'start'
        }}>
        {Object.entries(voices).map(([id, voice]) => (
          <div key={id} style={{ padding: 12, border: '1px solid #d0c4b0', borderRadius: 4, position: 'relative', background: '#fffef9' }}>
            <button
              onClick={() => handleDelete(id)}
              style={{ position: 'absolute', top: 8, right: 8, background: 'none', border: 'none', cursor: 'pointer', fontSize: 16 }}
              title="Delete"
            >
              🗑️
            </button>

            <div style={{ marginBottom: 8 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <input
                  type="checkbox"
                  checked={voice.enabled}
                  onChange={e => handleUpdate(id, 'enabled', e.target.checked)}
                />
                <input
                  type="text"
                  value={voice.name}
                  onChange={e => handleRename(id, e.target.value)}
                  placeholder="Voice Name"
                  style={{ flex: 1, border: 'none', borderBottom: '1px solid #d0c4b0', fontSize: 14, fontWeight: 'bold', background: 'transparent', padding: '4px 0' }}
                />
              </label>
            </div>

            <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              <select
                value={voice.icon}
                onChange={e => handleUpdate(id, 'icon', e.target.value)}
                style={{ flex: 1, padding: 4, border: '1px solid #d0c4b0', borderRadius: 4, background: '#fff' }}
              >
                {Object.entries(ICONS).map(([name, emoji]) => (
                  <option key={name} value={name}>{emoji} {name}</option>
                ))}
              </select>
              <select
                value={voice.color}
                onChange={e => handleUpdate(id, 'color', e.target.value)}
                style={{ flex: 1, padding: 4, border: '1px solid #d0c4b0', borderRadius: 4, background: '#fff' }}
              >
                {Object.entries(COLORS).map(([name, { hex, label }]) => (
                  <option key={name} value={name} style={{ color: hex }}>● {label}</option>
                ))}
              </select>
            </div>

            <textarea
              value={voice.systemPrompt}
              onChange={e => handleUpdate(id, 'systemPrompt', e.target.value)}
              placeholder="Voice prompt..."
              style={{ width: '100%', minHeight: 100, padding: 8, fontSize: 13, fontFamily: 'monospace', border: '1px solid #d0c4b0', borderRadius: 4, background: '#fff', resize: 'none', boxSizing: 'border-box' }}
            />
          </div>
        ))}
        </div>
      </div>
    </div>
  );
}
