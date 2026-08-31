import React from 'react';
import { ShieldCheck, ShieldAlert, AlertTriangle, ArrowUpRight, CheckCircle2 } from 'lucide-react';
import { getRiskLevel } from '../types/Risk';

const TONES = {
  CRITICAL: { fg: 'var(--danger)', bg: 'var(--danger-soft)', border: 'var(--danger-border)' },
  ELEVATED: { fg: 'var(--warning)', bg: 'var(--warning-soft)', border: 'var(--warning-border)' },
  NORMAL: { fg: 'var(--success)', bg: 'var(--success-soft)', border: 'var(--success-border)' },
};

export default function RiskCard({ risk, onMitigate, mitigationActive }) {
  if (!risk) return null;

  const level = getRiskLevel(risk.risk_score);
  const isCritical = level === 'CRITICAL';
  const tone = TONES[level] || TONES.NORMAL;

  return (
    <div className="panel" style={{ borderColor: isCritical ? tone.border : 'var(--border)' }}>
      <div className="section-header">
        <div className="section-title">
          {isCritical
            ? <ShieldAlert size={17} color={tone.fg} />
            : <ShieldCheck size={17} color={tone.fg} />}
          {risk.category}
        </div>
        <span
          className="status-badge"
          style={{ background: tone.bg, borderColor: tone.border, color: tone.fg }}
        >
          {level} · {risk.risk_score}/100
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
        <div className="result-metric">
          <div className="result-metric-label">Impact severity</div>
          <div style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-strong)' }}>{risk.impact}</div>
        </div>
        <div className="result-metric">
          <div className="result-metric-label">Probability</div>
          <div style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-strong)' }}>{risk.likelihood}</div>
        </div>
      </div>

      <div style={{
        background: 'var(--surface-subtle)',
        border: '1px solid var(--border)',
        padding: '14px',
        borderRadius: 'var(--radius)',
        marginBottom: '16px'
      }}>
        <div style={{
          fontSize: '0.72rem',
          color: 'var(--text-subtle)',
          fontWeight: 600,
          marginBottom: '6px',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          textTransform: 'uppercase',
          letterSpacing: '0.05em'
        }}>
          <AlertTriangle size={13} /> Recommended mitigation
        </div>
        <p style={{ fontSize: '0.875rem', color: 'var(--text-body)', lineHeight: 1.5 }}>
          {risk.mitigation_plan}
        </p>
      </div>

      {onMitigate && (
        <button
          className={mitigationActive ? 'btn-secondary' : 'btn-action'}
          style={{ width: '100%', justifyContent: 'center' }}
          onClick={onMitigate}
          disabled={mitigationActive}
        >
          {mitigationActive ? (
            <>
              <CheckCircle2 size={15} color="var(--success)" /> Mitigation executed
            </>
          ) : (
            <>
              Execute reroute &amp; mitigation <ArrowUpRight size={15} />
            </>
          )}
        </button>
      )}
    </div>
  );
}
