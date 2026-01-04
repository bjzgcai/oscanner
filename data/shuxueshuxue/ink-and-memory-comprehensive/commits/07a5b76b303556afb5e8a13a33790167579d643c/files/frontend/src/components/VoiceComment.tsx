import { FaBrain, FaHeart, FaQuestion, FaCloud, FaTheaterMasks, FaEye, FaFistRaised, FaLightbulb, FaShieldAlt, FaWind, FaFire, FaCompass } from 'react-icons/fa';

interface VoiceCommentProps {
  voice: string;
  text: string;
  icon: string;
  color: string;
  onQuote?: () => void;
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

export default function VoiceComment({ voice, text, icon, color, onQuote }: VoiceCommentProps) {
  const Icon = iconMap[icon as keyof typeof iconMap];
  const colors = colorMap[color] || { background: '#f0f0f0', border: '#ccc' };

  return (
    <div
      className="voice-comment"
      style={{
        backgroundColor: colors.background,
        borderColor: colors.border,
        position: 'relative'
      }}
    >
      <div className="voice-header">
        {Icon && <Icon className="voice-icon" />}
        <strong>{voice}:</strong>
      </div>
      <div className="voice-text">{text}</div>
      {onQuote && (
        <button
          onClick={onQuote}
          style={{
            position: 'absolute',
            top: 8,
            right: 8,
            background: 'rgba(255, 255, 255, 0.9)',
            border: 'none',
            borderRadius: '50%',
            width: 28,
            height: 28,
            fontSize: 18,
            fontWeight: 'bold',
            cursor: 'pointer',
            color: '#666',
            opacity: 0,
            transition: 'all 0.2s',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
          }}
          onMouseEnter={e => {
            e.currentTarget.style.opacity = '1';
            e.currentTarget.style.transform = 'scale(1.1)';
          }}
          onMouseLeave={e => {
            e.currentTarget.style.opacity = '0';
            e.currentTarget.style.transform = 'scale(1)';
          }}
          title="引用到编辑器"
          className="quote-button"
        >
          "
        </button>
      )}
    </div>
  );
}