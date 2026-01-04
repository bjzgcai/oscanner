import { FaBrain, FaHeart, FaQuestion, FaCloud } from 'react-icons/fa';
import { CSSProperties } from 'react';

interface VoiceCommentProps {
  voice: string;
  text: string;
  icon: string;
  color: string;
  style?: CSSProperties;
}

const iconMap = {
  brain: FaBrain,
  heart: FaHeart,
  question: FaQuestion,
  cloud: FaCloud,
};

const colorMap: Record<string, { background: string; border: string }> = {
  blue: { background: '#e6f2ff', border: '#4d9fff' },
  pink: { background: '#ffe6f2', border: '#ff66b3' },
  yellow: { background: '#fffbe6', border: '#ffdd33' },
  green: { background: '#e6ffe6', border: '#66ff66' },
  purple: { background: '#f3e6ff', border: '#b366ff' },
};

export default function VoiceComment({ voice, text, icon, color, style }: VoiceCommentProps) {
  const Icon = iconMap[icon as keyof typeof iconMap];
  const colors = colorMap[color] || { background: '#f0f0f0', border: '#ccc' };

  return (
    <div
      className="voice-comment"
      style={{
        backgroundColor: colors.background,
        borderColor: colors.border,
        ...style,
      }}
    >
      <div className="voice-header">
        {Icon && <Icon className="voice-icon" />}
        <strong>{voice}:</strong>
      </div>
      <div className="voice-text">{text}</div>
    </div>
  );
}