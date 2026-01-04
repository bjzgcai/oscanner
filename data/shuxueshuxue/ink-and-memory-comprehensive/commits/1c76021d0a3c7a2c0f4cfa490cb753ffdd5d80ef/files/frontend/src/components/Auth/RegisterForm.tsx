/**
 * Registration form component
 */

import React, { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';

interface RegisterFormProps {
  onSuccess: () => void;
  onSwitchToLogin: () => void;
}

export default function RegisterForm({ onSuccess, onSwitchToLogin }: RegisterFormProps) {
  const { register } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }

    setIsSubmitting(true);

    try {
      await register(email, password, displayName || undefined);
      onSuccess();
    } catch (err: any) {
      setError(err.message || 'Registration failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{
      width: '100%',
      maxWidth: '400px',
      margin: '0 auto',
      padding: '32px',
      backgroundColor: '#fffef9',
      border: '2px solid #d0c4b0',
      borderRadius: '12px',
      boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
      fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif"
    }}>
      <h2 style={{
        margin: '0 0 24px 0',
        fontSize: '24px',
        fontWeight: 600,
        color: '#333',
        textAlign: 'center'
      }}>
        Create Account
      </h2>

      {error && (
        <div style={{
          padding: '12px',
          marginBottom: '16px',
          backgroundColor: '#fee',
          border: '1px solid #fcc',
          borderRadius: '6px',
          fontSize: '14px',
          color: '#c33'
        }}>
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '16px' }}>
          <label style={{
            display: 'block',
            marginBottom: '6px',
            fontSize: '14px',
            fontWeight: 500,
            color: '#555'
          }}>
            Email
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            disabled={isSubmitting}
            style={{
              width: '100%',
              padding: '10px 12px',
              border: '1px solid #d0c4b0',
              borderRadius: '6px',
              fontSize: '15px',
              fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
              boxSizing: 'border-box'
            }}
          />
        </div>

        <div style={{ marginBottom: '16px' }}>
          <label style={{
            display: 'block',
            marginBottom: '6px',
            fontSize: '14px',
            fontWeight: 500,
            color: '#555'
          }}>
            Password
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            disabled={isSubmitting}
            style={{
              width: '100%',
              padding: '10px 12px',
              border: '1px solid #d0c4b0',
              borderRadius: '6px',
              fontSize: '15px',
              fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
              boxSizing: 'border-box'
            }}
          />
          <div style={{
            marginTop: '4px',
            fontSize: '12px',
            color: '#888'
          }}>
            At least 6 characters
          </div>
        </div>

        <div style={{ marginBottom: '24px' }}>
          <label style={{
            display: 'block',
            marginBottom: '6px',
            fontSize: '14px',
            fontWeight: 500,
            color: '#555'
          }}>
            Display Name (Optional)
          </label>
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            disabled={isSubmitting}
            style={{
              width: '100%',
              padding: '10px 12px',
              border: '1px solid #d0c4b0',
              borderRadius: '6px',
              fontSize: '15px',
              fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
              boxSizing: 'border-box'
            }}
          />
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          style={{
            width: '100%',
            padding: '12px',
            border: 'none',
            borderRadius: '6px',
            backgroundColor: isSubmitting ? '#ccc' : '#4a90e2',
            color: 'white',
            fontSize: '16px',
            fontWeight: 600,
            cursor: isSubmitting ? 'not-allowed' : 'pointer',
            fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
            transition: 'background-color 0.2s'
          }}
          onMouseEnter={(e) => {
            if (!isSubmitting) {
              e.currentTarget.style.backgroundColor = '#357abd';
            }
          }}
          onMouseLeave={(e) => {
            if (!isSubmitting) {
              e.currentTarget.style.backgroundColor = '#4a90e2';
            }
          }}
        >
          {isSubmitting ? 'Creating account...' : 'Register'}
        </button>
      </form>

      <div style={{
        marginTop: '20px',
        textAlign: 'center',
        fontSize: '14px',
        color: '#666'
      }}>
        Already have an account?{' '}
        <button
          onClick={onSwitchToLogin}
          disabled={isSubmitting}
          style={{
            background: 'none',
            border: 'none',
            color: '#4a90e2',
            cursor: 'pointer',
            textDecoration: 'underline',
            fontSize: '14px',
            fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif"
          }}
        >
          Login
        </button>
      </div>
    </div>
  );
}
