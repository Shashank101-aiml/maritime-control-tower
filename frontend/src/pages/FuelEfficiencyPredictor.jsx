import React, { useEffect, useMemo, useState } from 'react';
import { Fuel, DollarSign, Gauge, AlertTriangle, Send, Leaf, Clock } from 'lucide-react';
import { predictFuel, getFuelOptions, getFuelPrices } from '../services/fuelService';
import LoadingSpinner from '../components/LoadingSpinner';

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

const usd = (v) => `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

/** <option>s grouped by their `group`, keeping first-seen order. */
function GroupedOptions({ items }) {
  const groups = useMemo(() => {
    const map = new Map();
    items.forEach((i) => map.set(i.group, [...(map.get(i.group) || []), i]));
    return [...map.entries()];
  }, [items]);
  return groups.map(([group, list]) => (
    <optgroup key={group} label={group}>
      {list.map((i) => <option key={i.value} value={i.value}>{i.label || i.value}</option>)}
    </optgroup>
  ));
}

export default function FuelEfficiencyPredictor() {
  const [options, setOptions] = useState(null);
  const [form, setForm] = useState(null);
  const [prices, setPrices] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    getFuelOptions()
      .then((o) => {
        setOptions(o);
        const route = o.routes[0];
        setForm({
          ship_type: 'Container Ship (Post-Panamax, ~9,000 TEU)',
          route_id: route.value,
          fuel_type: 'VLSFO',
          weather_conditions: 'Moderate',
          distance: route.distance_nm ?? 150,
          month_num: new Date().getMonth() + 1,
          price_hub: route.hub,
        });
      })
      .catch((err) => setError(err.message));
  }, []);

  const hub = form?.price_hub;
  useEffect(() => {
    if (!hub) return;
    setPrices(null);
    getFuelPrices(hub).then(setPrices).catch(() => setPrices({ prices: {}, configured: false, failed: true }));
  }, [hub]);

  const update = (field, value) => setForm((f) => ({ ...f, [field]: value }));

  const chooseRoute = (value) => {
    const route = options.routes.find((r) => r.value === value);
    setForm((f) => ({ ...f, route_id: value, distance: route.distance_nm ?? f.distance, price_hub: route.hub }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await predictFuel({
        ...form,
        distance: Number(form.distance),
        month_num: Number(form.month_num),
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

  const fuelPrice = prices?.prices?.[form?.fuel_type];

  return (
    <div className="page-wrapper">
      <div className="section-header" style={{ marginBottom: '24px' }}>
        <div>
          <h1 className="section-title" style={{ fontSize: '1.8rem', color: 'var(--text-strong)' }}>
            <Fuel size={28} color="var(--accent-amber)" />
            Fuel Efficiency & Cost Savings
          </h1>
          <p style={{ color: 'var(--text-muted)', marginTop: '4px' }}>
            Estimates fuel burn, CO₂ and cost for a planned voyage, priced at today&apos;s live bunker prices.
          </p>
        </div>
      </div>

      {!options || !form ? (
        error ? <div className="prediction-result" style={{ color: 'var(--accent-rose)' }}>{error}</div> : <LoadingSpinner message="Loading options…" />
      ) : (
        <div className="glass-panel">
          <form className="predict-form" onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label" htmlFor="ship">Ship Type</label>
              <select id="ship" className="form-select" value={form.ship_type} onChange={(e) => update('ship_type', e.target.value)}>
                <GroupedOptions items={options.ship_types} />
              </select>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="route">Route</label>
              <select id="route" className="form-select" value={form.route_id} onChange={(e) => chooseRoute(e.target.value)}>
                <GroupedOptions items={options.routes} />
              </select>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="fuel">Fuel Type</label>
              <select id="fuel" className="form-select" value={form.fuel_type} onChange={(e) => update('fuel_type', e.target.value)}>
                {options.fuel_types.map((f) => (
                  <option key={f.value} value={f.value}>{f.label}{f.priced ? '' : ' (no live price)'}</option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="weather">Weather Conditions</label>
              <select id="weather" className="form-select" value={form.weather_conditions} onChange={(e) => update('weather_conditions', e.target.value)}>
                {options.weather.map((w) => <option key={w} value={w}>{w}</option>)}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="distance">Distance (nm)</label>
              <input
                id="distance" className="form-input" type="number" min="1" step="any"
                value={form.distance} onChange={(e) => update('distance', e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="hub">Bunker price hub</label>
              <select id="hub" className="form-select" value={form.price_hub} onChange={(e) => update('price_hub', e.target.value)}>
                {options.hubs.map((h) => <option key={h.value} value={h.value}>{h.label}</option>)}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="month">Month</label>
              <select id="month" className="form-select" value={form.month_num} onChange={(e) => update('month_num', e.target.value)}>
                {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
              </select>
            </div>

            <div className="form-actions">
              <button className="btn-action" type="submit" disabled={loading}>
                <Send size={16} className={loading ? 'spin' : ''} />
                {loading ? 'Estimating…' : 'Estimate Fuel & Cost'}
              </button>
            </div>
          </form>

          {fuelPrice && (
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '12px' }}>
              {fuelPrice.usd_per_tonne != null
                ? <>Live price: <strong style={{ color: 'var(--text-body)' }}>{usd(fuelPrice.usd_per_tonne)}/t</strong> ({fuelPrice.hub} · updated {new Date(fuelPrice.as_of).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}). {fuelPrice.note}</>
                : fuelPrice.note}
            </p>
          )}

          {loading && <LoadingSpinner message="Estimating fuel and fetching live prices…" />}

          {error && (
            <div className="prediction-result">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-rose)' }}>
                <AlertTriangle size={18} /> {error}
              </div>
            </div>
          )}

          {result && (
            <div className="prediction-result">
              <h3 className="section-title" style={{ fontSize: '1.1rem' }}>
                Estimate <span style={{ fontSize: '0.75rem', color: 'var(--text-subtle)', marginLeft: '8px' }}>
                  {result.method === 'trained_model' ? 'trained model' : 'reference estimate'}
                </span>
              </h3>
              <div className="result-metric-grid">
                <div className="result-metric">
                  <div className="result-metric-label">Fuel burned</div>
                  <div className="result-metric-value" style={{ color: 'var(--accent-cyan)' }}>
                    {result.fuel_tonnes.toLocaleString()} t
                  </div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-subtle)' }}>
                    {result.fuel_litres != null && `${result.fuel_litres.toLocaleString()} L · `}{result.days_at_sea} days at {result.speed_knots} kn
                  </div>
                </div>
                <div className="result-metric">
                  <div className="result-metric-label">
                    <DollarSign size={12} style={{ display: 'inline', marginRight: '4px' }} />
                    Fuel cost
                  </div>
                  <div className="result-metric-value" style={{ color: 'var(--accent-emerald)' }}>
                    {result.estimated_cost_usd != null ? usd(result.estimated_cost_usd) : 'N/A'}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-subtle)' }}>
                    {result.price.usd_per_tonne != null ? `at ${usd(result.price.usd_per_tonne)}/t, ${result.price.hub}` : 'no price'}
                  </div>
                </div>
                <div className="result-metric">
                  <div className="result-metric-label">
                    <Leaf size={12} style={{ display: 'inline', marginRight: '4px' }} />
                    CO₂ emitted
                  </div>
                  <div className="result-metric-value">{result.co2_tonnes.toLocaleString()} t</div>
                </div>
                <div className="result-metric">
                  <div className="result-metric-label">
                    <Gauge size={12} style={{ display: 'inline', marginRight: '4px' }} />
                    Confidence
                  </div>
                  <div className="result-metric-value" style={{ color: 'var(--accent-amber)' }}>
                    {(result.confidence * 100).toFixed(0)}%
                  </div>
                </div>
              </div>
              {result.price.note && (
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '14px' }}>
                  <Clock size={12} style={{ verticalAlign: '-1px', marginRight: '4px' }} />{result.price.note}
                </p>
              )}
              <ul style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: '10px 0 0', paddingLeft: '18px', lineHeight: 1.6 }}>
                {result.assumptions.map((a) => <li key={a}>{a}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
