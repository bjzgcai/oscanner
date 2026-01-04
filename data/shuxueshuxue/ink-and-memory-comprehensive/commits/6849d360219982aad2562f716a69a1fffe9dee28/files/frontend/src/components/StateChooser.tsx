import { useState, useEffect } from 'react';
import type { StateConfig } from '../types/voice';

interface Props {
  stateConfig: StateConfig;
  selectedState: string | null;
  onChoose: (stateId: string) => void;
}

export default function StateChooser({ stateConfig, selectedState, onChoose }: Props) {
  const [isExpanded, setIsExpanded] = useState(!selectedState);

  // @@@ Collapse when selectedState is set externally (e.g., loaded from database)
  useEffect(() => {
    if (selectedState) {
      setIsExpanded(false);
    }
  }, [selectedState]);

  const selectedStateData = selectedState ? stateConfig.states[selectedState] : null;

  return (
    <div style={{
      padding: '16px 20px',
      background: 'linear-gradient(135deg, #fffef9 0%, #f8f0e6 100%)',
      border: '1px solid #d0c4b0',
      borderRadius: 8,
      boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
      fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif"
    }}>
      {/* Compact view when state is selected */}
      {selectedStateData && !isExpanded ? (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            flex: 1
          }}>
            <span style={{
              fontSize: 13,
              color: '#666',
              fontWeight: 500
            }}>
              Current state:
            </span>
            <span style={{
              fontSize: 14,
              fontWeight: 600,
              color: '#333',
              padding: '4px 12px',
              background: '#fff',
              border: '1px solid #d0c4b0',
              borderRadius: 4
            }}>
              {selectedStateData.name}
            </span>
          </div>
          <button
            onClick={() => setIsExpanded(true)}
            style={{
              padding: '6px 14px',
              fontSize: 12,
              fontWeight: 500,
              border: '1px solid #d0c4b0',
              background: '#fff',
              borderRadius: 4,
              cursor: 'pointer',
              transition: 'all 0.2s',
              color: '#333'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#f0f0f0';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = '#fff';
            }}
          >
            Change
          </button>
        </div>
      ) : (
        /* Expanded view - choose state */
        <>
          <p style={{
            margin: '0 0 16px 0',
            fontSize: 15,
            color: '#333',
            textAlign: 'center',
            lineHeight: 1.5,
            fontWeight: 500
          }}>
            {stateConfig.greeting}
          </p>
          <div style={{
            display: 'flex',
            gap: 10,
            justifyContent: 'center',
            flexWrap: 'wrap'
          }}>
            {Object.entries(stateConfig.states).map(([id, state]) => {
              const isSelected = id === selectedState;
              return (
                <button
                  key={id}
                  onClick={() => {
                    onChoose(id);
                    setIsExpanded(false);
                  }}
                  style={{
                    padding: '10px 20px',
                    fontSize: 14,
                    fontWeight: isSelected ? 600 : 500,
                    border: isSelected ? '2px solid #666' : '1px solid #d0c4b0',
                    background: isSelected ? '#fff' : '#fff',
                    borderRadius: 6,
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    minWidth: '90px',
                    color: '#333',
                    boxShadow: isSelected ? '0 2px 6px rgba(0,0,0,0.12)' : 'none'
                  }}
                  onMouseEnter={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.background = '#f8f0e6';
                      e.currentTarget.style.borderColor = '#999';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.background = '#fff';
                      e.currentTarget.style.borderColor = '#d0c4b0';
                    }
                  }}
                >
                  {state.name}
                </button>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
