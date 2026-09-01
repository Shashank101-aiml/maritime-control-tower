import React, { useEffect, useState } from 'react';
import { Activity, RefreshCw } from 'lucide-react';
import { apiFetch } from '../../services/apiClient';

import { API_BASE_URL as BASE_URL } from '../../config';

/**
 * Hourly agent-execution activity over the last 24h.
 *
 * This replaces a chart that rendered a hardcoded array of invented
 * hourly telemetry counts — it claimed ~59 events across 24 hours while
 * the panel beneath it listed 8 real readings. Everything here comes
 * from recorded agent_executions rows.
 *
 * Nothing is backfilled, so a recently started instance genuinely has
 * only a few populated hours. The footnote states how much history
 * exists rather than implying a full day of it.
 */
export default function EventTimelineChart() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [hovered, setHovered] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const res = await apiFetch(`${BASE_URL}/governance/activity?hours=24`);
      if (!res.ok) throw new Error(`Request failed (${res.status})`);
      setData(await res.json());
      setError(null);
    } catch (err) {
      setError(err.message);
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const timer = setInterval(load, 60000);
    return () => clearInterval(timer);
  }, []);

  const buckets = data?.buckets || [];
  const peak = Math.max(1, ...buckets.map((b) => b.total));
  // Round the axis up to a clean number so gridline labels read well.
  const axisMax = peak <= 5 ? 5 : Math.ceil(peak / 10) * 10;
  const hasHistory = (data?.total_executions ?? 0) > 0;

  const coverage = () => {
    if (!data?.recorded_from) return 'No activity recorded yet.';
    const from = new Date(data.recorded_from + 'Z');
    const hrs = (Date.now() - from.getTime()) / 3600000;
    const span = hrs < 1
      ? `${Math.max(1, Math.round(hrs * 60))} min`
      : `${hrs.toFixed(1)} h`;
    return `${data.total_executions} executions recorded over ${span} of history. Older hours are empty because nothing is backfilled.`;
  };

  return (
    <div className="panel">
      <div className="section-header">
        <h3 className="section-title">
          <Activity size={17} color="var(--primary)" />
          Agent execution activity (24 h)
        </h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', fontSize: '0.75rem' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-subtle)' }}>
            <i style={{ width: 9, height: 9, borderRadius: 2, background: 'var(--primary)', display: 'inline-block' }} />
            Completed
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-subtle)' }}>
            <i style={{ width: 9, height: 9, borderRadius: 2, background: 'var(--warning)', display: 'inline-block' }} />
            Held or failed
          </span>
          {loading && <RefreshCw size={13} className="spin" color="var(--text-subtle)" />}
        </div>
      </div>

      {error ? (
        <div className="chart-empty">
          <p>Activity unavailable — {error}</p>
        </div>
      ) : !hasHistory && !loading ? (
        <div className="chart-empty">
          <p>No agent executions recorded yet.</p>
          <p className="chart-empty-sub">
            Run the agent pipeline or request a prediction and activity will appear here.
          </p>
        </div>
      ) : (
        <>
          <div className="chart-plot">
            {/* y-axis gridlines so a value can actually be read off the chart */}
            {[0, 0.25, 0.5, 0.75, 1].map((f) => (
              <div key={f} className="chart-gridline" style={{ bottom: `${f * 100}%` }}>
                <span>{Math.round(axisMax * f)}</span>
              </div>
            ))}

            <div className="chart-bars">
              {buckets.map((b, i) => {
                const clean = b.total - b.flagged;
                const isHovered = hovered === i;
                return (
                  <div
                    key={b.hour}
                    className="chart-bar-slot"
                    onMouseEnter={() => setHovered(i)}
                    onMouseLeave={() => setHovered(null)}
                  >
                    {isHovered && b.total > 0 && (
                      <div className="chart-tip">
                        <strong>{b.label}</strong> · {b.total} run{b.total === 1 ? '' : 's'}
                        {b.flagged > 0 && ` · ${b.flagged} held/failed`}
                      </div>
                    )}
                    <div className="chart-bar-stack">
                      {/* Stacked, not overlaid: the previous version drew the
                          high-severity bar on top of the total, so the visible
                          portion misrepresented its own magnitude. */}
                      <div
                        className="chart-seg"
                        style={{
                          height: `${(clean / axisMax) * 100}%`,
                          background: isHovered ? 'var(--primary-hover)' : 'var(--primary)',
                        }}
                      />
                      <div
                        className="chart-seg"
                        style={{
                          height: `${(b.flagged / axisMax) * 100}%`,
                          background: 'var(--warning)',
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="chart-xaxis">
            {buckets.map((b, i) => (
              // 24 labels will not fit; show every third.
              <span key={b.hour}>{i % 3 === 0 ? b.label : ''}</span>
            ))}
          </div>

          <p className="form-note">{coverage()}</p>
        </>
      )}
    </div>
  );
}
