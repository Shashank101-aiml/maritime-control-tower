import React, { useState } from 'react';
import { Anchor, LogIn, AlertTriangle } from 'lucide-react';
import { login } from '../services/authService';

export default function Login({ onSignedIn }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const user = await login(username.trim(), password);
      onSignedIn(user);
    } catch (err) {
      setError(err.message || 'Sign in failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-screen">
      <form className="login-card" onSubmit={handleSubmit}>
        <div className="login-brand">
          <Anchor size={22} strokeWidth={2.2} color="var(--primary)" />
          <div>
            <div className="brand-title">Maritime Control</div>
            <div className="brand-sub">Agentic fleet &amp; logistics intelligence</div>
          </div>
        </div>

        <h1 className="login-title">Sign in</h1>
        <p className="login-sub">
          The control tower requires an account. Agent approvals and vessel data are not public.
        </p>

        <div className="form-group">
          <label className="form-label" htmlFor="username">Username or email</label>
          <input
            id="username"
            className="form-input"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            autoFocus
            required
          />
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="password">Password</label>
          <input
            id="password"
            className="form-input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </div>

        {error && (
          <div className="login-error">
            <AlertTriangle size={15} /> {error}
          </div>
        )}

        <button className="btn-action login-submit" type="submit" disabled={busy}>
          <LogIn size={15} />
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  );
}
