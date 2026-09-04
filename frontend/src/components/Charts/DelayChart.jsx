import React from 'react';
import { Clock } from 'lucide-react';

/**
 * Real per-port delay data for the current route. This used to be a
 * permanent placeholder -- port_congestion.csv has real avg_wait_days
 * and berth_delay_hrs per port, but nothing served it. It's now on
 * every digital twin node (app/twin/digital_twin.py's _build_nodes()),
 * so the ports a real route actually passes through -- origin,
 * destination, and any intermediate stops on a multi-hop path -- can
 * show their real recorded figures, not an invented estimate.
 */
export default function DelayChart({ twin, ports = [] }) {
  const nodesByName = Object.fromEntries((twin?.nodes || []).map((n) => [n.id, n]));
  const rows = ports.map((p) => nodesByName[p]).filter(Boolean);

  if (rows.length === 0) {
    return (
      <div className="panel">
        <div className="section-header">
          <h3 className="section-title">
            <Clock size={17} color="var(--warning)" />
            Estimated transit &amp; port delays
          </h3>
        </div>
        <div className="chart-empty">
          <p>No delay estimates available.</p>
          <p className="chart-empty-sub">
            Run a route optimization above to see recorded wait times for the ports it passes through.
          </p>
        </div>
      </div>
    );
  }

  const maxWait = Math.max(...rows.map((r) => r.avg_wait_days ?? 0), 0.0001);

  return (
    <div className="panel">
      <div className="section-header">
        <h3 className="section-title">
          <Clock size={17} color="var(--warning)" />
          Estimated transit &amp; port delays
        </h3>
      </div>
      <p style={{ fontSize: '0.76rem', color: 'var(--text-subtle)', marginBottom: '12px' }}>
        Real recorded average wait days and berth delay per port along this route
        (port_congestion.csv, latest week per port).
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {rows.map((r, i) => (
          <div key={r.id}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', marginBottom: '4px', gap: '10px' }}>
              <span style={{ color: 'var(--text-body)' }}>{i + 1}. {r.id}</span>
              <span style={{ color: 'var(--text-subtle)', flexShrink: 0, textAlign: 'right' }}>
                {r.avg_wait_days != null ? `${r.avg_wait_days.toFixed(1)} wait days` : 'no data'}
                {r.berth_delay_hrs != null ? ` · ${r.berth_delay_hrs.toFixed(0)}h berth delay` : ''}
              </span>
            </div>
            <div style={{ background: 'var(--surface-subtle)', borderRadius: '4px', height: '8px', overflow: 'hidden' }}>
              <div style={{
                width: `${Math.max(4, ((r.avg_wait_days ?? 0) / maxWait) * 100)}%`,
                height: '100%', background: 'var(--accent-amber)', borderRadius: '4px',
              }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
