import { Node, mergeAttributes } from '@tiptap/core';
import { ReactNodeViewRenderer, NodeViewWrapper } from '@tiptap/react';
import { Node as ProseMirrorNode } from '@tiptap/pm/model';
import { useState, useEffect } from 'react';
import { DocumentStorage } from '../utils/documentStorage';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}

// @@@ Singleton storage instance
const storage = new DocumentStorage();

// @@@ React component for rendering the quote widget with chat
function VoiceQuoteView({ node, deleteNode, editor }: { node: ProseMirrorNode; deleteNode: () => void; editor: any }) {
  const { voiceName, comment, timestamp, widgetId } = node.attrs;
  const [isHovered, setIsHovered] = useState(false);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // @@@ Load conversation from storage, or initialize with first message
  const [messages, setMessages] = useState<Message[]>(() => {
    const saved = storage.getConversation(widgetId);
    return saved.length > 0 ? saved : [{ role: 'assistant', content: comment, timestamp }];
  });

  // @@@ Save conversation whenever messages change
  useEffect(() => {
    if (messages.length > 0) {
      storage.updateConversation(widgetId, messages);
    }
  }, [messages, widgetId]);

  const handleSendMessage = async () => {
    if (!inputText.trim() || isLoading) return;

    const userMessage: Message = {
      role: 'user',
      content: inputText,
      timestamp: Date.now()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputText('');
    setIsLoading(true);

    try {
      // @@@ Call backend chat API with full conversation history
      const { chatWithVoice } = await import('../api/voiceApi');

      // @@@ Get voice config from node attrs (stored when widget created)
      // Ensure it's an object (not string due to serialization)
      let voiceConfig = node.attrs.voiceConfig;
      if (typeof voiceConfig === 'string') {
        try {
          voiceConfig = JSON.parse(voiceConfig);
        } catch (e) {
          voiceConfig = { tagline: `${voiceName} voice from Disco Elysium` };
        }
      } else if (!voiceConfig || typeof voiceConfig !== 'object') {
        voiceConfig = { tagline: `${voiceName} voice from Disco Elysium` };
      }

      // @@@ Extract writing area text (exclude voice quote widgets)
      let writingAreaText = '';
      if (editor) {
        editor.state.doc.descendants((node: any) => {
          // Skip voice quote nodes
          if (node.type.name === 'voiceQuote') {
            return false;
          }
          // Collect text from other nodes
          if (node.isText) {
            writingAreaText += node.text;
          }
          return true;
        });
      }

      // Send entire conversation history + writing area text for context
      const response = await chatWithVoice(
        voiceName,
        voiceConfig,
        messages,
        inputText,
        writingAreaText
      );

      const assistantMessage: Message = {
        role: 'assistant',
        content: response,
        timestamp: Date.now()
      };
      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Chat error:', error);
      const errorMessage: Message = {
        role: 'assistant',
        content: `Sorry, I couldn't respond. (${error})`,
        timestamp: Date.now()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <NodeViewWrapper className="voice-quote-widget">
      <div
        contentEditable={false}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        style={{
          background: 'linear-gradient(135deg, rgba(255, 248, 240, 0.95), rgba(255, 250, 245, 0.95))',
          border: '1px solid #d0c4b0',
          borderRadius: 12,
          padding: '16px 20px',
          margin: '16px 0',
          fontFamily: 'Georgia, "Times New Roman", serif',
          fontSize: 16,
          lineHeight: 1.8,
          position: 'relative',
          cursor: 'default',
          userSelect: 'none',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.05)',
          transition: 'all 0.2s'
        }}
      >
        {/* Delete button - only visible on hover */}
        {isHovered && (
          <button
            onClick={deleteNode}
            style={{
              position: 'absolute',
              top: 12,
              right: 12,
              width: 24,
              height: 24,
              borderRadius: 12,
              border: '1px solid #d0c4b0',
              background: '#fff',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 16,
              color: '#666',
              padding: 0,
              transition: 'all 0.2s',
              boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)',
              zIndex: 10
            }}
            onMouseEnter={e => {
              e.currentTarget.style.background = '#f0e6d8';
              e.currentTarget.style.color = '#c33';
              e.currentTarget.style.borderColor = '#c33';
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = '#fff';
              e.currentTarget.style.color = '#666';
              e.currentTarget.style.borderColor = '#d0c4b0';
            }}
            title="Delete quote"
          >
            ×
          </button>
        )}

        <div
          style={{
            fontWeight: 600,
            color: '#2c2c2c',
            marginBottom: 8,
            fontSize: 15,
            paddingRight: isHovered ? 32 : 0,
            transition: 'padding-right 0.2s',
            letterSpacing: '0.3px'
          }}
        >
          {voiceName}
        </div>

        {/* Initial comment (always visible) */}
        <div
          style={{
            color: '#444',
            fontStyle: 'italic',
            fontSize: 16
          }}
        >
          "{comment}"
        </div>

        {timestamp && (
          <div
            style={{
              fontSize: 12,
              color: '#999',
              marginTop: 8,
              fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
            }}
          >
            {new Date(timestamp).toLocaleTimeString()}
          </div>
        )}

        {/* Chat messages - appear naturally after initial comment */}
        {messages.slice(1).map((msg, idx) => (
          <div
            key={idx}
            style={{
              marginTop: 16,
              color: msg.role === 'user' ? '#555' : '#444',
              fontSize: 15,
              fontFamily: msg.role === 'user'
                ? '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
                : 'Georgia, "Times New Roman", serif',
              fontStyle: msg.role === 'assistant' ? 'italic' : 'normal',
              paddingLeft: msg.role === 'user' ? 20 : 0,
              borderLeft: msg.role === 'user' ? '2px solid #d0c4b0' : 'none'
            }}
          >
            {msg.role === 'user' && <span style={{ fontWeight: 500, color: '#888' }}>You: </span>}
            {msg.content}
          </div>
        ))}

        {isLoading && (
          <div
            style={{
              marginTop: 16,
              color: '#999',
              fontSize: 15,
              fontFamily: 'Georgia, "Times New Roman", serif',
              fontStyle: 'italic'
            }}
          >
            Thinking...
          </div>
        )}

        {/* Input area */}
        <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Reply..."
              disabled={isLoading}
              style={{
                flex: 1,
                padding: '8px 12px',
                fontSize: 14,
                fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                background: 'transparent',
                border: 'none',
                borderBottom: '1px solid #d0c4b0',
                borderRadius: 0,
                outline: 'none',
                color: '#2c2c2c'
              }}
            />
            <button
              onClick={handleSendMessage}
              disabled={!inputText.trim() || isLoading}
              style={{
                padding: '6px 14px',
                fontSize: 13,
                fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                background: 'transparent',
                border: 'none',
                borderRadius: 0,
                cursor: inputText.trim() && !isLoading ? 'pointer' : 'not-allowed',
                color: inputText.trim() && !isLoading ? '#4CAF50' : '#ccc',
                fontWeight: 500,
                transition: 'all 0.2s'
              }}
              onMouseEnter={e => {
                if (inputText.trim() && !isLoading) {
                  e.currentTarget.style.color = '#45a049';
                }
              }}
              onMouseLeave={e => {
                if (inputText.trim() && !isLoading) {
                  e.currentTarget.style.color = '#4CAF50';
                }
              }}
            >
              →
            </button>
        </div>
      </div>
    </NodeViewWrapper>
  );
}

// @@@ Custom TipTap node for voice quotes - atomic and uneditable
export const VoiceQuote = Node.create({
  name: 'voiceQuote',

  group: 'block',

  atom: true, // Makes it atomic - can't edit inside, only delete whole thing

  selectable: false, // Cannot be selected, prevents replacement when typing

  draggable: false, // Disable drag to prevent accidental moves

  addAttributes() {
    return {
      widgetId: {
        default: '',
      },
      voiceName: {
        default: '',
      },
      comment: {
        default: '',
      },
      timestamp: {
        default: null,
      },
      voiceConfig: {
        default: {},
      },
    };
  },

  parseHTML() {
    return [
      {
        tag: 'div[data-type="voice-quote"]',
      },
    ];
  },

  renderHTML({ node, HTMLAttributes }) {
    // Render as a self-contained div with data attributes
    return ['div', mergeAttributes(HTMLAttributes, {
      'data-type': 'voice-quote',
      'data-voice-name': node.attrs.voiceName,
      'data-comment': node.attrs.comment,
      'data-timestamp': node.attrs.timestamp
    })];
  },

  addNodeView() {
    return ReactNodeViewRenderer(VoiceQuoteView);
  },
});

export default VoiceQuote;
