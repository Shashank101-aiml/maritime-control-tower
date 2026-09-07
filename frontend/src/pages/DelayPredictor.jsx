import React, { useEffect, useState, useRef } from 'react';
import { Clock, AlertTriangle, Send, Gauge, BarChart3, ArrowUpRight, Sparkles, RefreshCw } from 'lucide-react';
import { predictDelay, getDelayOverview, getPlantProfile } from '../services/delayService';
import LoadingSpinner from '../components/LoadingSpinner';

const BREAKDOWN_TABS = [
  { value: 'plant_code', label: 'By plant' },
  { value: 'carrier', label: 'By carrier' },
  { value: 'service_level', label: 'By service level' },
  { value: 'origin_port', label: 'By origin port' },
];

const FIELD_FOR_TAB = {
  carrier: 'carrier',
  service_level: 'service_level',
  origin_port: 'origin_port',
};

/**
 * Real historical shape of the shipment-delay training data -- overall
 * and per-category late rates, computed from the same 9,215 real
 * orders the model was trained on. Clicking a row either sets that
 * field directly (carrier/service level/origin port) or, for a plant,
 * loads and prefills its full real profile below (the numeric freight/
 * warehouse fields the old form never collected at all).
 */
function DelayOverviewPanel({ overview, loading, error, onReload, onSelectField, onUsePlantProfile, setActiveTab }) {
  const [tab, setTab] = useState('plant_code');
  const [profileLoadingFor, setProfileLoadingFor] = useState(null);
  const [profileError, setProfileError] = useState(null);

  const handleRowClick = async (item) => {
    if (tab === 'plant_code') {
      setProfileLoadingFor(item.value);
      setProfileError(null);
      try {
        const profile = await getPlantProfile(item.value);
        onUsePlantProfile(profile);
      } catch (err) {
        setProfileError(err.message);
      } finally {
        setProfileLoadingFor(null);
      }
    } else {
      onSelectField(FIELD_FOR_TAB[tab], item.value);
    }
  };

  return (
    <div className="glass-panel" style={{ padding: '24px', marginBottom: '24px' }}>
      <div className="section-header" style={{ marginBottom: '4px' }}>
        <h3 className="section-title" style={{ fontSize: '1.15rem' }}>
          <BarChart3 size={20} color="var(--accent-teal, var(--accent-cyan))" />
          Delay risk overview
        </h3>
        <button className="btn-secondary" onClick={onReload} style={{ padding: '8px 14px' }}>
          <RefreshCw size={14} className={loading ? 'spin' : ''} />
        </button>
      </div>
      <p style={{ fontSize: '0.82rem', color: 'var(--text-subtle)', marginBottom: '14px' }}>
        Real late-rate breakdown from all {overview?.orders?.toLocaleString() || '…'} historical orders the model
        was trained on (pipeline/train_delay_model.py). This dataset's port/plant codes are anonymized and
        unrelated to the real named maritime ports the Congestion tab scores -- shown separately below, not
        merged into one fake identity.
      </p>

      {loading ? (
        <LoadingSpinner message="Loading real historical breakdown…" />
      ) : error ? (
        <p style={{ color: 'var(--accent-rose)', fontSize: '0.85rem' }}>{error}</p>
      ) : overview ? (
        <>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginBottom: '16px' }}>
            <StatPill label="Overall late rate" value={`${(overview.overall_late_rate * 100).toFixed(1)}%`} />
            <StatPill label="Historical orders" value={overview.orders.toLocaleString()} />
            {overview.live_fleet_context && (
              <button
                type="button"
                onClick={() => setActiveTab?.('congestion')}
                title="Not a model input -- real live context from the Congestion tab"
                style={{
                  display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.78rem',
                  background: 'var(--surface-subtle)', border: '1px solid var(--border)',
                  borderRadius: '999px', padding: '6px 12px', color: 'var(--text-body)', cursor: 'pointer',
                }}
              >
                <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--accent-amber)', display: 'inline-block' }} />
                {overview.live_fleet_context.flagged_ports} of {overview.live_fleet_context.monitored_ports} monitored ports flagged live
                <ArrowUpRight size={12} />
              </button>
            )}
          </div>

          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '12px' }}>
            {BREAKDOWN_TABS.map((t) => (
              <button
                key={t.value}
                type="button"
                onClick={() => setTab(t.value)}
                className={tab === t.value ? 'btn-action' : 'btn-secondary'}
                style={{ fontSize: '0.76rem', padding: '6px 12px' }}
              >
                {t.label}
              </button>
            ))}
          </div>

          {profileError && <p style={{ color: 'var(--accent-rose)', fontSize: '0.78rem', marginBottom: '8px' }}>{profileError}</p>}

          <BreakdownBars
            items={overview.breakdown[tab] || []}
            onRowClick={handleRowClick}
            loadingValue={tab === 'plant_code' ? profileLoadingFor : null}
            clickHint={tab === 'plant_code' ? "Click to use this plant's real profile" : 'Click to use this value'}
          />
        </>
      ) : null}
    </div>
  );
}

function StatPill({ label, value }) {
  return (
    <div style={{
      background: 'var(--surface-subtle)', border: '1px solid var(--border)', borderRadius: '999px',
      padding: '6px 14px', fontSize: '0.78rem', color: 'var(--text-body)',
    }}>
      <span style={{ color: 'var(--text-subtle)' }}>{label}: </span>
      <strong style={{ color: 'var(--text-strong)' }}>{value}</strong>
    </div>
  );
}

function BreakdownBars({ items, onRowClick, loadingValue, clickHint }) {
  if (!items.length) return <p style={{ color: 'var(--text-subtle)', fontSize: '0.82rem' }}>No data for this breakdown.</p>;
  const maxRate = Math.max(...items.map((i) => i.late_rate), 0.001);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {items.map((item) => (
        <button
          key={item.value}
          type="button"
          onClick={() => onRowClick(item)}
          title={clickHint}
          disabled={loadingValue === item.value}
          style={{
            display: 'flex', alignItems: 'center', gap: '10px', background: 'transparent',
            border: 'none', padding: '4px 2px', cursor: 'pointer', width: '100%', textAlign: 'left',
          }}
        >
          <span style={{ width: '110px', flexShrink: 0, fontSize: '0.8rem', color: 'var(--text-body)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {loadingValue === item.value ? 'Loading…' : item.value}
          </span>
          <span style={{ flex: 1, background: 'var(--surface-subtle)', borderRadius: '4px', height: '16px', position: 'relative', overflow: 'hidden' }}>
            <span style={{
              position: 'absolute', inset: 0, width: `${Math.max(2, (item.late_rate / maxRate) * 100)}%`,
              background: item.late_rate > 0 ? 'var(--accent-rose)' : 'var(--accent-emerald)', opacity: 0.75,
            }} />
          </span>
          <span style={{ width: '46px', flexShrink: 0, fontSize: '0.78rem', textAlign: 'right', color: 'var(--text-strong)', fontWeight: 600 }}>
            {(item.late_rate * 100).toFixed(1)}%
          </span>
          <span style={{ width: '70px', flexShrink: 0, fontSize: '0.72rem', textAlign: 'right', color: 'var(--text-subtle)' }}>
            {item.orders.toLocaleString()} orders
          </span>
        </button>
      ))}
    </div>
  );
}

const buildDefaultForm = (overview) => ({
  origin_port: overview.known_values.origin_port[0] || '',
  destination_port: overview.known_values.destination_port[0] || '',
  carrier: overview.known_values.carrier[0] || '',
  service_level: overview.known_values.service_level[0] || '',
  customer: overview.known_values.customer[0] || '',
  plant_code: overview.known_values.plant_code[0] || '',
  tpt: 1,
  unit_quantity: 500,
  weight: 10,
  freight_rate: '',
  freight_min_cost: '',
  wh_cost_per_unit: '',
  wh_daily_capacity: '',
  plant_week_order_count: '',
  backlog_vs_capacity: '',
  is_vmi_customer_anywhere: false,
});

export default function DelayPredictor({ setActiveTab }) {
  const [overview, setOverview] = useState(null);
  const [overviewLoading, setOverviewLoading] = useState(true);
  const [overviewError, setOverviewError] = useState(null);

  const [form, setForm] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [prefillNote, setPrefillNote] = useState(null);
  const formRef = useRef(null);

  const loadOverview = async () => {
    setOverviewLoading(true);
    setOverviewError(null);
    try {
      const data = await getDelayOverview();
      setOverview(data);
    } catch (err) {
      setOverviewError(err.message);
    } finally {
      setOverviewLoading(false);
    }
  };

  useEffect(() => { loadOverview(); }, []);

  // Only ever seeds the form once, from real data -- never overwrites
  // values the user (or a prefill) has already set.
  useEffect(() => {
    if (overview && !form) setForm(buildDefaultForm(overview));
  }, [overview, form]);

  const update = (field, value) => {
    setPrefillNote(null);
    setForm((f) => {
      const next = { ...f, [field]: value };
      // Plant Code and Origin Port are really related in this data
      // (data/cleaned/supply_chain/plant_ports.csv) -- picking a plant
      // keeps the origin port a real combination instead of leaving
      // whatever was there before.
      if (field === 'plant_code') {
        const realPorts = overview?.plant_ports?.[value];
        if (realPorts?.length) next.origin_port = realPorts[0];
      }
      return next;
    });
  };

  const handleSelectField = (field, value) => update(field, value);

  const handleUsePlantProfile = (profileResponse) => {
    const p = profileResponse.profile;
    setForm((f) => ({
      ...f,
      plant_code: profileResponse.plant_code,
      origin_port: p.origin_port ?? f.origin_port,
      destination_port: p.destination_port ?? f.destination_port,
      carrier: p.carrier ?? f.carrier,
      service_level: p.service_level ?? f.service_level,
      customer: p.customer ?? f.customer,
      tpt: p.tpt ?? f.tpt,
      unit_quantity: p.unit_quantity ?? f.unit_quantity,
      weight: p.weight ?? f.weight,
      freight_rate: p.freight_rate ?? '',
      freight_min_cost: p.freight_min_cost ?? '',
      wh_cost_per_unit: p.wh_cost_per_unit ?? '',
      wh_daily_capacity: p.wh_daily_capacity ?? '',
      plant_week_order_count: p.plant_week_order_count ?? '',
      backlog_vs_capacity: p.backlog_vs_capacity ?? '',
      is_vmi_customer_anywhere: p.is_vmi_customer_anywhere ?? f.is_vmi_customer_anywhere,
    }));
    setResult(null);
    setError(null);
    setPrefillNote(profileResponse.plant_code);
    formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const numOrNull = (v) => (v === '' || v === undefined || v === null ? null : Number(v));
  // wh_daily_capacity / plant_week_order_count are integers in the API
  // schema; a real per-plant median can land on a .5, same as tpt/
  // unit_quantity above.
  const intOrNull = (v) => (v === '' || v === undefined || v === null ? null : Math.round(Number(v)));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await predictDelay({
        origin_port: form.origin_port,
        destination_port: form.destination_port,
        carrier: form.carrier,
        service_level: form.service_level,
        customer: form.customer,
        plant_code: form.plant_code,
        // The API's schema takes these as integers, but a real plant
        // profile's median can legitimately land on a .5 (an even-sized
        // group of otherwise-whole-number orders) -- round only at
        // submission time so the form itself keeps showing the real,
        // unrounded historical figure.
        tpt: Math.round(Number(form.tpt)),
        unit_quantity: Math.round(Number(form.unit_quantity)),
        weight: Number(form.weight),
        freight_rate: numOrNull(form.freight_rate),
        freight_min_cost: numOrNull(form.freight_min_cost),
        wh_cost_per_unit: numOrNull(form.wh_cost_per_unit),
        wh_daily_capacity: intOrNull(form.wh_daily_capacity),
        plant_week_order_count: intOrNull(form.plant_week_order_count),
        backlog_vs_capacity: numOrNull(form.backlog_vs_capacity),
        is_vmi_customer_anywhere: form.is_vmi_customer_anywhere,
      });
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

  const isLate = result?.is_late_flag === 1;

  return (
    <div className="page-wrapper">
      <div className="section-header" style={{ marginBottom: '24px' }}>
        <div>
          <h1 className="section-title" style={{ fontSize: '1.8rem', color: 'var(--text-strong)' }}>
            <Clock size={28} color="var(--accent-teal)" />
            Shipment Delay Prediction
          </h1>
          <p style={{ color: 'var(--text-muted)', marginTop: '4px' }}>
            Predicts the probability an order ships late, based on carrier, route, and plant capacity context.
          </p>
        </div>
      </div>

      <DelayOverviewPanel
        overview={overview}
        loading={overviewLoading}
        error={overviewError}
        onReload={loadOverview}
        onSelectField={handleSelectField}
        onUsePlantProfile={handleUsePlantProfile}
        setActiveTab={setActiveTab}
      />

      <div className="glass-panel" ref={formRef}>
        {!form ? (
          <LoadingSpinner message="Loading real category options…" />
        ) : (
          <>
            {prefillNote && (
              <div style={{
                display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px',
                padding: '10px 14px', borderRadius: 'var(--radius)',
                background: 'var(--surface-subtle)', border: '1px solid var(--accent-cyan)',
                fontSize: '0.82rem', color: 'var(--text-body)',
              }}>
                <Sparkles size={14} color="var(--accent-cyan)" />
                Prefilled with {prefillNote}'s real historical profile. Adjust anything below, or hit Predict as-is.
              </div>
            )}
            <form className="predict-form" onSubmit={handleSubmit}>
              <div className="form-group">
                <label className="form-label">Origin Port</label>
                <select className="form-select" value={form.origin_port} onChange={(e) => update('origin_port', e.target.value)}>
                  {overview.known_values.origin_port.map((v) => <option key={v} value={v}>{v}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Destination Port</label>
                <select className="form-select" value={form.destination_port} onChange={(e) => update('destination_port', e.target.value)}>
                  {overview.known_values.destination_port.map((v) => <option key={v} value={v}>{v}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Carrier</label>
                <select className="form-select" value={form.carrier} onChange={(e) => update('carrier', e.target.value)}>
                  {overview.known_values.carrier.map((v) => <option key={v} value={v}>{v}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Service Level</label>
                <select className="form-select" value={form.service_level} onChange={(e) => update('service_level', e.target.value)}>
                  {overview.known_values.service_level.map((v) => <option key={v} value={v}>{v}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Customer</label>
                <select className="form-select" value={form.customer} onChange={(e) => update('customer', e.target.value)}>
                  {overview.known_values.customer.map((v) => <option key={v} value={v}>{v}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Plant Code</label>
                <select className="form-select" value={form.plant_code} onChange={(e) => update('plant_code', e.target.value)}>
                  {overview.known_values.plant_code.map((v) => <option key={v} value={v}>{v}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Transit Time (days)</label>
                <input className="form-input" type="number" min="0" step="any" value={form.tpt} onChange={(e) => update('tpt', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Unit Quantity</label>
                <input className="form-input" type="number" min="0" step="any" value={form.unit_quantity} onChange={(e) => update('unit_quantity', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Weight</label>
                <input className="form-input" type="number" min="0" step="any" value={form.weight} onChange={(e) => update('weight', e.target.value)} />
              </div>
              <div className="form-group" style={{ justifyContent: 'flex-end' }}>
                <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <input
                    type="checkbox"
                    checked={form.is_vmi_customer_anywhere}
                    onChange={(e) => update('is_vmi_customer_anywhere', e.target.checked)}
                  />
                  VMI Customer
                </label>
              </div>

              <div className="form-group span-2" style={{ marginTop: '8px' }}>
                <p className="form-note" style={{ margin: 0 }}>
                  Real per-plant freight &amp; warehouse figures -- the model was trained with these, but the
                  original form never collected them. Click a plant above to fill them from its real historical
                  profile, or enter your own.
                </p>
              </div>
              <div className="form-group">
                <label className="form-label">Freight Rate</label>
                <input className="form-input" type="number" step="any" value={form.freight_rate} onChange={(e) => update('freight_rate', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Freight Min Cost</label>
                <input className="form-input" type="number" step="any" value={form.freight_min_cost} onChange={(e) => update('freight_min_cost', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Warehouse Cost / Unit</label>
                <input className="form-input" type="number" step="any" value={form.wh_cost_per_unit} onChange={(e) => update('wh_cost_per_unit', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Warehouse Daily Capacity</label>
                <input className="form-input" type="number" step="any" value={form.wh_daily_capacity} onChange={(e) => update('wh_daily_capacity', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Plant Week Order Count</label>
                <input className="form-input" type="number" step="any" value={form.plant_week_order_count} onChange={(e) => update('plant_week_order_count', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Backlog vs Capacity</label>
                <input className="form-input" type="number" step="any" value={form.backlog_vs_capacity} onChange={(e) => update('backlog_vs_capacity', e.target.value)} />
              </div>

              <div className="form-actions">
                <button className="btn-action" type="submit" disabled={loading}>
                  <Send size={16} className={loading ? 'spin' : ''} />
                  {loading ? 'Predicting…' : 'Predict Delay Risk'}
                </button>
              </div>
            </form>
          </>
        )}

        {loading && <LoadingSpinner message="Running delay prediction model…" />}

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
                <div className="result-metric-label">Late Probability</div>
                <div className="result-metric-value" style={{ color: isLate ? 'var(--accent-rose)' : 'var(--accent-emerald)' }}>
                  {(result.late_probability * 100).toFixed(1)}%
                </div>
              </div>
              <div className="result-metric">
                <div className="result-metric-label">Assessment</div>
                <div className="result-metric-value" style={{ color: isLate ? 'var(--accent-rose)' : 'var(--accent-emerald)' }}>
                  {isLate ? 'Likely Late' : 'On Time'}
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
              Trained on a small, imbalanced historical sample (~2% of orders were late) — treat as directional, not precise.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
