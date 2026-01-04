import { useState } from 'react';
import { FaBrain, FaHeart, FaQuestion, FaCloud, FaTheaterMasks, FaEye, FaFistRaised, FaLightbulb, FaShieldAlt, FaWind, FaFire, FaCompass } from 'react-icons/fa';

interface VoiceCommentProps {
  voice: string;
  text: string;
  icon: string;
  color: string;
  onQuote?: () => void;
  isHovered?: boolean;
}

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

const colorMap: Record<string, { background: string; border: string }> = {
  blue: { background: '#e6f2ff', border: '#4d9fff' },
  pink: { background: '#ffe6f2', border: '#ff66b3' },
  yellow: { background: '#fffbe6', border: '#ffdd33' },
  green: { background: '#e6ffe6', border: '#66ff66' },
  purple: { background: '#f3e6ff', border: '#b366ff' },
};

export default function VoiceComment({ voice, text, icon, color, onQuote, isHovered }: VoiceCommentProps) {
  const Icon = iconMap[icon as keyof typeof iconMap];
  const colors = colorMap[color] || { background: '#f0f0f0', border: '#ccc' };
  const [isLocalHovered, setIsLocalHovered] = useState(false);

  // Combined hover state (from parent highlighting OR local hover)
  const showHoverEffect = isHovered || isLocalHovered;

  return (
    <div
      className={`voice-comment ${showHoverEffect ? 'hovered' : ''}`}
      onMouseEnter={() => setIsLocalHovered(true)}
      onMouseLeave={() => setIsLocalHovered(false)}
      onClick={onQuote}
      style={{
        backgroundColor: colors.background,
        borderColor: colors.border,
        position: 'relative',
        transform: showHoverEffect ? 'scale(1.02)' : 'scale(1)',
        boxShadow: showHoverEffect ? '0 4px 12px rgba(0,0,0,0.15)' : 'none',
        transition: 'all 0.2s ease',
        borderWidth: showHoverEffect ? '2px' : '4px',
        cursor: onQuote ? 'pointer' : 'default',
      }}
    >
      <div className="voice-header">
        {Icon && <Icon className="voice-icon" />}
        <strong>{voice}:</strong>
      </div>
      <div className="voice-text">{text}</div>

      {/* Show "Click to reply" hint on hover */}
      {onQuote && isLocalHovered && (
        <div
          style={{
            position: 'absolute',
            bottom: 8,
            right: 8,
            fontSize: 11,
            color: '#888',
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            fontStyle: 'italic',
            pointerEvents: 'none',
            opacity: 0.8
          }}
        >
          Click to reply
        </div>
      )}
    </div>
  );
}