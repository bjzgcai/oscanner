import { useState, useEffect } from 'react';
import { StateCube } from './StateCube';
import type { StateConfig } from '../types/voice';

interface Props {
  stateConfig: StateConfig;
  selectedState: string | null;
  onChoose: (stateId: string) => void;
}

export default function StateChooser({ stateConfig, selectedState, onChoose }: Props) {
  const [isExpanded, setIsExpanded] = useState(!selectedState);

  // @@@ Collapse when selectedState is set externally
  useEffect(() => {
    if (selectedState) {
      setIsExpanded(false);
    }
  }, [selectedState]);

  const selectedStateData = selectedState ? stateConfig.states[selectedState] : null;

  // @@@ Format today's date
  const today = new Date();
  const dateString = today.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long'
  });

  const handleStateSelect = (stateId: string) => {
    onChoose(stateId);
    setIsExpanded(false);
  };

  // @@@ Mini icon generator for collapsed state (24px version)
  const getMiniStateIcon = (stateId: string) => {
    const iconProps = { width: 24, height: 24, viewBox: "0 0 100 100" };

    switch(stateId.toLowerCase()) {
      case 'happy':
        return (
          <svg {...iconProps}>
            <circle cx="50" cy="50" r="40" fill="none" stroke="#FFD93D" strokeWidth="6"/>
            <path d="M 35 60 Q 50 75 65 60" fill="none" stroke="#FFD93D" strokeWidth="6" strokeLinecap="round"/>
            <circle cx="38" cy="40" r="4" fill="#FFD93D"/>
            <circle cx="62" cy="40" r="4" fill="#FFD93D"/>
          </svg>
        );
      case 'ok':
        return (
          <svg {...iconProps}>
            <circle cx="50" cy="50" r="40" fill="none" stroke="#95D5B2" strokeWidth="6"/>
            <line x1="35" y1="60" x2="65" y2="60" stroke="#95D5B2" strokeWidth="6" strokeLinecap="round"/>
            <circle cx="38" cy="40" r="4" fill="#95D5B2"/>
            <circle cx="62" cy="40" r="4" fill="#95D5B2"/>
          </svg>
        );
      case 'unhappy':
        return (
          <svg {...iconProps}>
            <circle cx="50" cy="50" r="40" fill="none" stroke="#A8DADC" strokeWidth="6"/>
            <path d="M 35 65 Q 50 50 65 65" fill="none" stroke="#A8DADC" strokeWidth="6" strokeLinecap="round"/>
            <circle cx="38" cy="40" r="4" fill="#A8DADC"/>
            <circle cx="62" cy="40" r="4" fill="#A8DADC"/>
          </svg>
        );
      default:
        return (
          <svg {...iconProps}>
            <circle cx="50" cy="50" r="35" fill="none" stroke="#999" strokeWidth="4"/>
          </svg>
        );
    }
  };

  return (
    <div style={{
      padding: '0',
      fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif"
    }}>
      {/* Compact view when state is selected */}
      {selectedStateData && !isExpanded ? (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          cursor: 'pointer'
        }}
        onClick={() => setIsExpanded(true)}
        >
          {/* Date */}
          <div style={{
            fontSize: 13,
            color: '#666',
            fontWeight: 400
          }}>
            {dateString}
          </div>

          {/* Mini icon + state name */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: '4px 12px',
            background: 'rgba(255,255,255,0.6)',
            borderRadius: 6,
            border: '1px solid rgba(0,0,0,0.08)',
            transition: 'all 0.2s'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'rgba(255,255,255,0.9)';
            e.currentTarget.style.borderColor = 'rgba(0,0,0,0.15)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'rgba(255,255,255,0.6)';
            e.currentTarget.style.borderColor = 'rgba(0,0,0,0.08)';
          }}
          >
            {/* Shrunken state icon */}
            <div style={{ flexShrink: 0, display: 'flex', alignItems: 'center' }}>
              {selectedState && getMiniStateIcon(selectedState)}
            </div>

            <span style={{
              fontSize: 14,
              fontWeight: 500,
              color: '#333'
            }}>
              {selectedStateData.name}
            </span>
          </div>
        </div>
      ) : (
        /* Expanded view - cube centered on entire screen */
        <>
          {/* Date header - stays in place */}
          <div style={{
            fontSize: 13,
            color: '#666',
            fontWeight: 400
          }}>
            {dateString}
          </div>

          {/* Fixed overlay - cube centered on viewport */}
          <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            pointerEvents: 'none'
          }}>
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 20,
              pointerEvents: 'auto'
            }}>
              <StateCube
                stateConfig={stateConfig}
                onStateSelect={handleStateSelect}
              />

              {/* Helper text */}
              <div style={{
                fontSize: 12,
                color: '#999',
                textAlign: 'center'
              }}>
                Click a state to select
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
