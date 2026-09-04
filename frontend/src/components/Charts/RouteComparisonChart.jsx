import React from 'react';
import { GitCompare } from 'lucide-react';

/**
 * Real comparison of RouteOptimizer's ranked candidates (Slice 06) --
 * this used to be a permanent placeholder ("The Route Agent returns a
 * single recommended route... Producing real alternatives means
 * scoring candidate routes in the agent — a feature, not a chart
 * fix"). That feature now exists: `recommended` and `alternatives` are
 * real paths through the digital twin, each with a real composite
 * score (lower is better, normalized within this candidate set).
 */
export default function RouteComparisonChart({ recommended, alternatives = [] }) {
  const candidates = [recommended, ...alternatives].filter(Boolean);

  if (candidates.length === 0) {
    return (
      <div className="panel">
        <div className="section-header">
          <h3 className="section-title">
            <GitCompare size={17} color="var(--info)" />
            Corridor comparison
          </h3>
        </div>
        <div className="chart-empty">
          <p>No candidates to compare yet.</p>
          <p className="chart-empty-sub">Pick an origin and destination above to run the optimizer.</p>
        </div>
      </div>
    );
  }

  const maxScore = Math.max(...candidates.map((c) => c.score), 0.0001);
  const shown = candidates.slice(0, 5);

  return (
    <div className="panel">
      <div className="section-header">
        <h3 className="section-title">
          <GitCompare size={17} color="var(--info)" />
          Corridor comparison
        </h3>
        <span style={{ fontSize: '0.72rem', color: 'var(--text-subtle)' }}>Lower score = better</span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '8px' }}>
        {shown.map((c, i) => {
          const label = (c.lane_ids || []).join(' + ');
          const widthPct = Math.max(4, (c.score / maxScore) * 100);
          const color = i === 0 ? 'var(--accent-emerald)' : c.risk >= 60 ? 'var(--accent-rose)' : 'var(--accent-cyan)';
          return (
            <div key={`${label}-${i}`}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', marginBottom: '4px', gap: '10px' }}>
                <span style={{ color: 'var(--text-body)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {i === 0 ? '★ ' : ''}{label}
                </span>
                <span style={{ color: 'var(--text-subtle)', flexShrink: 0 }}>
                  risk {c.risk}/100 · score {c.score.toFixed(3)}
                </span>
              </div>
              <div style={{ background: 'var(--surface-subtle)', borderRadius: '4px', height: '8px', overflow: 'hidden' }}>
                <div style={{ width: `${widthPct}%`, height: '100%', background: color, borderRadius: '4px' }} />
              </div>
            </div>
          );
        })}
      </div>

      {candidates.length > 5 && (
        <p className="form-note">
          +{candidates.length - 5} more candidate{candidates.length - 5 === 1 ? '' : 's'} in the list below.
        </p>
      )}
    </div>
  );
}
