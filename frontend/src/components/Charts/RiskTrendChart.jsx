import React from 'react';
import { Waves } from 'lucide-react';

// Fixed categorical palette, not the theme's semantic accent colors
// (--accent-rose etc. mean severity elsewhere in this app) -- corridors
// aren't ranked by severity here, they need to stay visually distinct
// from each other regardless of which one is currently worst.
const CORRIDOR_COLORS = [
  '#22d3ee', '#34d399', '#fbbf24', '#fb7185',
  '#a78bfa', '#60a5fa', '#fb923c', '#f472b6',
];

const formatAxisLabel = (date) =>
  date.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });

/**
 * One real trend line per monitored corridor, not a single fleet-wide
 * line. The single-series version of this chart (still available as
 * GET /api/risks/history) only ever has data for whichever corridor
 * happened to be fleet-wide worst at the moment each /api/risks poll
 * landed -- in practice that meant risk_readings held months of
 * history for exactly one corridor and nothing else, which made this
 * chart nearly flat regardless of what was actually happening at the
 * other 7. trendsByCorridor comes from GET /api/risks/history/by-corridor,
 * which re-scores every stored sea-state reading (all 8 corridors) --
 * real comparative signal, not a coincidence of which corridor stayed
 * worst the longest.
 */
export default function RiskTrendChart({ trendsByCorridor }) {
  const corridors = Object.entries(trendsByCorridor || {})
    .filter(([, points]) => points && points.length > 0)
    .sort(([, a], [, b]) => b.length - a.length);

  if (corridors.length === 0) {
    return (
      <div className="panel">
        <div className="section-header">
          <h3 className="section-title">
            <Waves size={17} color="var(--accent-cyan)" />
            Risk Trend by Corridor
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
            No corridor risk history recorded yet.
          </p>
          <p style={{ color: 'var(--text-subtle)', fontSize: '0.8rem', marginTop: '6px' }}>
            Builds up as live sea-state conditions are polled for each monitored corridor.
          </p>
        </div>
      </div>
    );
  }

  const width = 640;
  const height = 220;
  const paddingX = 50;
  const paddingY = 20;
  const plotWidth = width - paddingX * 2;
  const plotHeight = height - paddingY * 2;

  const sortedByTime = corridors.map(([location, points]) => [
    location,
    [...points].sort((a, b) => new Date(a.time) - new Date(b.time)),
  ]);

  const allTimes = sortedByTime.flatMap(([, points]) => points.map((p) => new Date(p.time).getTime()));
  const minTime = Math.min(...allTimes);
  const maxTime = Math.max(...allTimes);
  const timeSpan = maxTime - minTime || 1; // avoid a div-by-zero when every point shares one timestamp

  const xFor = (isoTime) => paddingX + ((new Date(isoTime).getTime() - minTime) / timeSpan) * plotWidth;
  const yFor = (score) => height - paddingY - (score / 100) * plotHeight;

  const allScores = sortedByTime.flatMap(([, points]) => points.map((p) => p.score));
  const peak = Math.max(...allScores);
  const totalPoints = allScores.length;

  const labelCount = 4;
  const timeLabels = Array.from({ length: labelCount }, (_, i) =>
    new Date(minTime + (timeSpan * i) / (labelCount - 1))
  );

  return (
    <div className="glass-panel" style={{ padding: '24px', width: '100%' }}>
      <div className="section-header">
        <h3 className="section-title" style={{ fontSize: '1.15rem' }}>
          <Waves size={20} color="var(--accent-cyan)" />
          Risk Trend by Corridor
        </h3>
        <span className="status-badge" style={{ fontSize: '0.75rem' }}>
          PEAK: {peak}/100 · {totalPoints} reading{totalPoints === 1 ? '' : 's'} across {corridors.length} corridor{corridors.length === 1 ? '' : 's'}
        </span>
      </div>

      <div style={{ width: '100%', overflowX: 'auto', marginTop: '16px' }}>
        <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: 'auto', overflow: 'visible' }}>
          <line x1={paddingX} y1={paddingY} x2={width - paddingX} y2={paddingY} stroke="var(--surface-subtle)" strokeDasharray="4 4" />
          <line x1={paddingX} y1={height / 2} x2={width - paddingX} y2={height / 2} stroke="var(--surface-subtle)" strokeDasharray="4 4" />
          <line x1={paddingX} y1={height - paddingY} x2={width - paddingX} y2={height - paddingY} stroke="var(--border-strong)" />

          {sortedByTime.map(([location, points], idx) => {
            const color = CORRIDOR_COLORS[idx % CORRIDOR_COLORS.length];
            const linePoints = points.map((p) => `${xFor(p.time)},${yFor(p.score)}`).join(' ');
            return (
              <g key={location}>
                {points.length > 1 && (
                  <polyline
                    fill="none" stroke={color} strokeWidth="2" opacity="0.85"
                    points={linePoints} strokeLinecap="round" strokeLinejoin="round"
                  />
                )}
                {points.map((p, i) => (
                  <circle
                    key={i} cx={xFor(p.time)} cy={yFor(p.score)} r="3.5"
                    fill={color} stroke="var(--surface)" strokeWidth="1.5"
                    style={{ cursor: 'pointer' }}
                  >
                    <title>{`${location} — ${p.time}: ${p.score}/100`}</title>
                  </circle>
                ))}
              </g>
            );
          })}

          {timeLabels.map((d, i) => (
            <text
              key={i}
              x={paddingX + (plotWidth * i) / (labelCount - 1)}
              y={height - 4}
              fill="var(--text-muted)" fontSize="9.5" textAnchor="middle" fontFamily="var(--font-body)"
            >
              {formatAxisLabel(d)}
            </text>
          ))}
        </svg>
      </div>

      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: '8px 18px',
        marginTop: '14px', paddingTop: '14px', borderTop: '1px solid var(--border)'
      }}>
        {sortedByTime.map(([location, points], idx) => {
          const color = CORRIDOR_COLORS[idx % CORRIDOR_COLORS.length];
          const latest = points[points.length - 1];
          return (
            <div key={location} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.78rem', color: 'var(--text-body)' }}>
              <span style={{ width: '9px', height: '9px', borderRadius: '50%', background: color, display: 'inline-block', flexShrink: 0 }} />
              {location}
              <strong style={{ color: 'var(--text-strong)' }}>{latest.score}/100</strong>
            </div>
          );
        })}
      </div>
    </div>
  );
}
