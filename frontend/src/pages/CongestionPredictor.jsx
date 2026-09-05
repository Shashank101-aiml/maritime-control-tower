import React, { useEffect, useState } from 'react';
import { Anchor, AlertTriangle, Send, Gauge, ScanSearch, RefreshCw } from 'lucide-react';
import { predictCongestion, getAnomalies } from '../services/congestionService';
import LoadingSpinner from '../components/LoadingSpinner';

/**
 * Real anomaly scan across every port with congestion history (Slice
 * 09) -- an Isolation Forest trained on the same real weekly data this
 * page's own model uses, scored against each port's own history. Not
 * the same thing as the manual prediction form below: this is "is
 * today's real snapshot unusual for this specific port," not "what's
 * the congestion probability for a hypothetical input."
 */
function AnomalyScanPanel() {
  const [anomalies, setAnomalies] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setAnomalies(await getAnomalies());
    } catch (err) {
      setError(err.message);
      setAnomalies(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const flagged = (anomalies || []).filter((a) => a.anomaly_detected);

  return (
    <div className="glass-panel" style={{ padding: '24px', marginBottom: '24px' }}>
      <div className="section-header" style={{ marginBottom: '12px' }}>
        <h3 className="section-title" style={{ fontSize: '1.15rem' }}>
          <ScanSearch size={20} color="var(--accent-rose)" />
          Real-time anomaly scan
        </h3>
        <button className="btn-secondary" onClick={load} style={{ padding: '8px 14px' }}>
          <RefreshCw size={14} className={loading ? 'spin' : ''} />
        </button>
      </div>
      <p style={{ fontSize: '0.82rem', color: 'var(--text-subtle)', marginBottom: '14px' }}>
        Each port's latest real weekly congestion snapshot, scored by an Isolation Forest against that
        port's own history (pipeline/train_anomaly_model.py) -- unsupervised, since there's no labeled
        "anomaly" ground truth to train against.
      </p>

      {loading ? (
        <LoadingSpinner message="Scoring live snapshots against historical distributions…" />
      ) : error ? (
        <p style={{ color: 'var(--accent-rose)', fontSize: '0.85rem' }}>{error}</p>
      ) : (
        <>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-body)', marginBottom: '12px' }}>
            {flagged.length === 0
              ? `No anomalies flagged across ${anomalies.length} monitored ports.`
              : `${flagged.length} of ${anomalies.length} ports flagged as anomalous right now.`}
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '10px' }}>
            {anomalies.map((a) => (
              <div key={a.affected_region} style={{
                padding: '12px 14px', borderRadius: 'var(--radius)',
                background: a.anomaly_detected ? 'var(--danger-soft)' : 'var(--surface-subtle)',
                border: `1px solid ${a.anomaly_detected ? 'var(--accent-rose)' : 'var(--border)'}`,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                  <strong style={{ fontSize: '0.88rem', color: 'var(--text-strong)' }}>{a.affected_region}</strong>
                  <span className="status-badge" style={{
                    fontSize: '0.68rem',
                    background: 'transparent',
                    borderColor: a.anomaly_detected ? 'var(--accent-rose)' : 'var(--text-subtle)',
                    color: a.anomaly_detected ? 'var(--accent-rose)' : 'var(--text-subtle)',
                  }}>
                    {a.anomaly_detected ? 'ANOMALY' : 'NORMAL'} · {a.anomaly_score.toFixed(3)}
                  </span>
                </div>
                <p style={{ fontSize: '0.76rem', color: 'var(--text-subtle)', lineHeight: 1.4 }}>{a.reason}</p>
              </div>
            ))}
          </div>
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

  const update = (field, value) => setForm((f) => ({ ...f, [field]: value }));

  const handleEntityChange = (entityType) => {
    setForm((f) => ({ ...f, entity_type: entityType, source: SOURCE_BY_ENTITY[entityType][0].value }));
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

      <AnomalyScanPanel />

      <div className="glass-panel">
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
