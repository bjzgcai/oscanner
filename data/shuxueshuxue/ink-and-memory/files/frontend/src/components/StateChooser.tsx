import { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { StateCube } from './StateCube';
import type { StateConfig } from '../api/voiceApi';
import { getDateLocale } from '../i18n';
import { parseFlexibleTimestamp } from '../utils/timezone';

interface Props {
  stateConfig: StateConfig;
  selectedState: string | null;
  selectedStateLoading?: boolean;
  createdAt?: string;  // ISO timestamp recorded when the session was created
  onChoose: (stateId: string) => void;
}

export default function StateChooser({
  stateConfig,
  selectedState,
  selectedStateLoading = false,
  createdAt,
  onChoose
}: Props) {
  const { i18n } = useTranslation();
  const [isExpanded, setIsExpanded] = useState(false);
  const [shouldAnimate, setShouldAnimate] = useState(false);
  const [isFadingOut, setIsFadingOut] = useState(false);
  const indicatorRef = useRef<HTMLDivElement>(null);

  // @@@ Collapse when selectedState is set externally (skip while loading)
  useEffect(() => {
    if (selectedStateLoading) return;
    if (selectedState) {
      setIsExpanded(false);
      // Trigger highlight animation
      setShouldAnimate(true);
      setTimeout(() => setShouldAnimate(false), 600);
    } else {
      setIsExpanded(true);
    }
  }, [selectedState, selectedStateLoading]);

  const selectedStateData = selectedState ? stateConfig.states[selectedState] : null;

  // @@@ Use createdAt if provided, otherwise use today
  const timestamp = createdAt ? parseFlexibleTimestamp(createdAt) : null;
  const displayDate = timestamp ?? new Date();

  const dateLocale = getDateLocale(i18n.language);
  const dateString = displayDate.toLocaleDateString(dateLocale, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long'
  });

  const handleStateSelect = (stateId: string) => {
    // Trigger fade-out animation
    setIsFadingOut(true);

    // Wait for animation, then collapse and notify parent
    setTimeout(() => {
      setIsExpanded(false);
      setIsFadingOut(false);
      onChoose(stateId);
    }, 800); // Match animation duration
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

  if (selectedStateLoading) {
    return <div style={{ height: '32px' }} />;
  }

  return (
    <>
      {/* @@@ Keyframe animation for highlight effect */}
      <style>{`
        @keyframes stateHighlight {
          0% {
            transform: scale(1);
            box-shadow: 0 0 0 0 rgba(100, 150, 255, 0.4);
          }
          50% {
            transform: scale(1.05);
            box-shadow: 0 0 0 8px rgba(100, 150, 255, 0);
          }
          100% {
            transform: scale(1);
            box-shadow: 0 0 0 0 rgba(100, 150, 255, 0);
          }
        }
      `}</style>

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
            <div
              ref={indicatorRef}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '4px 12px',
                background: 'rgba(255,255,255,0.6)',
                borderRadius: 6,
                border: '1px solid rgba(0,0,0,0.08)',
                transition: 'all 0.2s',
                animation: shouldAnimate ? 'stateHighlight 0.6s ease-out' : 'none'
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
        /* Expanded view - full-screen white overlay */
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: '#ffffff',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          zIndex: 9999,
          opacity: isFadingOut ? 0 : 1,
          transition: 'opacity 0.8s ease-out',
          pointerEvents: isFadingOut ? 'none' : 'auto'
        }}>
          {/* Header text */}
          <h1 style={{
            fontSize: 48,
            fontWeight: 300,
            color: '#333',
            marginBottom: 60,
            textAlign: 'center',
            letterSpacing: '0.05em',
            opacity: isFadingOut ? 0 : 1,
            transform: isFadingOut ? 'translateY(-20px)' : 'translateY(0)',
            transition: 'all 0.8s ease-out'
          }}>
            {stateConfig.greeting || "What's your emotion today?"}
          </h1>

          {/* 3D Cube */}
          <div style={{
            opacity: isFadingOut ? 0 : 1,
            transform: isFadingOut ? 'scale(0.9)' : 'scale(1)',
            transition: 'all 0.8s ease-out'
          }}>
            <StateCube
              stateConfig={stateConfig}
              onStateSelect={handleStateSelect}
            />
          </div>

          {/* Helper text */}
          <p style={{
            marginTop: 40,
            fontSize: 14,
            color: '#999',
            textAlign: 'center',
            opacity: isFadingOut ? 0 : 1,
            transition: 'opacity 0.8s ease-out'
          }}>
            Click a state to begin writing
          </p>
        </div>
      )}
      </div>
    </>
  );
}
