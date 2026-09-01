import React from 'react';
import { ShieldAlert } from 'lucide-react';

export default function RiskTrendChart({ trends }) {
  const data = trends || [];

  // No invented curve: the backend stores no historical risk series yet,
  // so an empty state is shown rather than a fabricated 24h trend.
  if (data.length === 0) {
    return (
      <div className="panel">
        <div className="section-header">
          <h3 className="section-title">
            <ShieldAlert size={17} color="var(--danger)" />
            Fleet Risk Score Trajectory
          </h3>
        </div>
        <div style={{
          textAlign: 'center',
          padding: '40px 20px',
          border: '1px dashed var(--border-strong)',
          borderRadius: 'var(--radius)',
          background: 'var(--surface-subtle)'
        }}>
          <p style={{ color: 'var(--text-subtle)', fontSize: '0.875rem' }}>
            No risk history recorded yet.
          </p>
          <p style={{ color: 'var(--text-subtle)', fontSize: '0.8rem', marginTop: '6px' }}>
            Scores are computed per request; persisting them over time will populate this trend.
          </p>
        </div>
      </div>
    );
  }

  // SVG dimensions
  const width = 600;
  const height = 180;
  const paddingX = 40;
  const paddingY = 20;

  const points = data.map((d, i) => {
    const x = paddingX + (i / (data.length - 1)) * (width - paddingX * 2);
    const y = height - paddingY - (d.score / 100) * (height - paddingY * 2);
    return `${x},${y}`;
  }).join(' ');

  const areaPoints = `${paddingX},${height - paddingY} ${points} ${width - paddingX},${height - paddingY}`;

  const peak = Math.max(...data.map((d) => d.score));
  const peakTone = peak >= 75
    ? { fg: 'var(--danger)', bg: 'var(--danger-soft)', border: 'var(--danger-border)' }
    : peak >= 40
      ? { fg: 'var(--warning)', bg: 'var(--warning-soft)', border: 'var(--warning-border)' }
      : { fg: 'var(--success)', bg: 'var(--success-soft)', border: 'var(--success-border)' };

  return (
    <div className="glass-panel" style={{ padding: '24px', width: '100%' }}>
      <div className="section-header">
        <h3 className="section-title" style={{ fontSize: '1.15rem' }}>
          <ShieldAlert size={20} color="var(--accent-rose)" />
          Fleet Risk Score Trajectory (24h Trend)
        </h3>
        {/* Computed from the recorded series. This badge previously read
            a hardcoded "PEAK HAZARD: 68/100" regardless of the data. */}
        <span className="status-badge" style={{ fontSize: '0.75rem', background: peakTone.bg, borderColor: peakTone.border, color: peakTone.fg }}>
          PEAK: {peak}/100 · {data.length} reading{data.length === 1 ? '' : 's'}
        </span>
      </div>

      <div style={{ width: '100%', overflowX: 'auto', marginTop: '16px' }}>
        <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: 'auto', overflow: 'visible' }}>
          <defs>
            <linearGradient id="riskGradient" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="var(--accent-rose)" stopOpacity="0.4" />
              <stop offset="50%" stopColor="var(--accent-amber)" stopOpacity="0.2" />
              <stop offset="100%" stopColor="var(--accent-cyan)" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          <line x1={paddingX} y1={paddingY} x2={width - paddingX} y2={paddingY} stroke="var(--surface-subtle)" strokeDasharray="4 4" />
          <line x1={paddingX} y1={height / 2} x2={width - paddingX} y2={height / 2} stroke="var(--surface-subtle)" strokeDasharray="4 4" />
          <line x1={paddingX} y1={height - paddingY} x2={width - paddingX} y2={height - paddingY} stroke="var(--border-strong)" />

          {/* Area under curve */}
          <polygon points={areaPoints} fill="url(#riskGradient)" />

          {/* Line path */}
          <polyline fill="none" stroke="var(--accent-rose)" strokeWidth="3" points={points} strokeLinecap="round" strokeLinejoin="round" />

          {/* Data points and labels */}
          {data.map((d, i) => {
            const x = paddingX + (i / (data.length - 1)) * (width - paddingX * 2);
            const y = height - paddingY - (d.score / 100) * (height - paddingY * 2);
            const isHigh = d.score > 50;

            return (
              <g key={i}>
                <circle 
                  cx={x} 
                  cy={y} 
                  r="5" 
                  fill={isHigh ? 'var(--accent-rose)' : 'var(--accent-cyan)'} 
                  stroke="var(--surface)" 
                  strokeWidth="2"
                  style={{ cursor: 'pointer' }}
                >
                  <title>{`${d.time}: Risk Score ${d.score}/100`}</title>
                </circle>
                <text x={x} y={height - 4} fill="var(--text-muted)" fontSize="10" textAnchor="middle" fontFamily="var(--font-body)">
                  {d.time}
                </text>
                <text x={x} y={y - 10} fill={isHigh ? 'var(--accent-rose)' : 'var(--text-strong)'} fontSize="11" fontWeight="700" textAnchor="middle" fontFamily="var(--font-heading)">
                  {d.score}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
