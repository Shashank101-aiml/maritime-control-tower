import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Anchor, AlertTriangle, Send, Gauge, ScanSearch, RefreshCw, Search,
  Wind, Waves, ArrowUpRight, ChevronDown, Sparkles,
} from 'lucide-react';
import { predictCongestion, getAnomalies, getPortSnapshot } from '../services/congestionService';
import LoadingSpinner from '../components/LoadingSpinner';
import FreshnessIndicator from '../components/FreshnessIndicator';

const LIVE_SEVERITY_COLOR = {
  critical: 'var(--accent-rose)',
  high: 'var(--accent-rose)',
  warning: 'var(--accent-amber)',
  low: 'var(--accent-cyan)',
  info: 'var(--accent-emerald)',
};

const SORT_OPTIONS = [
  { value: 'anomaly', label: 'Most anomalous first' },
  { value: 'wave', label: 'Live wave height' },
  { value: 'wind', label: 'Live wind gusts' },
  { value: 'name', label: 'Port name (A-Z)' },
];

/** Small single-series trend line -- no axis, no library, just enough
 * to show direction and shape at a glance inside an expanded card. */
function Sparkline({ trend }) {
  if (!trend || trend.length < 2) return null;
  const width = 220;
  const height = 44;
  const values = trend.map((p) => p.congestion_index);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const stepX = width / (values.length - 1);
  const coords = values
    .map((v, i) => `${(i * stepX).toFixed(1)},${(height - ((v - min) / span) * height).toFixed(1)}`)
    .join(' ');
  const trendingUp = values[values.length - 1] > values[0];
  const color = trendingUp ? 'var(--accent-rose)' : 'var(--accent-emerald)';

  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: `${height}px`, display: 'block' }}>
      <polyline fill="none" stroke={color} strokeWidth="2" points={coords} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** One port's card: real anomaly score + real live weather, expandable
 * to a real recent trend and a "use this port's data" prefill for the
 * manual prediction form below. */
function PortCard({ anomaly, expanded, onToggle, snapshot, snapshotLoading, snapshotError, onUsePortData }) {
  const live = anomaly.live_conditions;
  const conditions = live?.conditions;
  const liveColor = live ? (LIVE_SEVERITY_COLOR[live.severity] || 'var(--text-subtle)') : null;

  return (
    <div style={{
      borderRadius: 'var(--radius)',
      background: anomaly.anomaly_detected ? 'var(--danger-soft)' : 'var(--surface-subtle)',
      border: `1px solid ${anomaly.anomaly_detected ? 'var(--accent-rose)' : 'var(--border)'}`,
      overflow: 'hidden',
    }}>
      <button
        type="button"
        onClick={onToggle}
        style={{
          width: '100%', textAlign: 'left', background: 'transparent', border: 'none', cursor: 'pointer',
          padding: '12px 14px', color: 'inherit', font: 'inherit',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
          <strong style={{ fontSize: '0.88rem', color: 'var(--text-strong)' }}>{anomaly.affected_region}</strong>
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span className="status-badge" style={{
              fontSize: '0.68rem', background: 'transparent',
              borderColor: anomaly.anomaly_detected ? 'var(--accent-rose)' : 'var(--text-subtle)',
              color: anomaly.anomaly_detected ? 'var(--accent-rose)' : 'var(--text-subtle)',
            }}>
              {anomaly.anomaly_detected ? 'ANOMALY' : 'NORMAL'} · {anomaly.anomaly_score.toFixed(3)}
            </span>
            <ChevronDown size={14} style={{ transform: expanded ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s' }} />
          </span>
        </div>

        <p style={{ fontSize: '0.76rem', color: 'var(--text-subtle)', lineHeight: 1.4, marginBottom: '8px' }}>{anomaly.reason}</p>

        {live ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.75rem', color: 'var(--text-body)' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: liveColor }}>
              <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: liveColor, display: 'inline-block' }} />
              Live now
            </span>
            {conditions?.wave_height_m != null && (
              <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                <Waves size={11} /> {conditions.wave_height_m.toFixed(1)} m
              </span>
            )}
            {conditions?.wind_gusts_kmh != null && (
              <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                <Wind size={11} /> {Math.round(conditions.wind_gusts_kmh)} km/h gusts
              </span>
            )}
          </div>
        ) : (
          <span style={{ fontSize: '0.75rem', color: 'var(--text-subtle)' }}>Live weather unavailable right now</span>
        )}
      </button>

      {expanded && (
        <div style={{ padding: '0 14px 14px', borderTop: '1px solid var(--border)', marginTop: '2px', paddingTop: '12px' }}>
          {snapshotLoading ? (
            <LoadingSpinner message="Loading real recent trend…" />
          ) : snapshotError ? (
            <p style={{ color: 'var(--accent-rose)', fontSize: '0.78rem' }}>{snapshotError}</p>
          ) : snapshot ? (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '4px' }}>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-subtle)' }}>
                  Congestion index — last {snapshot.trend.length} weeks (week of {snapshot.week_start})
                </span>
                <span style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-strong)' }}>
                  {snapshot.current.congestion_index.toFixed(2)}
                </span>
              </div>
              <Sparkline trend={snapshot.trend} />

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))', gap: '8px', margin: '10px 0' }}>
                <MiniStat label="Avg wait" value={`${snapshot.current.avg_wait_days.toFixed(1)}d`} />
                <MiniStat label="At anchor" value={Math.round(snapshot.current.vessels_at_anchor)} />
                <MiniStat label="Utilization" value={`${Math.round(snapshot.current.port_utilization_pct * 100)}%`} />
                <MiniStat label="Berth delay" value={`${snapshot.current.berth_delay_hrs.toFixed(1)}h`} />
              </div>

              <button
                type="button"
                className="btn-secondary"
                onClick={() => onUsePortData(anomaly.affected_region, snapshot.predict_inputs)}
                style={{ fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: '6px' }}
              >
                <Sparkles size={13} /> Use {anomaly.affected_region}'s real data in the form below <ArrowUpRight size={13} />
              </button>
            </>
          ) : null}
        </div>
      )}
    </div>
  );
}

function MiniStat({ label, value }) {
  return (
    <div style={{ background: 'var(--surface)', borderRadius: '6px', padding: '6px 8px' }}>
      <div style={{ fontSize: '0.65rem', color: 'var(--text-subtle)', textTransform: 'uppercase' }}>{label}</div>
      <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-strong)' }}>{value}</div>
    </div>
  );
}

/**
 * Real anomaly scan across every port with congestion history (Slice
 * 09) -- an Isolation Forest trained on the same real weekly data this
 * page's own model uses, scored against each port's own history. Each
 * card also carries a genuinely live weather reading at that port's
 * coordinates (same Open-Meteo pipeline as the Fleet Overview hazard
 * feed) -- the anomaly score itself only advances when new training
 * data lands, so it's labelled by the real week it's from rather than
 * implied to be live; the weather overlay is what's actually live here,
 * refreshed automatically.
 */
function AnomalyScanPanel({ onUsePortData }) {
  const [anomalies, setAnomalies] = useState(null);
  const [freshness, setFreshness] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState('anomaly');
  const [flaggedOnly, setFlaggedOnly] = useState(false);

  const [expandedPort, setExpandedPort] = useState(null);
  const [snapshots, setSnapshots] = useState({}); // port -> {data} | {error} | 'loading'

  const load = async () => {
    setError(null);
    try {
      const res = await getAnomalies();
      setAnomalies(res.anomalies);
      setFreshness(res.freshness);
    } catch (err) {
      setError(err.message);
      setAnomalies(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // Live weather is worth polling; the anomaly score itself changes
    // far less often, but re-fetching both together is one simple call.
    const interval = setInterval(load, 60000);
    return () => clearInterval(interval);
  }, []);

  const toggleExpand = async (port) => {
    if (expandedPort === port) {
      setExpandedPort(null);
      return;
    }
    setExpandedPort(port);
    if (snapshots[port] && snapshots[port] !== 'loading') return;
    setSnapshots((s) => ({ ...s, [port]: 'loading' }));
    try {
      const data = await getPortSnapshot(port);
      setSnapshots((s) => ({ ...s, [port]: { data } }));
    } catch (err) {
      setSnapshots((s) => ({ ...s, [port]: { error: err.message } }));
    }
  };

  const flagged = (anomalies || []).filter((a) => a.anomaly_detected);
  const liveCount = (anomalies || []).filter((a) => a.live_conditions).length;

  const visible = useMemo(() => {
    let list = anomalies || [];
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter((a) => a.affected_region.toLowerCase().includes(q));
    }
    if (flaggedOnly) {
      list = list.filter((a) => a.anomaly_detected);
    }
    const withWave = (a) => a.live_conditions?.conditions?.wave_height_m ?? -1;
    const withWind = (a) => a.live_conditions?.conditions?.wind_gusts_kmh ?? -1;
    switch (sortBy) {
      case 'wave':
        return [...list].sort((a, b) => withWave(b) - withWave(a));
      case 'wind':
        return [...list].sort((a, b) => withWind(b) - withWind(a));
      case 'name':
        return [...list].sort((a, b) => a.affected_region.localeCompare(b.affected_region));
      default:
        return list; // already sorted worst-first by the backend
    }
  }, [anomalies, search, flaggedOnly, sortBy]);

  return (
    <div className="glass-panel" style={{ padding: '24px', marginBottom: '24px' }}>
      <div className="section-header" style={{ marginBottom: '4px' }}>
        <h3 className="section-title" style={{ fontSize: '1.15rem' }}>
          <ScanSearch size={20} color="var(--accent-rose)" />
          Anomaly scan &amp; live port conditions
        </h3>
        <button className="btn-secondary" onClick={load} style={{ padding: '8px 14px' }}>
          <RefreshCw size={14} className={loading ? 'spin' : ''} />
        </button>
      </div>
      {freshness && <div style={{ marginBottom: '10px' }}><FreshnessIndicator freshness={freshness} /></div>}
      <p style={{ fontSize: '0.82rem', color: 'var(--text-subtle)', marginBottom: '14px' }}>
        The anomaly score is each port's latest real weekly congestion snapshot, scored by an Isolation
        Forest against that port's own history (pipeline/train_anomaly_model.py) -- it only changes when
        new training data lands, so it's labelled with the real week it's from, not presented as live.
        The weather reading on each card <em>is</em> live -- current wind and sea state at that port's
        coordinates, refreshed automatically.
      </p>

      {loading ? (
        <LoadingSpinner message="Scoring snapshots and fetching live conditions…" />
      ) : error ? (
        <p style={{ color: 'var(--accent-rose)', fontSize: '0.85rem' }}>{error}</p>
      ) : (
        <>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center', marginBottom: '14px' }}>
            <div style={{ position: 'relative', flex: '1 1 200px' }}>
              <Search size={13} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-subtle)' }} />
              <input
                className="form-input"
                placeholder="Search ports…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{ paddingLeft: '30px', fontSize: '0.82rem' }}
              />
            </div>
            <select className="form-select" value={sortBy} onChange={(e) => setSortBy(e.target.value)} style={{ fontSize: '0.82rem', width: 'auto' }}>
              {SORT_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', color: 'var(--text-body)', cursor: 'pointer' }}>
              <input type="checkbox" checked={flaggedOnly} onChange={(e) => setFlaggedOnly(e.target.checked)} />
              Flagged only
            </label>
          </div>

          <p style={{ fontSize: '0.85rem', color: 'var(--text-body)', marginBottom: '12px' }}>
            {flagged.length === 0
              ? `No anomalies flagged across ${anomalies.length} monitored ports.`
              : `${flagged.length} of ${anomalies.length} ports flagged as anomalous.`}
            {' '}{liveCount} of {anomalies.length} reporting live weather right now.
            {visible.length !== anomalies.length && ` Showing ${visible.length}.`}
          </p>

          {visible.length === 0 ? (
            <p style={{ color: 'var(--text-subtle)', fontSize: '0.85rem', textAlign: 'center', padding: '20px' }}>
              No ports match this search/filter.
            </p>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '10px' }}>
              {visible.map((a) => {
                const entry = snapshots[a.affected_region];
                return (
                  <PortCard
                    key={a.affected_region}
                    anomaly={a}
                    expanded={expandedPort === a.affected_region}
                    onToggle={() => toggleExpand(a.affected_region)}
                    snapshot={entry && entry !== 'loading' ? entry.data : null}
                    snapshotLoading={entry === 'loading'}
                    snapshotError={entry && entry !== 'loading' ? entry.error : null}
                    onUsePortData={onUsePortData}
                  />
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}

const SOURCE_BY_ENTITY = {
  vessel: [
    { value: 'global_loitering_weekly', label: 'Global loitering (weekly, vessel history)' },
    { value: 'la_lb_visit_2023h2', label: 'LA/Long Beach visit (static vessel specs)' },
  ],
  port: [
    { value: 'port_congestion_2019_2024', label: 'Named port (weekly, lagged metrics)' },
  ],
};

const DEFAULT_FORM = {
  entity_type: 'vessel',
  source: 'global_loitering_weekly',
  last_lat: '25.0',
  last_lon: '-80.0',
  month: 7,
  quarter: 3,
  events_last_4w: '2',
  events_last_12w: '5',
  duration_last_4w_hours: '30',
  avg_speed_last_4w_knots: '2.5',
  cumulative_events_to_date: '15',
  weeks_since_last_event: '1',
  vessel_type: '80',
  length: '250',
  width: '32',
  draft: '12',
  region: 'Asia',
  congestion_index_lag1w: '1.5',
  congestion_index_roll4w_mean: '1.6',
  avg_wait_days_lag1w: '15',
  vessels_at_anchor_lag1w: '5',
};

export default function CongestionPredictor() {
  const [form, setForm] = useState(DEFAULT_FORM);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [prefillNote, setPrefillNote] = useState(null);
  const formRef = useRef(null);

  const update = (field, value) => {
    setForm((f) => ({ ...f, [field]: value }));
    setPrefillNote(null);
  };

  const handleEntityChange = (entityType) => {
    setForm((f) => ({ ...f, entity_type: entityType, source: SOURCE_BY_ENTITY[entityType][0].value }));
    setPrefillNote(null);
  };

  const handleUsePortData = (port, predictInputs) => {
    setForm((f) => ({
      ...f,
      entity_type: 'port',
      source: 'port_congestion_2019_2024',
      region: predictInputs.region ?? f.region,
      congestion_index_lag1w: predictInputs.congestion_index_lag1w ?? '',
      congestion_index_roll4w_mean: predictInputs.congestion_index_roll4w_mean ?? '',
      avg_wait_days_lag1w: predictInputs.avg_wait_days_lag1w ?? '',
      vessels_at_anchor_lag1w: predictInputs.vessels_at_anchor_lag1w ?? '',
    }));
    setResult(null);
    setError(null);
    setPrefillNote(port);
    formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const numOrNull = (v) => (v === '' || v === undefined ? null : Number(v));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const payload = {
        entity_type: form.entity_type,
        source: form.source,
        last_lat: numOrNull(form.last_lat),
        last_lon: numOrNull(form.last_lon),
        month: Number(form.month),
        quarter: Number(form.quarter),
      };

      if (form.source === 'global_loitering_weekly') {
        Object.assign(payload, {
          events_last_4w: numOrNull(form.events_last_4w),
          events_last_12w: numOrNull(form.events_last_12w),
          duration_last_4w_hours: numOrNull(form.duration_last_4w_hours),
          avg_speed_last_4w_knots: numOrNull(form.avg_speed_last_4w_knots),
          cumulative_events_to_date: numOrNull(form.cumulative_events_to_date),
          weeks_since_last_event: numOrNull(form.weeks_since_last_event),
        });
      } else if (form.source === 'la_lb_visit_2023h2') {
        Object.assign(payload, {
          vessel_type: numOrNull(form.vessel_type),
          length: numOrNull(form.length),
          width: numOrNull(form.width),
          draft: numOrNull(form.draft),
        });
      } else if (form.source === 'port_congestion_2019_2024') {
        Object.assign(payload, {
          region: form.region,
          congestion_index_lag1w: numOrNull(form.congestion_index_lag1w),
          congestion_index_roll4w_mean: numOrNull(form.congestion_index_roll4w_mean),
          avg_wait_days_lag1w: numOrNull(form.avg_wait_days_lag1w),
          vessels_at_anchor_lag1w: numOrNull(form.vessels_at_anchor_lag1w),
        });
      }

      const response = await predictCongestion(payload);
      if (response.status !== 'COMPLETED') {
        setError(response.error || `Request returned status: ${response.status}`);
      } else {
        setResult(response.prediction);
      }
    } catch (err) {
      setError(err.message || 'Prediction failed');
    } finally {
      setLoading(false);
    }
  };

  const isCongested = result?.congestion_flag === 1;

  return (
    <div className="page-wrapper">
      <div className="section-header" style={{ marginBottom: '24px' }}>
        <div>
          <h1 className="section-title" style={{ fontSize: '1.8rem', color: 'var(--text-strong)' }}>
            <Anchor size={28} color="var(--accent-cyan)" />
            Congestion Prediction
          </h1>
          <p style={{ color: 'var(--text-muted)', marginTop: '4px' }}>
            Predicts congestion likelihood for a vessel or a named port, trained across three real data sources.
          </p>
        </div>
      </div>

      <AnomalyScanPanel onUsePortData={handleUsePortData} />

      <div className="glass-panel" ref={formRef}>
        {prefillNote && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px',
            padding: '10px 14px', borderRadius: 'var(--radius)',
            background: 'var(--info-soft, var(--surface-subtle))', border: '1px solid var(--accent-cyan)',
            fontSize: '0.82rem', color: 'var(--text-body)',
          }}>
            <Sparkles size={14} color="var(--accent-cyan)" />
            Prefilled with {prefillNote}'s real latest data. Adjust anything below, or hit Predict as-is.
          </div>
        )}
        <form className="predict-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Entity Type</label>
            <select className="form-select" value={form.entity_type} onChange={(e) => handleEntityChange(e.target.value)}>
              <option value="vessel">Vessel</option>
              <option value="port">Port</option>
            </select>
          </div>

          <div className="form-group span-2">
            <label className="form-label">Data Source</label>
            <select className="form-select" value={form.source} onChange={(e) => update('source', e.target.value)}>
              {SOURCE_BY_ENTITY[form.entity_type].map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Latitude</label>
            <input className="form-input" type="number" step="any" value={form.last_lat} onChange={(e) => update('last_lat', e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">Longitude</label>
            <input className="form-input" type="number" step="any" value={form.last_lon} onChange={(e) => update('last_lon', e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">Month</label>
            <input className="form-input" type="number" min="1" max="12" value={form.month} onChange={(e) => update('month', e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">Quarter</label>
            <input className="form-input" type="number" min="1" max="4" value={form.quarter} onChange={(e) => update('quarter', e.target.value)} />
          </div>

          {form.source === 'global_loitering_weekly' && (
            <>
              <div className="form-group">
                <label className="form-label">Events (last 4w)</label>
                <input className="form-input" type="number" min="0" value={form.events_last_4w} onChange={(e) => update('events_last_4w', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Events (last 12w)</label>
                <input className="form-input" type="number" min="0" value={form.events_last_12w} onChange={(e) => update('events_last_12w', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Loitering Duration (last 4w, hrs)</label>
                <input className="form-input" type="number" min="0" value={form.duration_last_4w_hours} onChange={(e) => update('duration_last_4w_hours', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Avg Speed (last 4w, knots)</label>
                <input className="form-input" type="number" step="any" value={form.avg_speed_last_4w_knots} onChange={(e) => update('avg_speed_last_4w_knots', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Cumulative Events To Date</label>
                <input className="form-input" type="number" min="0" value={form.cumulative_events_to_date} onChange={(e) => update('cumulative_events_to_date', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Weeks Since Last Event</label>
                <input className="form-input" type="number" min="0" value={form.weeks_since_last_event} onChange={(e) => update('weeks_since_last_event', e.target.value)} />
              </div>
            </>
          )}

          {form.source === 'la_lb_visit_2023h2' && (
            <>
              <div className="form-group">
                <label className="form-label">Vessel Type (AIS code)</label>
                <input className="form-input" type="number" value={form.vessel_type} onChange={(e) => update('vessel_type', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Length (m)</label>
                <input className="form-input" type="number" value={form.length} onChange={(e) => update('length', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Width (m)</label>
                <input className="form-input" type="number" value={form.width} onChange={(e) => update('width', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Draft (m)</label>
                <input className="form-input" type="number" step="any" value={form.draft} onChange={(e) => update('draft', e.target.value)} />
              </div>
            </>
          )}

          {form.source === 'port_congestion_2019_2024' && (
            <>
              <div className="form-group">
                <label className="form-label">Region</label>
                <input className="form-input" value={form.region} onChange={(e) => update('region', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Congestion Index (1 week ago)</label>
                <input className="form-input" type="number" step="any" value={form.congestion_index_lag1w} onChange={(e) => update('congestion_index_lag1w', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Congestion Index (4w avg)</label>
                <input className="form-input" type="number" step="any" value={form.congestion_index_roll4w_mean} onChange={(e) => update('congestion_index_roll4w_mean', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Avg Wait Days (1 week ago)</label>
                <input className="form-input" type="number" step="any" value={form.avg_wait_days_lag1w} onChange={(e) => update('avg_wait_days_lag1w', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Vessels At Anchor (1 week ago)</label>
                <input className="form-input" type="number" min="0" value={form.vessels_at_anchor_lag1w} onChange={(e) => update('vessels_at_anchor_lag1w', e.target.value)} />
              </div>
            </>
          )}

          <div className="form-actions">
            <button className="btn-action" type="submit" disabled={loading}>
              <Send size={16} className={loading ? 'spin' : ''} />
              {loading ? 'Predicting…' : 'Predict Congestion'}
            </button>
          </div>
        </form>

        {loading && <LoadingSpinner message="Running congestion model…" />}

        {error && (
          <div className="prediction-result">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-rose)' }}>
              <AlertTriangle size={18} /> {error}
            </div>
          </div>
        )}

        {result && (
          <div className="prediction-result">
            <h3 className="section-title" style={{ fontSize: '1.1rem' }}>Prediction</h3>
            <div className="result-metric-grid">
              <div className="result-metric">
                <div className="result-metric-label">Congestion Probability</div>
                <div className="result-metric-value" style={{ color: isCongested ? 'var(--accent-rose)' : 'var(--accent-emerald)' }}>
                  {(result.congestion_probability * 100).toFixed(1)}%
                </div>
              </div>
              <div className="result-metric">
                <div className="result-metric-label">Assessment</div>
                <div className="result-metric-value" style={{ color: isCongested ? 'var(--accent-rose)' : 'var(--accent-emerald)' }}>
                  {isCongested ? 'Congested' : 'Clear'}
                </div>
              </div>
              <div className="result-metric">
                <div className="result-metric-label">
                  <Gauge size={12} style={{ display: 'inline', marginRight: '4px' }} />
                  Model Confidence
                </div>
                <div className="result-metric-value" style={{ color: 'var(--accent-amber)' }}>
                  {(result.confidence * 100).toFixed(0)}%
                </div>
              </div>
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '14px' }}>
              Trained across three sources with different congestion definitions (loitering events, AIS waiting-area
              flags, port-index thresholds) — treat this as one model adapting per source, not one uniform definition.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
