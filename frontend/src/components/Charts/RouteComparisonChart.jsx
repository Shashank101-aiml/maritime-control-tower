import React from 'react';
import { Navigation, Fuel, ShieldCheck, Clock } from 'lucide-react';

export default function RouteComparisonChart() {
  const metrics = [
    { label: 'Hazard Safety Score (Higher is Safer)', std: 25, ai: 78, unit: '/100', icon: <ShieldCheck size={16} /> },
    { label: 'Fuel Efficiency (Tons Saved)', std: 0, ai: 15, unit: ' tons', icon: <Fuel size={16} /> },
    { label: 'Storm Detour Margin (Nautical Miles)', std: 0, ai: 120, unit: ' nm', icon: <Navigation size={16} /> },
    { label: 'On-Time Arrival Confidence', std: 45, ai: 92, unit: '%', icon: <Clock size={16} /> }
  ];

  return (
    <div className="glass-panel" style={{ padding: '24px' }}>
      <div className="section-header">
        <h3 className="section-title" style={{ fontSize: '1.15rem' }}>
          <Navigation size={20} color="var(--accent-teal)" />
          Standard Corridor vs. AI Recommended Corridor
        </h3>
        <div style={{ display: 'flex', gap: '16px', fontSize: '0.85rem' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-muted)' }}>
            <span style={{ width: '12px', height: '12px', background: 'var(--border-strong)', borderRadius: '3px', display: 'inline-block' }}></span>
            Corridor Alpha (Direct)
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--accent-cyan)', fontWeight: 700 }}>
            <span style={{ width: '12px', height: '12px', background: 'var(--accent-cyan)', borderRadius: '3px', display: 'inline-block' }}></span>
            Corridor Beta (AI Recommended)
          </span>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', marginTop: '24px' }}>
        {metrics.map((m, idx) => {
          const maxVal = Math.max(m.std, m.ai, 100);
          const stdPct = (m.std / maxVal) * 100;
          const aiPct = (m.ai / maxVal) * 100;

          return (
            <div key={idx} style={{ background: 'var(--surface-subtle)', padding: '14px 18px', borderRadius: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-strong)', marginBottom: '12px' }}>
                <span style={{ color: 'var(--accent-teal)' }}>{m.icon}</span>
                {m.label}
              </div>

              {/* Standard bar */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                <span style={{ width: '60px', fontSize: '0.75rem', color: 'var(--text-muted)' }}>Standard</span>
                <div style={{ flex: 1, height: '10px', background: 'var(--surface-subtle)', borderRadius: '5px', overflow: 'hidden' }}>
                  <div style={{ width: `${stdPct}%`, height: '100%', background: 'var(--border-strong)', borderRadius: '5px' }} />
                </div>
                <span style={{ width: '70px', textAlign: 'right', fontSize: '0.85rem', color: 'var(--text-muted)' }}>{m.std}{m.unit}</span>
              </div>

              {/* AI bar */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span style={{ width: '60px', fontSize: '0.75rem', color: 'var(--accent-cyan)', fontWeight: 700 }}>AI Optimal</span>
                <div style={{ flex: 1, height: '12px', background: 'var(--primary-soft)', borderRadius: '6px', overflow: 'hidden' }}>
                  <div style={{ 
                    width: `${aiPct}%`, 
                    height: '100%', 
                    background: 'linear-gradient(90deg, var(--accent-teal), var(--accent-cyan))', 
                    borderRadius: '6px',

                  }} />
                </div>
                <span style={{ width: '70px', textAlign: 'right', fontSize: '0.95rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>{m.ai}{m.unit}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
