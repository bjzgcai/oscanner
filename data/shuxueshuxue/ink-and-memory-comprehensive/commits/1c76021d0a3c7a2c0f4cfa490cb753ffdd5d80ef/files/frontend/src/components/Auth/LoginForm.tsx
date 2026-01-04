/**
 * Login form component
 */

import React, { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';

interface LoginFormProps {
  onSuccess: () => void;
  onSwitchToRegister: () => void;
}

export default function LoginForm({ onSuccess, onSwitchToRegister }: LoginFormProps) {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);

    try {
      await login(email, password);
      onSuccess();
    } catch (err: any) {
      setError(err.message || 'Login failed');
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
        Welcome Back
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

        <div style={{ marginBottom: '24px' }}>
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
          {isSubmitting ? 'Logging in...' : 'Login'}
        </button>
      </form>

      <div style={{
        marginTop: '20px',
        textAlign: 'center',
        fontSize: '14px',
        color: '#666'
      }}>
        Don't have an account?{' '}
        <button
          onClick={onSwitchToRegister}
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
          Register
        </button>
      </div>
    </div>
  );
}
