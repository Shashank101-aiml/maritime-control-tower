import React, { useState } from 'react';
import { Settings as SettingsIcon, Save, ShieldCheck, Database, Sliders, Bell, CheckCircle2 } from 'lucide-react';
import { API_BASE_URL } from '../config';

export default function Settings() {
  const [apiEndpoint, setApiEndpoint] = useState(API_BASE_URL);
  const [pollingInterval, setPollingInterval] = useState('15');
  const [riskThreshold, setRiskThreshold] = useState('50');
  const [simMode, setSimMode] = useState(true);
  const [autoReroute, setAutoReroute] = useState(true);
  const [notifSound, setNotifSound] = useState(true);
  const [saved, setSaved] = useState(false);

  const handleSave = (e) => {
    e.preventDefault();
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  return (
    <div className="page-wrapper" style={{ maxWidth: '1000px', margin: '0 auto' }}>
      <div className="section-header" style={{ marginBottom: '28px' }}>
        <div>
          <h1 className="section-title" style={{ fontSize: '1.8rem', color: 'var(--text-strong)' }}>
            <SettingsIcon size={28} color="var(--accent-cyan)" />
            System Configuration & AI Guardrails
          </h1>
          <p style={{ color: 'var(--text-muted)', marginTop: '4px' }}>
            Adjust telemetry streaming rates, autonomous agent confidence thresholds, and backend API connections.
          </p>
        </div>

        <button className="btn-action" onClick={handleSave}>
          {saved ? <CheckCircle2 size={18} /> : <Save size={18} />}
          {saved ? 'Settings Saved!' : 'Save Configurations'}
        </button>
      </div>

      <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {/* Backend Connection */}
        <div className="glass-panel" style={{ padding: '24px' }}>
          <h3 className="section-title" style={{ fontSize: '1.15rem', marginBottom: '16px' }}>
            <Database size={20} color="var(--accent-teal)" />
            FastAPI Backend & Connection
          </h3>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '16px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '6px' }}>
                API Base URL Endpoint
              </label>
              <input 
                type="text" 
                value={apiEndpoint} 
                onChange={(e) => setApiEndpoint(e.target.value)}
                style={{
                  width: '100%',
                  background: 'var(--surface-subtle)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '8px',
                  padding: '12px 16px',
                  color: 'var(--text-strong)',
                  fontFamily: 'var(--font-body)'
                }}
              />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'var(--surface-subtle)', padding: '14px 18px', borderRadius: '10px' }}>
              <div>
                <div style={{ fontWeight: 600, color: 'var(--text-strong)' }}>Autonomous Simulation Fallback Mode</div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                  Automatically generate realistic telemetry and multi-agent AI reasoning if local FastAPI backend goes offline.
                </div>
              </div>
              <input 
                type="checkbox" 
                checked={simMode} 
                onChange={(e) => setSimMode(e.target.checked)} 
                style={{ width: '20px', height: '20px', cursor: 'pointer', accentColor: 'var(--accent-cyan)' }}
              />
            </div>
          </div>
        </div>

        {/* AI Orchestration & Guardrails */}
        <div className="glass-panel" style={{ padding: '24px' }}>
          <h3 className="section-title" style={{ fontSize: '1.15rem', marginBottom: '16px' }}>
            <Sliders size={20} color="var(--accent-amber)" />
            Agentic AI & Hazard Guardrails
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
            <div>
              <label style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '8px' }}>
                <span>Telemetry Ingestion Polling Rate (seconds)</span>
                <strong style={{ color: 'var(--text-strong)' }}>{pollingInterval}s</strong>
              </label>
              <input 
                type="range" 
                min="5" 
                max="60" 
                step="5"
                value={pollingInterval} 
                onChange={(e) => setPollingInterval(e.target.value)}
                style={{ width: '100%', accentColor: 'var(--accent-cyan)', cursor: 'pointer' }}
              />
            </div>

            <div>
              <label style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '8px' }}>
                <span>Critical Risk Alert Sensitivity Threshold (0-100)</span>
                <strong style={{ color: 'var(--accent-rose)' }}>{riskThreshold}/100</strong>
              </label>
              <input 
                type="range" 
                min="20" 
                max="80" 
                step="5"
                value={riskThreshold} 
                onChange={(e) => setRiskThreshold(e.target.value)}
                style={{ width: '100%', accentColor: 'var(--accent-rose)', cursor: 'pointer' }}
              />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'var(--surface-subtle)', padding: '14px 18px', borderRadius: '10px' }}>
              <div>
                <div style={{ fontWeight: 600, color: 'var(--text-strong)' }}>Autonomous Waypoint Rerouting (Route Optimization Agent)</div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                  Allow AI to automatically suggest and queue waypoint detours when corridor hazard score exceeds threshold.
                </div>
              </div>
              <input 
                type="checkbox" 
                checked={autoReroute} 
                onChange={(e) => setAutoReroute(e.target.checked)} 
                style={{ width: '20px', height: '20px', cursor: 'pointer', accentColor: 'var(--accent-cyan)' }}
              />
            </div>
          </div>
        </div>

        {/* Notifications & Security */}
        <div className="glass-panel" style={{ padding: '24px' }}>
          <h3 className="section-title" style={{ fontSize: '1.15rem', marginBottom: '16px' }}>
            <Bell size={20} color="var(--accent-rose)" />
            Alerts & Audio Notifications
          </h3>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'var(--surface-subtle)', padding: '14px 18px', borderRadius: '10px' }}>
            <div>
              <div style={{ fontWeight: 600, color: 'var(--text-strong)' }}>Audio Alarm on Critical Hazard Ingestion</div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                Play sonar chime when severe storm cells or piracy activities are detected in active fleet corridors.
              </div>
            </div>
            <input 
              type="checkbox" 
              checked={notifSound} 
              onChange={(e) => setNotifSound(e.target.checked)} 
              style={{ width: '20px', height: '20px', cursor: 'pointer', accentColor: 'var(--accent-rose)' }}
            />
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '10px' }}>
          <button type="submit" className="btn-action" style={{ padding: '14px 32px', fontSize: '1rem' }}>
            {saved ? <CheckCircle2 size={20} /> : <Save size={20} />}
            {saved ? 'Configurations Saved!' : 'Save System Settings'}
          </button>
        </div>
      </form>
    </div>
  );
}
