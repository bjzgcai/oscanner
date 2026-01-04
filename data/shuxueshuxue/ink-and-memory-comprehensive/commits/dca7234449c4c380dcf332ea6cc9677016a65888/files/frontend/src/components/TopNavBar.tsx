import { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';

interface Props {
  currentView: 'writing' | 'settings' | 'timeline' | 'analysis' | 'decks';
  onViewChange: (view: 'writing' | 'settings' | 'timeline' | 'analysis' | 'decks') => void;
}

export default function LeftSidebar({ currentView, onViewChange }: Props) {
  const { user, logout } = useAuth();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const buttonStyle = (isActive: boolean) => ({
    height: '100%',
    padding: '0 20px',
    border: 'none',
    background: isActive ? 'rgba(44, 44, 44, 0.08)' : 'transparent',
    fontSize: 14,
    fontWeight: isActive ? 600 : 400,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'all 0.2s',
    color: isActive ? '#2c2c2c' : '#888',
    position: 'relative' as const,
    borderBottom: isActive ? '3px solid #2c2c2c' : '3px solid transparent',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    letterSpacing: '-0.2px'
  });

  return (
    <div style={{
      position: 'fixed',
      left: 0,
      top: 0,
      right: 0,
      height: 48,
      background: '#f8f0e6',
      borderBottom: '1px solid #d0c4b0',
      display: 'flex',
      flexDirection: 'row',
      alignItems: 'center',
      padding: '0 24px',
      gap: 8,
      zIndex: 999
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        marginRight: 40,
        fontSize: 17,
        fontFamily: 'Georgia, "Times New Roman", serif',
        letterSpacing: '-0.2px'
      }}>
        <span style={{
          fontSize: 20,
          fontWeight: 700,
          color: '#2c2c2c',
          fontStyle: 'italic'
        }}>I</span>
        <span style={{
          fontWeight: 400,
          color: '#2c2c2c'
        }}>nk & </span>
        <span style={{
          fontSize: 20,
          fontWeight: 700,
          color: '#2c2c2c',
          fontStyle: 'italic'
        }}>M</span>
        <span style={{
          fontWeight: 400,
          color: '#2c2c2c'
        }}>emory</span>
      </div>

      <div style={{
        display: 'flex',
        height: '100%',
        gap: 0
      }}>
        <button
          onClick={() => onViewChange('writing')}
          style={buttonStyle(currentView === 'writing')}
          title="Writing"
          onMouseEnter={e => {
            if (currentView !== 'writing') {
              e.currentTarget.style.background = 'rgba(44, 44, 44, 0.04)';
            }
          }}
          onMouseLeave={e => {
            if (currentView !== 'writing') {
              e.currentTarget.style.background = 'transparent';
            }
          }}
        >
          Writing
        </button>

        <button
          onClick={() => onViewChange('timeline')}
          style={buttonStyle(currentView === 'timeline')}
          title="Timeline"
          onMouseEnter={e => {
            if (currentView !== 'timeline') {
              e.currentTarget.style.background = 'rgba(44, 44, 44, 0.04)';
            }
          }}
          onMouseLeave={e => {
            if (currentView !== 'timeline') {
              e.currentTarget.style.background = 'transparent';
            }
          }}
        >
          Timeline
        </button>

        <button
          onClick={() => onViewChange('analysis')}
          style={buttonStyle(currentView === 'analysis')}
          title="Reflections"
          onMouseEnter={e => {
            if (currentView !== 'analysis') {
              e.currentTarget.style.background = 'rgba(44, 44, 44, 0.04)';
            }
          }}
          onMouseLeave={e => {
            if (currentView !== 'analysis') {
              e.currentTarget.style.background = 'transparent';
            }
          }}
        >
          Reflections
        </button>

        <button
          onClick={() => onViewChange('decks')}
          style={buttonStyle(currentView === 'decks')}
          title="Decks"
          onMouseEnter={e => {
            if (currentView !== 'decks') {
              e.currentTarget.style.background = 'rgba(44, 44, 44, 0.04)';
            }
          }}
          onMouseLeave={e => {
            if (currentView !== 'decks') {
              e.currentTarget.style.background = 'transparent';
            }
          }}
        >
          Decks
        </button>
      </div>

      <div style={{ flex: 1 }} />

      <button
        onClick={() => onViewChange('settings')}
        style={{
          width: 28,
          height: 28,
          borderRadius: 6,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: currentView === 'settings' ? 'rgba(0, 0, 0, 0.08)' : 'transparent',
          border: 'none',
          cursor: 'pointer',
          transition: 'all 0.2s',
          color: '#666',
          fontSize: 16
        }}
        onMouseEnter={e => {
          if (currentView !== 'settings') {
            e.currentTarget.style.background = 'rgba(0, 0, 0, 0.05)';
          }
        }}
        onMouseLeave={e => {
          if (currentView !== 'settings') {
            e.currentTarget.style.background = 'transparent';
          }
        }}
        title="Settings"
      >
        <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor">
          <path d="M17.502 10c0 .34-.03.66-.07.98l2.11 1.65c.19.15.24.42.12.64l-2 3.46c-.12.22-.39.3-.61.22l-2.49-1c-.52.4-1.08.73-1.69.98l-.38 2.65c-.03.24-.24.42-.49.42h-4c-.25 0-.46-.18-.49-.42l-.38-2.65c-.61-.25-1.17-.59-1.69-.98l-2.49 1c-.23.09-.49 0-.61-.22l-2-3.46c-.13-.22-.07-.49.12-.64l2.11-1.65c-.04-.32-.07-.65-.07-.98 0-.33.03-.66.07-.98L.93 7.37c-.19-.15-.24-.42-.12-.64l2-3.46c.12-.22.39-.3.61-.22l2.49 1c.52-.4 1.08-.73 1.69-.98l.38-2.65C7.01.18 7.22 0 7.47 0h4c.25 0 .46.18.49.42l.38 2.65c.61.25 1.17.59 1.69.98l2.49-1c.23-.09.49 0 .61.22l2 3.46c.12.22.07.49-.12.64l-2.11 1.65c.04.32.07.65.07.98zm-7.5 3c1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3 1.34 3 3 3z"/>
        </svg>
      </button>

      <div style={{ position: 'relative' }}>
        <button
          onClick={() => setShowUserMenu(!showUserMenu)}
          style={{
            width: 28,
            height: 28,
            borderRadius: 14,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: '#4CAF50',
            border: 'none',
            cursor: 'pointer',
            transition: 'all 0.2s',
            color: '#fff',
            fontSize: 12,
            fontWeight: 600,
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
          }}
          onMouseEnter={e => {
            e.currentTarget.style.background = '#45a049';
          }}
          onMouseLeave={e => {
            e.currentTarget.style.background = '#4CAF50';
          }}
          title="User Profile"
        >
          {user?.display_name?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || 'U'}
        </button>

        {showUserMenu && (
          <>
            <div
              style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                zIndex: 998
              }}
              onClick={() => setShowUserMenu(false)}
            />
            <div style={{
              position: 'absolute',
              top: '100%',
              right: 0,
              marginTop: 8,
              width: 200,
              background: '#fff',
              border: '1px solid #d0c4b0',
              borderRadius: 8,
              boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
              zIndex: 999,
              overflow: 'hidden'
            }}>
              <div style={{
                padding: '12px 16px',
                borderBottom: '1px solid #e8e8e8',
                fontSize: 13
              }}>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>
                  {user?.display_name || 'User'}
                </div>
                <div style={{ fontSize: 11, color: '#666' }}>
                  {user?.email}
                </div>
              </div>
              <button
                onClick={() => {
                  logout();
                  setShowUserMenu(false);
                }}
                style={{
                  width: '100%',
                  padding: '10px 16px',
                  border: 'none',
                  background: 'transparent',
                  textAlign: 'left',
                  fontSize: 13,
                  cursor: 'pointer',
                  transition: 'background 0.2s',
                  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto'
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.background = '#f5f5f5';
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.background = 'transparent';
                }}
              >
                Logout
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
