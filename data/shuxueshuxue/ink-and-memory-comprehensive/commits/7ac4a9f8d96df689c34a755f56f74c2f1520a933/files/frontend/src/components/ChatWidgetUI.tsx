import React, { useState, useRef, useEffect } from 'react';
import type { ChatWidgetData } from '../engine/ChatWidget';
import {
  FaBrain, FaHeart, FaQuestion, FaCloud, FaTheaterMasks, FaEye,
  FaFistRaised, FaLightbulb, FaShieldAlt, FaWind, FaFire, FaCompass
} from 'react-icons/fa';

// @@@ Inject CSS keyframes for button pulse animation
if (typeof document !== 'undefined') {
  const styleId = 'chat-widget-pulse-animation';
  if (!document.getElementById(styleId)) {
    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
      @keyframes pulse {
        0%, 100% {
          opacity: 0.5;
        }
        50% {
          opacity: 1;
        }
      }
    `;
    document.head.appendChild(style);
  }
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

interface ChatWidgetUIProps {
  data: ChatWidgetData;
  onSendMessage: (message: string) => void;
  onDelete: () => void;
  isProcessing: boolean;
}

export default function ChatWidgetUI({ data, onSendMessage, onDelete, isProcessing }: ChatWidgetUIProps) {
  const [inputValue, setInputValue] = useState('');
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const [isHovered, setIsHovered] = useState(false);

  // @@@ Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    setTimeout(() => {
      if (messagesContainerRef.current) {
        messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight;
      }
    }, 100);
  }, [data.messages.length]);

  const handleSend = () => {
    if (inputValue.trim() && !isProcessing) {
      onSendMessage(inputValue.trim());
      setInputValue('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const Icon = iconMap[data.voiceConfig.icon as keyof typeof iconMap] || FaBrain;

  return (
    <div
      style={{
        margin: '20px 0',
        padding: '16px 20px',
        background: 'rgba(250, 248, 245, 0.6)',
        borderRadius: '12px',
        maxWidth: '600px',
        position: 'relative',
        transition: 'all 0.2s ease'
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Delete button - only visible on hover */}
      <button
        onClick={onDelete}
        style={{
          position: 'absolute',
          top: '8px',
          right: '8px',
          padding: '4px 8px',
          backgroundColor: 'transparent',
          color: '#999',
          border: 'none',
          borderRadius: '4px',
          fontSize: '16px',
          cursor: 'pointer',
          transition: 'all 0.2s',
          opacity: isHovered ? 0.6 : 0,
          pointerEvents: isHovered ? 'auto' : 'none',
          lineHeight: '1'
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.opacity = '1';
          e.currentTarget.style.color = '#d44';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.opacity = '0.6';
          e.currentTarget.style.color = '#999';
        }}
        title="Delete chat"
      >
        ×
      </button>

      {/* Initial greeting or first message */}
      <div style={{
        display: 'flex',
        gap: '10px',
        alignItems: 'flex-start',
        marginBottom: '16px'
      }}>
        <Icon size={18} color="#666" style={{ marginTop: '2px', flexShrink: 0 }} />
        <div style={{
          color: '#444',
          fontSize: '15px',
          lineHeight: '1.6',
          fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
          flex: 1
        }}>
          {data.messages.length === 0
            ? "What's up?"
            : data.messages[0].role === 'assistant'
              ? data.messages[0].content
              : "What's up?"
          }
        </div>
      </div>

      {/* Messages (skip first if it's assistant) */}
      <div
        ref={messagesContainerRef}
        style={{
          maxHeight: '300px',
          overflowY: 'auto',
          marginBottom: '16px'
        }}
      >
        {data.messages.length > 0 && (
          data.messages
            .slice(data.messages[0].role === 'assistant' ? 1 : 0)
            .map((msg, idx) => (
              <div
                key={idx}
                style={{
                  marginBottom: '12px',
                  display: 'flex',
                  gap: '10px',
                  alignItems: 'flex-start'
                }}
              >
                {msg.role === 'user' ? (
                  <>
                    <div style={{
                      width: '26px',
                      height: '26px',
                      borderRadius: '50%',
                      backgroundColor: 'rgba(100, 100, 100, 0.1)',
                      flexShrink: 0,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '11px',
                      color: '#666',
                      fontWeight: 600,
                      fontFamily: 'system-ui'
                    }}>
                      U
                    </div>
                    <div style={{
                      color: '#555',
                      fontSize: '15px',
                      lineHeight: '1.6',
                      paddingTop: '2px',
                      fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif"
                    }}>
                      {msg.content}
                    </div>
                  </>
                ) : (
                  <>
                    <Icon size={18} color="#666" style={{ marginTop: '2px', flexShrink: 0 }} />
                    <div style={{
                      color: '#444',
                      fontSize: '15px',
                      lineHeight: '1.6',
                      paddingTop: '2px',
                      fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif"
                    }}>
                      {msg.content}
                    </div>
                  </>
                )}
              </div>
            ))
        )}
      </div>

      {/* Input */}
      <div style={{
        display: 'flex',
        gap: '10px',
        alignItems: 'center',
        paddingTop: '4px'
      }}>
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={`Chat with ${data.voiceConfig.name}...`}
          disabled={isProcessing}
          style={{
            flex: 1,
            padding: '8px 12px',
            border: 'none',
            borderBottom: '2px solid rgba(0, 0, 0, 0.1)',
            fontSize: '15px',
            outline: 'none',
            backgroundColor: 'transparent',
            fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
            color: '#444',
            transition: 'border-color 0.2s'
          }}
          onFocus={(e) => {
            e.currentTarget.style.borderBottomColor = 'rgba(0, 0, 0, 0.2)';
          }}
          onBlur={(e) => {
            e.currentTarget.style.borderBottomColor = 'rgba(0, 0, 0, 0.1)';
          }}
        />
        <button
          onClick={handleSend}
          disabled={!inputValue.trim() || isProcessing}
          style={{
            padding: '6px 14px',
            backgroundColor: 'transparent',
            color: isProcessing || !inputValue.trim() ? '#ccc' : '#666',
            border: '1.5px solid',
            borderColor: isProcessing || !inputValue.trim() ? 'rgba(0,0,0,0.1)' : 'rgba(0,0,0,0.2)',
            borderRadius: '6px',
            fontSize: '14px',
            fontWeight: 500,
            cursor: isProcessing || !inputValue.trim() ? 'not-allowed' : 'pointer',
            transition: 'all 0.2s',
            fontFamily: 'system-ui',
            animation: isProcessing ? 'pulse 1.5s ease-in-out infinite' : 'none'
          }}
          onMouseEnter={(e) => {
            if (!isProcessing && inputValue.trim()) {
              e.currentTarget.style.backgroundColor = 'rgba(0,0,0,0.05)';
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent';
          }}
        >
          {isProcessing ? '...' : '↵'}
        </button>
      </div>
    </div>
  );
}
