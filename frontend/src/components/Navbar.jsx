import React, { useState, useEffect } from 'react';
import { Anchor, Clock, User as UserIcon, LogOut } from 'lucide-react';

const formatUtc = (date) =>
  date.toISOString().slice(0, 19).replace('T', ' ') + ' UTC';

export default function Navbar({ backendOnline, onBrandClick, user, onSignOut }) {
  const [time, setTime] = useState(() => formatUtc(new Date()));

  useEffect(() => {
    const timer = setInterval(() => setTime(formatUtc(new Date())), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className="navbar">
      <button
        className="brand"
        onClick={onBrandClick}
        title={onBrandClick ? 'Back to overview page' : undefined}
        style={{
          background: 'none',
          border: 'none',
          padding: 0,
          cursor: onBrandClick ? 'pointer' : 'default',
          textAlign: 'left',
          fontFamily: 'inherit',
        }}
      >
        <Anchor className="brand-icon" size={20} strokeWidth={2.2} />
        <div>
          <div className="brand-title">Maritime Control</div>
          <div className="brand-sub">Agentic fleet &amp; logistics intelligence</div>
        </div>
      </button>

      <div className="topbar-meta">
        <div className="clock">
          <Clock size={14} />
          <span>{time}</span>
        </div>

        <span
          className="status-badge"
          style={
            backendOnline
              ? undefined
              : {
                  background: 'var(--surface-sunken)',
                  borderColor: 'var(--border-strong)',
                  color: 'var(--text-subtle)',
                }
          }
        >
          <span className="pulse-dot" />
          {backendOnline ? 'Operational' : 'Offline'}
        </span>

        {user && (
          <button
            className="user-chip"
            onClick={onSignOut}
            title={`Signed in as ${user.username}${user.is_superuser ? ' (admin)' : ''} — click to sign out`}
          >
            <UserIcon size={13} />
            {user.username}
            <LogOut size={13} />
          </button>
        )}
      </div>
    </header>
  );
}
