import React, { useCallback, useEffect, useState } from 'react';
import { Users, UserPlus, KeyRound, AlertCircle, CheckCircle } from 'lucide-react';
import { listUsers, createUser, updateUser, resetUserPassword } from '../services/userService';
import { ROLES, ROLE_LABELS, ROLE_DESCRIPTIONS, roleOf } from '../utils/permissions';
import LoadingSpinner from '../components/LoadingSpinner';

const EMPTY_FORM = { username: '', email: '', full_name: '', password: '', role: 'operator' };

const cell = { padding: '12px 8px', verticalAlign: 'middle' };
const label = { display: 'block', fontSize: '0.78rem', color: 'var(--text-subtle)', marginBottom: '6px' };

export default function UserManagement({ currentUser }) {
  const [users, setUsers] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [creating, setCreating] = useState(false);
  const [notice, setNotice] = useState(null); // { kind: 'ok' | 'error', text }
  const [resetting, setResetting] = useState(null); // user id whose reset row is open
  const [newPassword, setNewPassword] = useState('');

  const load = useCallback(async () => {
    try {
      setUsers(await listUsers());
      setLoadError(null);
    } catch (err) {
      setLoadError(err.message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const run = async (action, successText) => {
    setNotice(null);
    try {
      await action();
      setNotice({ kind: 'ok', text: successText });
      await load();
      return true;
    } catch (err) {
      setNotice({ kind: 'error', text: err.message });
      return false;
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setCreating(true);
    const ok = await run(
      () => createUser({ ...form, full_name: form.full_name || null }),
      `Created ${form.username} as ${ROLE_LABELS[form.role]}.`,
    );
    setCreating(false);
    if (ok) setForm(EMPTY_FORM);
  };

  const handleReset = async (user) => {
    const ok = await run(
      () => resetUserPassword(user.id, newPassword),
      `Password reset for ${user.username}.`,
    );
    if (ok) { setResetting(null); setNewPassword(''); }
  };

  if (loadError && !users) {
    return (
      <div className="page-wrapper">
        <div className="glass-panel" style={{ textAlign: 'center', padding: '40px', borderColor: 'var(--accent-rose)' }}>
          <AlertCircle size={36} color="var(--accent-rose)" style={{ margin: '0 auto 12px' }} />
          <p style={{ color: 'var(--text-main)' }}>{loadError}</p>
        </div>
      </div>
    );
  }
  if (!users) return <LoadingSpinner message="Loading users…" />;

  return (
    <div className="page-wrapper">
      <div className="section-header" style={{ marginBottom: '24px' }}>
        <div>
          <h1 className="section-title" style={{ fontSize: '1.8rem', color: 'var(--text-strong)' }}>
            <Users size={28} color="var(--accent-teal)" />
            User Management
          </h1>
          <p style={{ color: 'var(--text-muted)', marginTop: '4px' }}>
            Create accounts and set what each person can do. Every change is written to the audit log.
          </p>
        </div>
      </div>

      {notice && (
        <div
          className="glass-panel"
          role={notice.kind === 'error' ? 'alert' : 'status'}
          style={{
            padding: '12px 16px', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '10px',
            borderColor: notice.kind === 'error' ? 'var(--accent-rose)' : 'var(--accent-emerald)',
          }}
        >
          {notice.kind === 'error'
            ? <AlertCircle size={18} color="var(--accent-rose)" />
            : <CheckCircle size={18} color="var(--accent-emerald)" />}
          <span style={{ color: 'var(--text-main)', fontSize: '0.9rem' }}>{notice.text}</span>
        </div>
      )}

      <div className="panel" style={{ marginBottom: '20px' }}>
        <div className="section-header">
          <h3 className="section-title"><UserPlus size={17} /> Add a user</h3>
        </div>
        <form onSubmit={handleCreate}>
          <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <div>
              <label htmlFor="new-username" style={label}>Username</label>
              <input id="new-username" className="form-input" required minLength={3} pattern="[A-Za-z0-9_.\-]+"
                title="Letters, numbers, dots, dashes and underscores" autoComplete="off"
                value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
            </div>
            <div>
              <label htmlFor="new-email" style={label}>Email</label>
              <input id="new-email" className="form-input" type="email" required autoComplete="off"
                value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            </div>
            <div>
              <label htmlFor="new-name" style={label}>Full name (optional)</label>
              <input id="new-name" className="form-input" autoComplete="off"
                value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
            </div>
            <div>
              <label htmlFor="new-password" style={label}>Temporary password (min 8)</label>
              <input id="new-password" className="form-input" type="password" required minLength={8} autoComplete="new-password"
                value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
            </div>
            <div>
              <label htmlFor="new-role" style={label}>Role</label>
              <select id="new-role" className="form-input" value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value })}>
                {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
              </select>
            </div>
            <button className="btn-action" type="submit" disabled={creating}>
              <UserPlus size={16} /> {creating ? 'Creating…' : 'Create user'}
            </button>
          </div>
          <p className="form-note" style={{ marginTop: '10px' }}>{ROLE_DESCRIPTIONS[form.role]}</p>
        </form>
      </div>

      <div className="panel">
        <div className="section-header">
          <h3 className="section-title">Accounts ({users.length})</h3>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', color: 'var(--text-light)' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-light)', textAlign: 'left', color: 'var(--text-muted)', fontSize: '0.8rem', textTransform: 'uppercase' }}>
                <th style={cell}>User</th>
                <th style={cell}>Role</th>
                <th style={cell}>Status</th>
                <th style={cell}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const isSelf = u.id === currentUser?.id;
                return (
                  <React.Fragment key={u.id}>
                    <tr style={{ borderBottom: '1px solid var(--border-light)' }}>
                      <td style={cell}>
                        <div style={{ fontWeight: 'bold', color: 'var(--text-strong)' }}>
                          {u.username}{isSelf ? ' (you)' : ''}
                        </div>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                          {u.full_name ? `${u.full_name} · ` : ''}{u.email}
                        </div>
                      </td>
                      <td style={cell}>
                        <select
                          className="form-input"
                          aria-label={`Role for ${u.username}`}
                          value={roleOf(u)}
                          disabled={isSelf}
                          title={isSelf ? 'You cannot change your own role' : ROLE_DESCRIPTIONS[roleOf(u)]}
                          onChange={(e) => run(
                            () => updateUser(u.id, { role: e.target.value }),
                            `${u.username} is now ${ROLE_LABELS[e.target.value]}.`,
                          )}
                        >
                          {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
                        </select>
                      </td>
                      <td style={cell}>
                        <span className="status-badge" style={u.is_active ? undefined : {
                          background: 'var(--surface-sunken)', borderColor: 'var(--border-strong)', color: 'var(--text-subtle)',
                        }}>
                          {u.is_active ? 'Active' : 'Deactivated'}
                        </span>
                      </td>
                      <td style={cell}>
                        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                          <button
                            className="btn-secondary"
                            style={{ fontSize: '0.78rem' }}
                            disabled={isSelf}
                            title={isSelf ? 'You cannot deactivate yourself' : undefined}
                            onClick={() => run(
                              () => updateUser(u.id, { is_active: !u.is_active }),
                              `${u.username} ${u.is_active ? 'deactivated' : 'reactivated'}.`,
                            )}
                          >
                            {u.is_active ? 'Deactivate' : 'Reactivate'}
                          </button>
                          <button
                            className="btn-secondary"
                            style={{ fontSize: '0.78rem' }}
                            onClick={() => { setResetting(resetting === u.id ? null : u.id); setNewPassword(''); }}
                          >
                            <KeyRound size={13} /> Reset password
                          </button>
                        </div>
                      </td>
                    </tr>
                    {resetting === u.id && (
                      <tr style={{ borderBottom: '1px solid var(--border-light)' }}>
                        <td colSpan={4} style={cell}>
                          <form
                            style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}
                            onSubmit={(e) => { e.preventDefault(); handleReset(u); }}
                          >
                            <label htmlFor={`reset-${u.id}`} style={{ ...label, margin: 0 }}>
                              New password for {u.username}
                            </label>
                            <input id={`reset-${u.id}`} className="form-input" type="password" required minLength={8}
                              autoComplete="new-password" value={newPassword}
                              onChange={(e) => setNewPassword(e.target.value)} />
                            <button className="btn-action" type="submit">Set password</button>
                            <button className="btn-secondary" type="button" onClick={() => setResetting(null)}>Cancel</button>
                          </form>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
