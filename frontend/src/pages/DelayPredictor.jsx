import React, { useEffect, useState, useRef } from 'react';
import {
  Clock, AlertTriangle, Send, Gauge, BarChart3, ArrowUpRight, Sparkles, RefreshCw,
  Ship, Package, Warehouse, ChevronDown, CheckCircle2, TrendingUp, TrendingDown, Info,
} from 'lucide-react';
import { predictDelay, getDelayOverview, getPlantProfile } from '../services/delayService';
import LoadingSpinner from '../components/LoadingSpinner';

const OPTIONAL_PROFILE_FIELDS = [
  'freight_rate', 'freight_min_cost', 'wh_cost_per_unit',
  'wh_daily_capacity', 'plant_week_order_count', 'backlog_vs_capacity',
];

function FormSection({ icon, title, subtitle, children }) {
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginBottom: '12px' }}>
        <span style={{ display: 'flex', color: 'var(--accent-teal, var(--accent-cyan))' }}>{icon}</span>
        <h4 style={{ fontSize: '0.92rem', fontWeight: 600, color: 'var(--text-strong)', margin: 0 }}>{title}</h4>
        {subtitle && <span style={{ fontSize: '0.76rem', color: 'var(--text-subtle)' }}>{subtitle}</span>}
      </div>
      <div className="predict-form">{children}</div>
    </div>
  );
}

/**
 * Where this prediction's probability sits against two real reference
 * points -- the overall historical late rate and (when the selected
 * plant has its own history) that plant's real rate -- rather than a
 * bare percentage with nothing to compare it to.
 */
function RateComparisonMeter({ predictedRate, overallRate, plantRate, plantLabel }) {
  const scaleMax = Math.max(predictedRate, overallRate, plantRate ?? 0, 0.02) * 1.3;
  const pct = (v) => `${Math.min(100, (v / scaleMax) * 100)}%`;
  const predictedColor = predictedRate >= 0.5 ? 'var(--accent-rose)' : predictedRate > overallRate ? 'var(--accent-amber)' : 'var(--accent-emerald)';

  return (
    <div>
      <div style={{ position: 'relative', height: '24px', background: 'var(--surface-subtle)', borderRadius: '999px', overflow: 'hidden', border: '1px solid var(--border)' }}>
        <div style={{ position: 'absolute', inset: 0, width: pct(predictedRate), background: predictedColor, opacity: 0.85, transition: 'width 0.3s ease' }} />
        <div title={`Overall real late rate: ${(overallRate * 100).toFixed(1)}%`}
          style={{ position: 'absolute', left: pct(overallRate), top: 0, bottom: 0, width: '2px', background: 'var(--text-strong)' }} />
        {plantRate != null && (
          <div title={`${plantLabel}'s real late rate: ${(plantRate * 100).toFixed(1)}%`}
            style={{ position: 'absolute', left: pct(plantRate), top: 0, bottom: 0, width: '2px', background: 'var(--accent-cyan)' }} />
        )}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '14px', marginTop: '8px', fontSize: '0.74rem', color: 'var(--text-subtle)' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <span style={{ width: '10px', height: '10px', borderRadius: '2px', background: predictedColor, display: 'inline-block' }} />
          This prediction: <strong style={{ color: 'var(--text-strong)' }}>{(predictedRate * 100).toFixed(1)}%</strong>
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <span style={{ width: '2px', height: '10px', background: 'var(--text-strong)', display: 'inline-block' }} />
          Overall real rate: <strong style={{ color: 'var(--text-strong)' }}>{(overallRate * 100).toFixed(1)}%</strong>
        </span>
        {plantRate != null && (
          <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '2px', height: '10px', background: 'var(--accent-cyan)', display: 'inline-block' }} />
            {plantLabel}'s real rate: <strong style={{ color: 'var(--text-strong)' }}>{(plantRate * 100).toFixed(1)}%</strong>
          </span>
        )}
      </div>
    </div>
  );
}

/**
 * Real per-prediction SHAP-style attributions from the model's own
 * pred_contrib output (LightGBM), not a post-hoc "this looks unusual"
 * guess -- an additive, exact decomposition of this specific
 * prediction's log-odds.
 */
function ContributionsList({ contributions }) {
  if (!contributions?.length) return null;
  const maxAbs = Math.max(...contributions.map((c) => Math.abs(c.contribution)), 0.0001);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {contributions.map((c) => {
        const increases = c.contribution > 0;
        const halfWidthPct = (Math.abs(c.contribution) / maxAbs) * 50;
        return (
          <div key={c.feature} style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ width: '150px', flexShrink: 0, fontSize: '0.78rem', color: 'var(--text-body)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {c.label}
            </span>
            <span style={{ flex: 1, position: 'relative', height: '14px' }}>
              <span style={{ position: 'absolute', left: '50%', top: 0, bottom: 0, width: '1px', background: 'var(--border-strong)' }} />
              <span style={{
                position: 'absolute', top: '2px', bottom: '2px', borderRadius: '2px',
                background: increases ? 'var(--accent-rose)' : 'var(--accent-emerald)', opacity: 0.8,
                left: increases ? '50%' : `${50 - halfWidthPct}%`,
                width: `${halfWidthPct}%`,
              }} />
            </span>
            <span style={{ width: '90px', flexShrink: 0, fontSize: '0.72rem', textAlign: 'right', color: 'var(--text-subtle)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {c.value}
            </span>
            {increases
              ? <TrendingUp size={13} color="var(--accent-rose)" style={{ flexShrink: 0 }} />
              : <TrendingDown size={13} color="var(--accent-emerald)" style={{ flexShrink: 0 }} />}
          </div>
        );
      })}
    </div>
  );
}

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
  // Real dataset medians, not arbitrary round numbers -- these are the
  // three required numeric fields, so unlike the optional profile
  // fields below they need a real starting value, not a blank.
  tpt: overview.typical.tpt ?? 1,
  unit_quantity: overview.typical.unit_quantity ?? 500,
  weight: overview.typical.weight ?? 10,
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
  const [profileOpen, setProfileOpen] = useState(false);
  const formRef = useRef(null);

  const filledProfileCount = form
    ? OPTIONAL_PROFILE_FIELDS.filter((f) => form[f] !== '' && form[f] != null).length
    : 0;

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
    setProfileOpen(true);
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
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              <FormSection icon={<Ship size={16} />} title="Shipment route">
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
              </FormSection>

              <FormSection icon={<Package size={16} />} title="Order details">
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
                  <label className="form-label">Weight (kg)</label>
                  <input className="form-input" type="number" min="0" step="any" value={form.weight} onChange={(e) => update('weight', e.target.value)} />
                </div>
                <div className="form-group" style={{ justifyContent: 'center' }}>
                  <label style={{
                    display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '0.85rem',
                    color: 'var(--text-body)', background: 'var(--surface-subtle)', border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-sm)', padding: '8px 11px',
                  }}>
                    <input
                      type="checkbox"
                      checked={form.is_vmi_customer_anywhere}
                      onChange={(e) => update('is_vmi_customer_anywhere', e.target.checked)}
                    />
                    VMI Customer
                  </label>
                </div>
              </FormSection>

              <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', overflow: 'hidden' }}>
                <button
                  type="button"
                  onClick={() => setProfileOpen((o) => !o)}
                  style={{
                    width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    background: 'var(--surface-subtle)', border: 'none', padding: '12px 16px', cursor: 'pointer',
                  }}
                >
                  <span style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-strong)', fontSize: '0.92rem', fontWeight: 600 }}>
                    <Warehouse size={16} color="var(--accent-teal, var(--accent-cyan))" />
                    Plant &amp; freight profile
                    <span style={{
                      fontSize: '0.7rem', fontWeight: 600, padding: '2px 8px', borderRadius: '999px',
                      background: filledProfileCount > 0 ? 'var(--accent-emerald)' : 'var(--surface)',
                      color: filledProfileCount > 0 ? '#ffffff' : 'var(--text-subtle)',
                      border: filledProfileCount > 0 ? 'none' : '1px solid var(--border)',
                    }}>
                      {filledProfileCount > 0 ? (
                        <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                          <CheckCircle2 size={11} /> {filledProfileCount} of 6 set
                        </span>
                      ) : 'optional'}
                    </span>
                  </span>
                  <ChevronDown size={16} color="var(--text-subtle)" style={{ transform: profileOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s' }} />
                </button>

                {profileOpen && (
                  <div style={{ padding: '16px' }}>
                    <p className="form-note" style={{ marginTop: 0, marginBottom: '14px' }}>
                      Real per-plant freight &amp; warehouse figures -- the model was trained with these, but the
                      original form never collected them. Click a plant in the overview above to fill them from its
                      real historical profile, or enter your own. Unfilled fields are placeholders showing the
                      dataset-wide median, not blanks the model treats as zero.
                    </p>
                    <div className="predict-form">
                      <div className="form-group">
                        <label className="form-label">Freight Rate ($/unit)</label>
                        <input className="form-input" type="number" step="any" placeholder={`e.g. ${overview.typical.freight_rate}`} value={form.freight_rate} onChange={(e) => update('freight_rate', e.target.value)} />
                      </div>
                      <div className="form-group">
                        <label className="form-label">Freight Min Cost ($)</label>
                        <input className="form-input" type="number" step="any" placeholder={`e.g. ${overview.typical.freight_min_cost}`} value={form.freight_min_cost} onChange={(e) => update('freight_min_cost', e.target.value)} />
                      </div>
                      <div className="form-group">
                        <label className="form-label">Warehouse Cost / Unit ($)</label>
                        <input className="form-input" type="number" step="any" placeholder={`e.g. ${overview.typical.wh_cost_per_unit}`} value={form.wh_cost_per_unit} onChange={(e) => update('wh_cost_per_unit', e.target.value)} />
                      </div>
                      <div className="form-group">
                        <label className="form-label">Warehouse Daily Capacity (units)</label>
                        <input className="form-input" type="number" step="any" placeholder={`e.g. ${overview.typical.wh_daily_capacity}`} value={form.wh_daily_capacity} onChange={(e) => update('wh_daily_capacity', e.target.value)} />
                      </div>
                      <div className="form-group">
                        <label className="form-label">Plant Week Order Count</label>
                        <input className="form-input" type="number" step="any" placeholder={`e.g. ${overview.typical.plant_week_order_count}`} value={form.plant_week_order_count} onChange={(e) => update('plant_week_order_count', e.target.value)} />
                      </div>
                      <div className="form-group">
                        <label className="form-label">Backlog vs Capacity</label>
                        <input className="form-input" type="number" step="any" placeholder={`e.g. ${overview.typical.backlog_vs_capacity}`} value={form.backlog_vs_capacity} onChange={(e) => update('backlog_vs_capacity', e.target.value)} />
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div className="form-actions" style={{ marginTop: 0 }}>
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

            {overview && (
              <div style={{ marginTop: '20px' }}>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-subtle)', marginBottom: '8px' }}>
                  How this compares to real history
                </div>
                <RateComparisonMeter
                  predictedRate={result.late_probability}
                  overallRate={overview.overall_late_rate}
                  plantRate={overview.breakdown.plant_code.find((p) => p.value === form.plant_code)?.late_rate ?? null}
                  plantLabel={form.plant_code}
                />
              </div>
            )}

            {result.feature_contributions?.length > 0 && (
              <div style={{ marginTop: '20px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', color: 'var(--text-subtle)', marginBottom: '10px' }}>
                  What drove this prediction
                  <span title="LightGBM's own per-prediction contribution breakdown (pred_contrib) -- exact, not an approximation.">
                    <Info size={12} />
                  </span>
                </div>
                <ContributionsList contributions={result.feature_contributions} />
              </div>
            )}

            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '18px' }}>
              Trained on a small, imbalanced historical sample (~2% of orders were late) — treat as directional, not precise.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
