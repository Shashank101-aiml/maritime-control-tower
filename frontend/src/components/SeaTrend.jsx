import React, { useMemo } from 'react';
import Sparkline from './Sparkline';
import { summarizeTrend, formatSpan, formatClock } from '../utils/seaTrend';

const TONE = { up: '#fbbf24', down: '#34d399', flat: 'var(--text-subtle)' };
const ARROW = { up: '▲', down: '▼', flat: '►' };

const signed = (value, decimals) => `${value > 0 ? '+' : ''}${value.toFixed(decimals)}`;

/**
 * How a corridor's sea state has actually moved: a sparkline of its
 * recorded readings and the change since the previous one. Rising is amber
 * (conditions worsening), easing is green, unchanged is muted. Built only
 * from stored readings -- with fewer than two it says so instead of
 * drawing anything.
 */
export default function SeaTrend({ points }) {
  const trend = useMemo(() => summarizeTrend(points), [points]);

  if (points == null) return null; // history still loading
  if (!trend || trend.valid.length < 2) {
    return (
      <span
        style={{ fontSize: '0.7rem', color: 'var(--text-subtle)' }}
        title="Fewer than two recorded readings in this window, so there is no trend to draw yet."
      >
        no trend yet
      </span>
    );
  }

  const { label, unit, decimals, delta, direction, prev, last, first, windowDelta, min, max, valid, spanMs } = trend;
  const tone = TONE[direction];
  const summary =
    `${label}: ${last.v.toFixed(decimals)} ${unit} now; ` +
    (direction === 'flat'
      ? `unchanged since ${formatClock(prev.t)}. `
      : `${signed(delta, decimals)} ${unit} since ${formatClock(prev.t)} (${last.v.toFixed(decimals)} vs ${prev.v.toFixed(decimals)}). `) +
    `Over ${formatSpan(spanMs)}: ${first.v.toFixed(decimals)} to ${last.v.toFixed(decimals)} ${unit} ` +
    `(${signed(windowDelta, decimals)}), range ${min.toFixed(decimals)}-${max.toFixed(decimals)}, ${valid.length} recorded readings.`;

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)' }} title={summary}>
      <Sparkline points={valid} color="var(--accent-cyan)" dotColor={tone} label={summary} />
      <span style={{ color: tone, fontSize: '0.72rem', fontWeight: 600, whiteSpace: 'nowrap', minWidth: '62px', textAlign: 'right' }}>
        {ARROW[direction]} {direction === 'flat' ? 'steady' : `${signed(delta, decimals)} ${unit}`}
      </span>
    </span>
  );
}
