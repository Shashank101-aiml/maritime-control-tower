import React from 'react';
import { Compass } from 'lucide-react';

export default function LoadingSpinner({ message = 'Synchronizing Maritime Telemetry...', size = 36 }) {
  return (
    <div style={{ 
      display: 'flex', 
      flexDirection: 'column', 
      alignItems: 'center', 
      justifyContent: 'center', 
      padding: '48px 20px',
      textAlign: 'center',
      gap: '16px'
    }}>
      <div style={{ position: 'relative', width: `${size * 1.5}px`, height: `${size * 1.5}px`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div 
          style={{
            position: 'absolute',
            width: '100%',
            height: '100%',
            border: '2px solid var(--primary-soft)',
            borderTopColor: 'var(--accent-cyan)',
            borderRadius: '50%',
            animation: 'spin 1.2s linear infinite',

          }}
        />
        <Compass size={size} color="var(--accent-cyan)" style={{ animation: 'pulse 2s infinite' }} />
      </div>
      
      <p style={{ 
        color: 'var(--text-muted)', 
        fontSize: '0.95rem', 
        fontFamily: 'var(--font-heading)',
        letterSpacing: '0.03em'
      }}>
        {message}
      </p>
    </div>
  );
}
