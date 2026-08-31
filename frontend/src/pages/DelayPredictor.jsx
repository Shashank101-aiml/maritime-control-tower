import React, { useState } from 'react';
import { Clock, AlertTriangle, Send, Gauge } from 'lucide-react';
import { predictDelay } from '../services/delayService';
import LoadingSpinner from '../components/LoadingSpinner';

const DEFAULT_FORM = {
  origin_port: 'PORT09',
  destination_port: 'PORT09',
  carrier: 'V44_3',
  service_level: 'CRF',
  customer: 'V555555555555555_29',
  plant_code: 'PLANT03',
  tpt: 1,
  unit_quantity: 500,
  weight: 10,
  is_vmi_customer_anywhere: false,
};

export default function DelayPredictor() {
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
      const response = await predictDelay({
        ...form,
        tpt: Number(form.tpt),
        unit_quantity: Number(form.unit_quantity),
        weight: Number(form.weight),
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

      <div className="glass-panel">
        <form className="predict-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Origin Port</label>
            <input className="form-input" value={form.origin_port} onChange={(e) => update('origin_port', e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">Destination Port</label>
            <input className="form-input" value={form.destination_port} onChange={(e) => update('destination_port', e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">Carrier</label>
            <input className="form-input" value={form.carrier} onChange={(e) => update('carrier', e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">Service Level</label>
            <select className="form-select" value={form.service_level} onChange={(e) => update('service_level', e.target.value)}>
              <option value="CRF">CRF</option>
              <option value="DTP">DTP</option>
              <option value="DTD">DTD</option>
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Customer</label>
            <input className="form-input" value={form.customer} onChange={(e) => update('customer', e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">Plant Code</label>
            <input className="form-input" value={form.plant_code} onChange={(e) => update('plant_code', e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">Transit Time (days)</label>
            <input className="form-input" type="number" min="0" value={form.tpt} onChange={(e) => update('tpt', e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">Unit Quantity</label>
            <input className="form-input" type="number" min="0" value={form.unit_quantity} onChange={(e) => update('unit_quantity', e.target.value)} />
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

          <div className="form-actions">
            <button className="btn-action" type="submit" disabled={loading}>
              <Send size={16} className={loading ? 'spin' : ''} />
              {loading ? 'Predicting…' : 'Predict Delay Risk'}
            </button>
          </div>
        </form>

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
