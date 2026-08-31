import React, { useState } from 'react';
import { Activity } from 'lucide-react';

export default function EventTimelineChart() {
  const [activeBar, setActiveBar] = useState(null);

  const hours = [
    { time: '00:00', events: 2, highSev: 0 },
    { time: '03:00', events: 5, highSev: 1 },
    { time: '06:00', events: 3, highSev: 0 },
    { time: '09:00', events: 8, highSev: 3 },
    { time: '12:00', events: 12, highSev: 4 },
    { time: '15:00', events: 16, highSev: 6 },
    { time: '18:00', events: 9, highSev: 2 },
    { time: '21:00', events: 4, highSev: 1 }
  ];

  const maxEvents = 18;

  return (
    <div className="glass-panel" style={{ padding: '24px' }}>
      <div className="section-header">
        <h3 className="section-title" style={{ fontSize: '1.15rem' }}>
          <Activity size={20} color="var(--accent-cyan)" />
          Telemetry Event Frequency (24h Timeline)
        </h3>
        <div style={{ display: 'flex', gap: '14px', fontSize: '0.8rem' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--accent-cyan)' }}>
            <span style={{ width: '10px', height: '10px', background: 'var(--accent-cyan)', borderRadius: '2px', display: 'inline-block' }}></span>
            Total Events
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--accent-rose)' }}>
            <span style={{ width: '10px', height: '10px', background: 'var(--accent-rose)', borderRadius: '2px', display: 'inline-block' }}></span>
            High Severity Hazards
          </span>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', height: '180px', marginTop: '32px', paddingBottom: '10px', borderBottom: '1px solid var(--border-subtle)' }}>
        {hours.map((h, i) => {
          const totalHeightPct = (h.events / maxEvents) * 100;
          const highHeightPct = (h.highSev / maxEvents) * 100;
          const isHovered = activeBar === i;

          return (
            <div 
              key={h.time}
              onMouseEnter={() => setActiveBar(i)}
              onMouseLeave={() => setActiveBar(null)}
              style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1, height: '100%', justifyContent: 'flex-end', position: 'relative', cursor: 'pointer' }}
            >
              {isHovered && (
                <div style={{
                  position: 'absolute',
                  top: '-45px',
                  background: 'var(--surface)',
                  border: '1px solid var(--accent-cyan)',
                  padding: '6px 10px',
                  borderRadius: '6px',
                  fontSize: '0.75rem',
                  whiteSpace: 'nowrap',
                  zIndex: 10,
                  boxShadow: '0 4px 12px var(--surface-subtle)'
                }}>
                  <strong>{h.time}</strong>: {h.events} Total ({h.highSev} High Hazard)
                </div>
              )}

              <div style={{ width: '32px', height: '100%', display: 'flex', alignItems: 'flex-end', justifyContent: 'center', position: 'relative' }}>
                {/* Total events bar */}
                <div style={{
                  width: '100%',
                  height: `${totalHeightPct}%`,
                  background: isHovered ? 'var(--accent-cyan)' : 'var(--primary-border)',
                  borderRadius: '6px 6px 0 0',
                  transition: 'all 0.3s ease',
                  position: 'absolute',
                  bottom: 0
                }} />

                {/* High severity bar overlay */}
                <div style={{
                  width: '100%',
                  height: `${highHeightPct}%`,
                  background: 'var(--accent-rose)',
                  borderRadius: '6px 6px 0 0',
                  transition: 'all 0.3s ease',
                  position: 'absolute',
                  bottom: 0,
                  boxShadow: h.highSev > 0 ? '0 0 10px var(--danger-border)' : 'none'
                }} />
              </div>

              <span style={{ fontSize: '0.75rem', color: isHovered ? 'var(--text-strong)' : 'var(--text-muted)', marginTop: '10px', fontWeight: isHovered ? 700 : 400 }}>
                {h.time}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
