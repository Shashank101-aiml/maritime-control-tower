import React from 'react';
import { AlertTriangle, ShieldAlert, X, Navigation } from 'lucide-react';

export default function AlertBanner({ alert, onDismiss, onAction }) {
  if (!alert) return null;

  const isCritical = alert.severity === 'CRITICAL' || alert.severity === 'HIGH';
  const accent = isCritical ? 'var(--danger)' : 'var(--warning)';
  const Icon = isCritical ? ShieldAlert : AlertTriangle;

  return (
    <div className={`alert-banner ${isCritical ? '' : 'warning'}`}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: 0 }}>
        <Icon size={18} color={accent} style={{ flexShrink: 0 }} />
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--text-strong)' }}>
            <span style={{ color: accent, textTransform: 'uppercase', letterSpacing: '0.04em', fontSize: '0.72rem', marginRight: '8px' }}>
              {alert.severity}
            </span>
            {alert.event_type}
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-subtle)', marginTop: '1px' }}>
            {alert.location}
            {alert.vessel_id ? ` · Vessel ${alert.vessel_id}` : ' · Fleet corridor'}
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
        {onAction && (
          <button className="btn-secondary" onClick={onAction}>
            <Navigation size={14} /> View route options
          </button>
        )}
        <button
          onClick={onDismiss}
          title="Dismiss"
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--text-subtle)',
            cursor: 'pointer',
            padding: '4px',
            display: 'flex',
            alignItems: 'center',
            borderRadius: 'var(--radius-sm)',
          }}
        >
          <X size={16} />
        </button>
      </div>
    </div>
  );
}
