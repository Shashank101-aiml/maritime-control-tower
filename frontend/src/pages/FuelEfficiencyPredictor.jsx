import React, { useState } from 'react';
import { Fuel, DollarSign, Gauge, AlertTriangle, Send } from 'lucide-react';
import { predictFuel } from '../services/fuelService';
import LoadingSpinner from '../components/LoadingSpinner';

const SHIP_TYPES = ['Oil Service Boat', 'Fishing Trawler', 'Surfer Boat', 'Tanker Ship'];
const ROUTES = ['Warri-Bonny', 'Port Harcourt-Lagos', 'Bonny-Lagos', 'Lagos-Warri'];
const FUEL_TYPES = ['HFO', 'Diesel'];
const WEATHER = ['Calm', 'Moderate', 'Stormy'];
const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

const DEFAULT_FORM = {
  ship_type: SHIP_TYPES[3],
  route_id: ROUTES[0],
  fuel_type: FUEL_TYPES[0],
  weather_conditions: WEATHER[1],
  distance: 150,
  month_num: 6,
};

export default function FuelEfficiencyPredictor() {
  const [form, setForm] = useState(DEFAULT_FORM);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const update = (field, value) => setForm((f) => ({ ...f, [field]: value }));

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

  return (
    <div className="page-wrapper">
      <div className="section-header" style={{ marginBottom: '24px' }}>
        <div>
          <h1 className="section-title" style={{ fontSize: '1.8rem', color: 'var(--text-strong)' }}>
            <Fuel size={28} color="var(--accent-amber)" />
            Fuel Efficiency & Cost Savings
          </h1>
          <p style={{ color: 'var(--text-muted)', marginTop: '4px' }}>
            Predicts fuel consumption for a planned trip and estimates cost using reference bunker prices.
          </p>
        </div>
      </div>

      <div className="glass-panel">
        <form className="predict-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Ship Type</label>
            <select className="form-select" value={form.ship_type} onChange={(e) => update('ship_type', e.target.value)}>
              {SHIP_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Route</label>
            <select className="form-select" value={form.route_id} onChange={(e) => update('route_id', e.target.value)}>
              {ROUTES.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Fuel Type</label>
            <select className="form-select" value={form.fuel_type} onChange={(e) => update('fuel_type', e.target.value)}>
              {FUEL_TYPES.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Weather Conditions</label>
            <select className="form-select" value={form.weather_conditions} onChange={(e) => update('weather_conditions', e.target.value)}>
              {WEATHER.map((w) => <option key={w} value={w}>{w}</option>)}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Distance (nm)</label>
            <input
              className="form-input" type="number" min="0" step="any"
              value={form.distance} onChange={(e) => update('distance', e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Month</label>
            <select className="form-select" value={form.month_num} onChange={(e) => update('month_num', e.target.value)}>
              {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
            </select>
          </div>

          <div className="form-actions">
            <button className="btn-action" type="submit" disabled={loading}>
              <Send size={16} className={loading ? 'spin' : ''} />
              {loading ? 'Predicting…' : 'Predict Fuel Consumption'}
            </button>
          </div>
        </form>

        {loading && <LoadingSpinner message="Running fuel efficiency model…" />}

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
                <div className="result-metric-label">Predicted Fuel Consumption</div>
                <div className="result-metric-value" style={{ color: 'var(--accent-cyan)' }}>
                  {result.predicted_fuel_consumption.toLocaleString()} L
                </div>
              </div>
              <div className="result-metric">
                <div className="result-metric-label">
                  <DollarSign size={12} style={{ display: 'inline', marginRight: '4px' }} />
                  Estimated Cost (illustrative)
                </div>
                <div className="result-metric-value" style={{ color: 'var(--accent-emerald)' }}>
                  {result.estimated_cost_usd != null ? `$${result.estimated_cost_usd.toLocaleString()}` : 'N/A'}
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
              Cost is illustrative, based on fixed reference bunker prices (HFO ~$0.55/L, Diesel ~$0.80/L), not a live feed.
              Confidence reflects whether the inputs match categories the model was actually trained on.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
