import React from 'react';
import { GAP_MS } from '../utils/seaTrend';

// Blank width left at a break, measured in reading-steps.
const BREAK_STEPS = 2;

/**
 * A small line of recorded values, one step per reading. Wherever readings
 * are more than GAP_MS apart (the app wasn't collecting) the line is broken
 * and a blank space is left, so a stretch with no data reads as a break
 * instead of a straight line that implies data. Readings are laid out in
 * sequence rather than to a time scale: a time scale would squeeze each
 * cluster of readings into a few pixels whenever there is a long gap.
 * A flat series draws a flat line.
 */
export default function Sparkline({ points, width = 96, height = 28, color = 'currentColor', dotColor, label }) {
  if (!points || points.length < 2) return null;

  const pad = 3;
  const lo = Math.min(...points.map((p) => p.v));
  const hi = Math.max(...points.map((p) => p.v));

  // Position of each reading along the axis, with extra room at each break.
  const positions = [];
  let position = 0;
  let breaks = 0;
  points.forEach((p, i) => {
    if (i > 0) {
      const gap = p.t - points[i - 1].t > GAP_MS;
      if (gap) breaks += 1;
      position += gap ? BREAK_STEPS : 1;
    }
    positions.push(position);
  });
  const span = Math.max(position, 1);

  const x = (pos) => pad + (pos / span) * (width - pad * 2);
  const y = (v) => (hi === lo ? height / 2 : pad + (1 - (v - lo) / (hi - lo)) * (height - pad * 2));

  const segments = [];
  let current = [];
  points.forEach((p, i) => {
    if (i > 0 && p.t - points[i - 1].t > GAP_MS) {
      segments.push(current);
      current = [];
    }
    current.push({ ...p, pos: positions[i] });
  });
  segments.push(current);

  const last = points[points.length - 1];
  const lastPos = positions[positions.length - 1];

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label} style={{ flex: 'none' }}>
      {segments.map((seg, i) => (
        seg.length > 1
          ? (
            <polyline
              key={i}
              points={seg.map((p) => `${x(p.pos).toFixed(1)},${y(p.v).toFixed(1)}`).join(' ')}
              fill="none" stroke={color} strokeWidth="1.7" strokeLinejoin="round" strokeLinecap="round" opacity="0.9"
            />
          )
          : <circle key={i} cx={x(seg[0].pos)} cy={y(seg[0].v)} r="1.6" fill={color} opacity="0.75" />
      ))}
      <circle cx={x(lastPos)} cy={y(last.v)} r="2.8" fill={dotColor || color} />
      {breaks > 0 && segments.slice(1).map((seg, i) => (
        <line
          key={`break-${i}`}
          x1={x(seg[0].pos - BREAK_STEPS / 2)} x2={x(seg[0].pos - BREAK_STEPS / 2)}
          y1={height - pad} y2={height - pad - 4}
          stroke="var(--text-subtle)" strokeWidth="1" opacity="0.7"
        />
      ))}
    </svg>
  );
}
