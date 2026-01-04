import { useState, useEffect } from 'react';
import type { VoiceConfig } from '../types/voice';
import { getVoices, saveVoices, clearVoices } from '../utils/voiceStorage';

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
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saved'>('idle');

  // @@@ Sync with defaultVoices prop (handles async fetch + Use Default button)
  useEffect(() => {
    if (Object.keys(defaultVoices).length > 0) {
      const stored = getVoices();
      setVoices(stored || defaultVoices);
    }
  }, [defaultVoices]);

  const handleSave = () => {
    saveVoices(voices);
    onSave(voices);
    setSaveStatus('saved');
    setTimeout(() => setSaveStatus('idle'), 2000);
  };

  const handleDefault = () => {
    clearVoices();
    // Deep copy to force React to re-render
    const freshDefaults = JSON.parse(JSON.stringify(defaultVoices));
    setVoices(freshDefaults);
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
  };

  const handleDelete = (id: string) => {
    const { [id]: _, ...rest } = voices;
    setVoices(rest);
  };

  const handleRename = (id: string, newName: string) => {
    // Just update the name, keep the ID stable to avoid React re-renders
    setVoices({ ...voices, [id]: { ...voices[id], name: newName } });
  };

  const handleUpdate = (id: string, field: keyof VoiceConfig, value: any) => {
    setVoices({ ...voices, [id]: { ...voices[id], [field]: value } });
  };

  const handleExport = () => {
    const blob = new Blob([JSON.stringify(voices, null, 2)], { type: 'application/json' });
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
          setVoices(imported);
          saveVoices(imported);
          onSave(imported);
        });
      }
    };
    input.click();
  };

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: '#f5e6d3', overflow: 'hidden' }}>
      <div style={{ padding: '20px 32px', borderBottom: '1px solid #d0c4b0', background: '#f5e6d3', flexShrink: 0 }}>
        <h2 style={{ margin: '0 0 16px 0', color: '#333', fontSize: 24 }}>Voice Settings</h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={handleAdd} style={{ padding: '6px 12px', border: '1px solid #ccc', background: '#fffef9', borderRadius: 4, cursor: 'pointer' }}>+ Add</button>
          <button onClick={handleImport} style={{ padding: '6px 12px', border: '1px solid #ccc', background: '#fffef9', borderRadius: 4, cursor: 'pointer' }}>Import</button>
          <button onClick={handleExport} style={{ padding: '6px 12px', border: '1px solid #ccc', background: '#fffef9', borderRadius: 4, cursor: 'pointer' }}>Export</button>
          <button onClick={handleDefault} style={{ padding: '6px 12px', border: '1px solid #ccc', background: '#fffef9', borderRadius: 4, cursor: 'pointer' }}>Use Default</button>
          <button
            onClick={handleSave}
            style={{
              padding: '6px 12px',
              border: saveStatus === 'saved' ? '1px solid #27ae60' : '1px solid #666',
              background: saveStatus === 'saved' ? '#27ae60' : '#333',
              color: '#fff',
              borderRadius: 4,
              cursor: 'pointer',
              fontWeight: 'bold',
              transition: 'all 0.3s'
            }}
          >
            {saveStatus === 'saved' ? '✓ Saved!' : 'Save'}
          </button>
        </div>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: 32, display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 20, alignContent: 'start', background: '#f5e6d3' }}>
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
  );
}
