import React, { useState } from 'react';
import { Clock, AlertCircle } from 'lucide-react';

export default function DelayChart() {
  const [hoveredIndex, setHoveredIndex] = useState(null);

  const data = [
    { label: 'Port Singapore', delayHours: 14.5, reason: 'Congestion & Swell', severity: 'HIGH' },
    { label: 'Suez Canal North', delayHours: 4.2, reason: 'Routine Transit', severity: 'LOW' },
    { label: 'Strait of Malacca', delayHours: 8.8, reason: 'Anchor Queue', severity: 'MEDIUM' },
    { label: 'Gulf of Aden', delayHours: 18.0, reason: 'Security Convoy Wait', severity: 'HIGH' },
    { label: 'Strait of Hormuz', delayHours: 6.5, reason: 'Patrol Escort', severity: 'MEDIUM' },
    { label: 'Rotterdam Terminal', delayHours: 2.0, reason: 'Normal Operations', severity: 'LOW' }
  ];

  const maxHours = 20;

  return (
    <div className="glass-panel" style={{ padding: '24px' }}>
      <div className="section-header">
        <h3 className="section-title" style={{ fontSize: '1.15rem' }}>
          <Clock size={20} color="var(--accent-amber)" />
          Estimated Transit & Port Delays (Hours)
        </h3>
        <span className="status-badge" style={{ fontSize: '0.75rem', background: 'var(--warning-soft)', borderColor: 'var(--accent-amber)', color: 'var(--accent-amber)' }}>
          LIVE ESTIMATES
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', marginTop: '18px' }}>
        {data.map((item, i) => {
          const widthPct = (item.delayHours / maxHours) * 100;
          const color = item.severity === 'HIGH' ? 'var(--accent-rose)' : item.severity === 'MEDIUM' ? 'var(--accent-amber)' : 'var(--accent-cyan)';
          const isHovered = hoveredIndex === i;

          return (
            <div 
              key={item.label}
              onMouseEnter={() => setHoveredIndex(i)}
              onMouseLeave={() => setHoveredIndex(null)}
              style={{
                background: isHovered ? 'var(--surface-subtle)' : 'transparent',
                padding: '6px 10px',
                borderRadius: '8px',
                transition: 'background 0.2s ease'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontSize: '0.9rem' }}>
                <span style={{ fontWeight: 600, color: 'var(--text-strong)' }}>{item.label}</span>
                <span style={{ color, fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px' }}>
                  {item.delayHours} hrs
                  {item.severity === 'HIGH' && <AlertCircle size={14} />}
                </span>
              </div>

              <div style={{ width: '100%', height: '10px', background: 'var(--surface-subtle)', borderRadius: '5px', overflow: 'hidden', position: 'relative' }}>
                <div style={{
                  width: `${widthPct}%`,
                  height: '100%',
                  background: color,
                  borderRadius: '5px',
                  transition: 'width 0.6s cubic-bezier(0.16, 1, 0.3, 1)'
                }} />
              </div>

              {isHovered && (
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                  Primary Factor: <strong style={{ color: 'var(--text-strong)' }}>{item.reason}</strong>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
