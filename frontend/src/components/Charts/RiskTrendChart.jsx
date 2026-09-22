import React, { useState } from 'react';
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

// Catmull-Rom -> cubic Bezier conversion (tension 1/6) so real,
// irregularly-spaced readings render as a smooth curve instead of a
// jagged polyline -- no charting library, just the standard spline math.
function smoothLinePath(points) {
  if (points.length < 2) return '';
  if (points.length === 2) return `M ${points[0].x},${points[0].y} L ${points[1].x},${points[1].y}`;
  let d = `M ${points[0].x},${points[0].y}`;
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i === 0 ? 0 : i - 1];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[i + 2 < points.length ? i + 2 : i + 1];
    const cp1x = p1.x + (p2.x - p0.x) / 6;
    const cp1y = p1.y + (p2.y - p0.y) / 6;
    const cp2x = p2.x - (p3.x - p1.x) / 6;
    const cp2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C ${cp1x},${cp1y} ${cp2x},${cp2y} ${p2.x},${p2.y}`;
  }
  return d;
}

function smoothAreaPath(points, baselineY) {
  const line = smoothLinePath(points);
  const last = points[points.length - 1];
  const first = points[0];
  return `${line} L ${last.x},${baselineY} L ${first.x},${baselineY} Z`;
}

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
export default function RiskTrendChart({ trendsByCorridor, selectedLocation, onSelectLocation }) {
  const [hovered, setHovered] = useState(null);

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
  const height = 260;
  const paddingX = 50;
  const paddingTop = 20;
  const paddingBottom = 34;
  const plotWidth = width - paddingX * 2;
  const plotHeight = height - paddingTop - paddingBottom;

  const sortedByTime = corridors.map(([location, points]) => [
    location,
    [...points].sort((a, b) => new Date(a.time) - new Date(b.time)),
  ]);

  const allTimes = sortedByTime.flatMap(([, points]) => points.map((p) => new Date(p.time).getTime()));
  const minTime = Math.min(...allTimes);
  const maxTime = Math.max(...allTimes);
  const timeSpan = maxTime - minTime || 1; // avoid a div-by-zero when every point shares one timestamp

  const xFor = (isoTime) => paddingX + ((new Date(isoTime).getTime() - minTime) / timeSpan) * plotWidth;
  const yFor = (score) => paddingTop + plotHeight - (score / 100) * plotHeight;
  const baselineY = paddingTop + plotHeight;

  const allScores = sortedByTime.flatMap(([, points]) => points.map((p) => p.score));
  const peak = Math.max(...allScores);
  const totalPoints = allScores.length;

  // The single highest reading across every corridor -- called out with
  // its own glowing marker so the badge number ("PEAK: x/100") has a
  // visible anchor on the chart, not just a summary stat floating above it.
  let peakMarker = null;
  outer: for (const [location, points] of sortedByTime) {
    for (const p of points) {
      if (p.score === peak) {
        peakMarker = { location, time: p.time, score: p.score, x: xFor(p.time), y: yFor(p.score) };
        break outer;
      }
    }
  }

  const labelCount = 4;
  const timeLabels = Array.from({ length: labelCount }, (_, i) =>
    new Date(minTime + (timeSpan * i) / (labelCount - 1))
  );
  const yTicks = [0, 25, 50, 75, 100];

  return (
    <div className="glass-panel" style={{ padding: '24px', width: '100%' }}>
      <style>{`
        @keyframes riskPeakPulse {
          0% { r: 5; opacity: 0.55; }
          70% { r: 13; opacity: 0; }
          100% { r: 13; opacity: 0; }
        }
        .risk-peak-ring { animation: riskPeakPulse 2.2s ease-out infinite; transform-origin: center; }
        .risk-trend-dot { transition: r 0.15s ease; }
      `}</style>

      <div className="section-header">
        <h3 className="section-title" style={{ fontSize: '1.15rem' }}>
          <Waves size={20} color="var(--accent-cyan)" />
          Risk Trend by Corridor
        </h3>
        <span className="status-badge" style={{ fontSize: '0.75rem' }}>
          PEAK: {peak}/100 · {totalPoints} reading{totalPoints === 1 ? '' : 's'} across {corridors.length} corridor{corridors.length === 1 ? '' : 's'}
        </span>
      </div>

      <div style={{ width: '100%', overflowX: 'auto', marginTop: '16px', position: 'relative' }}>
        <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: 'auto', overflow: 'visible' }}>
          <defs>
            {sortedByTime.map(([location], idx) => {
              const color = CORRIDOR_COLORS[idx % CORRIDOR_COLORS.length];
              return (
                <linearGradient key={location} id={`riskFill-${idx}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity="0.32" />
                  <stop offset="100%" stopColor={color} stopOpacity="0" />
                </linearGradient>
              );
            })}
          </defs>

          {/* Y-axis gridlines + score labels -- previously there was no
              visual reference at all for what a line's height meant. */}
          {yTicks.map((tick) => (
            <g key={tick}>
              <line
                x1={paddingX} x2={width - paddingX} y1={yFor(tick)} y2={yFor(tick)}
                stroke={tick === 0 ? 'var(--border-strong)' : 'var(--surface-subtle)'}
                strokeDasharray={tick === 0 ? 'none' : '4 4'}
              />
              <text x={paddingX - 10} y={yFor(tick) + 3} fill="var(--text-muted)" fontSize="9.5" textAnchor="end" fontFamily="var(--font-body)">
                {tick}
              </text>
            </g>
          ))}

          {sortedByTime.map(([location, points], idx) => {
            const color = CORRIDOR_COLORS[idx % CORRIDOR_COLORS.length];
            const isSelected = selectedLocation === location;
            const dimmed = selectedLocation && !isSelected;
            const coords = points.map((p) => ({ x: xFor(p.time), y: yFor(p.score) }));
            return (
              <g
                key={location}
                opacity={dimmed ? 0.2 : 1}
                style={{ cursor: onSelectLocation ? 'pointer' : 'default', transition: 'opacity 0.25s ease' }}
                onClick={() => onSelectLocation?.(location)}
              >
                {points.length > 1 && (
                  <>
                    <path d={smoothAreaPath(coords, baselineY)} fill={`url(#riskFill-${idx})`} stroke="none" />
                    <path
                      d={smoothLinePath(coords)}
                      fill="none" stroke={color} strokeWidth={isSelected ? 3.5 : 2} opacity="0.95"
                      strokeLinecap="round" strokeLinejoin="round"
                    />
                  </>
                )}
                {points.map((p, i) => (
                  <circle
                    key={i}
                    className="risk-trend-dot"
                    cx={xFor(p.time)} cy={yFor(p.score)}
                    r={hovered?.location === location && hovered?.time === p.time ? 6 : (isSelected ? 4.5 : 3.5)}
                    fill={color} stroke="var(--surface)" strokeWidth="1.5"
                    onMouseEnter={() => setHovered({ location, time: p.time, score: p.score, x: xFor(p.time), y: yFor(p.score), color })}
                    onMouseLeave={() => setHovered((h) => (h?.location === location && h?.time === p.time ? null : h))}
                  />
                ))}
              </g>
            );
          })}

          {peakMarker && (
            <g style={{ pointerEvents: 'none' }}>
              <circle className="risk-peak-ring" cx={peakMarker.x} cy={peakMarker.y} r="5" fill="none" stroke="var(--danger)" strokeWidth="2" />
              <circle cx={peakMarker.x} cy={peakMarker.y} r="4" fill="var(--danger)" stroke="var(--surface)" strokeWidth="1.5" />
            </g>
          )}

          {timeLabels.map((d, i) => (
            <text
              key={i}
              x={paddingX + (plotWidth * i) / (labelCount - 1)}
              y={height - paddingBottom + 18}
              fill="var(--text-muted)" fontSize="9.5" textAnchor="middle" fontFamily="var(--font-body)"
            >
              {formatAxisLabel(d)}
            </text>
          ))}
        </svg>

        {hovered && (
          <div
            style={{
              position: 'absolute',
              left: `${(hovered.x / width) * 100}%`,
              top: `${(hovered.y / height) * 100}%`,
              transform: 'translate(-50%, -130%)',
              background: 'var(--surface)',
              border: `1px solid ${hovered.color}`,
              borderRadius: 'var(--radius)',
              padding: '8px 11px',
              fontSize: '0.75rem',
              color: 'var(--text-body)',
              whiteSpace: 'nowrap',
              pointerEvents: 'none',
              boxShadow: '0 4px 14px rgba(0,0,0,0.35)',
              zIndex: 2,
            }}
          >
            <div style={{ fontWeight: 700, color: 'var(--text-strong)', marginBottom: '2px' }}>{hovered.location}</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: hovered.color, display: 'inline-block' }} />
              {hovered.score}/100 · {formatAxisLabel(new Date(hovered.time))}
            </div>
          </div>
        )}
      </div>

      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: '6px 10px',
        marginTop: '14px', paddingTop: '14px', borderTop: '1px solid var(--border)'
      }}>
        {sortedByTime.map(([location, points], idx) => {
          const color = CORRIDOR_COLORS[idx % CORRIDOR_COLORS.length];
          const latest = points[points.length - 1];
          const isSelected = selectedLocation === location;
          return (
            <button
              key={location}
              type="button"
              onClick={() => onSelectLocation?.(location)}
              title={onSelectLocation ? `${isSelected ? 'Clear' : 'Select'} ${location}` : undefined}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.78rem',
                color: 'var(--text-body)', background: isSelected ? 'var(--primary-soft)' : 'transparent',
                border: isSelected ? '1px solid var(--accent-cyan)' : '1px solid transparent',
                borderRadius: '999px', padding: '3px 9px 3px 6px',
                cursor: onSelectLocation ? 'pointer' : 'default',
              }}
            >
              <span style={{ width: '9px', height: '9px', borderRadius: '50%', background: color, display: 'inline-block', flexShrink: 0 }} />
              {location}
              <strong style={{ color: 'var(--text-strong)' }}>{latest.score}/100</strong>
            </button>
          );
        })}
      </div>
    </div>
  );
}
