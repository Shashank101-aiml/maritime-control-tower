import React, { useEffect, useState } from 'react';
import { FlaskConical, TrendingUp, ShieldCheck, AlertCircle, Gauge } from 'lucide-react';
import { getModelMetrics, getGovernanceImpact } from '../services/evaluationService';
import LoadingSpinner from '../components/LoadingSpinner';

const MODEL_LABELS = {
  congestion: 'Congestion classifier',
  delay: 'Shipment delay classifier',
  fuel: 'Fuel efficiency regressor',
  anomaly: 'Anomaly detector (Isolation Forest)',
};

/** One model's real persisted metrics against its own real baseline --
 *  no-skill positive rate for a classifier, always-predict-the-mean
 *  for the regressor, contamination rate for the unsupervised anomaly
 *  detector. Missing (not yet trained) is shown honestly, not guessed. */
function ModelMetricCard({ name, metrics }) {
  if (!metrics) {
    return (
      <div className="panel">
        <div className="section-header">
          <h3 className="section-title" style={{ fontSize: '1rem' }}>{MODEL_LABELS[name]}</h3>
        </div>
        <p style={{ color: 'var(--text-subtle)', fontSize: '0.85rem' }}>
          Not yet trained -- run pipeline/train_{name}_model.py.
        </p>
      </div>
    );
  }

  const isClassifier = 'roc_auc' in metrics;
  const isRegressor = 'r2' in metrics;

  return (
    <div className="panel">
      <div className="section-header">
        <h3 className="section-title" style={{ fontSize: '1rem' }}>{MODEL_LABELS[name]}</h3>
        <span style={{ fontSize: '0.7rem', color: 'var(--text-subtle)' }}>
          {metrics.n_train ?? metrics.n_samples} train rows
        </span>
      </div>

      {isClassifier && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '10px' }}>
            <div className="result-metric">
              <div className="result-metric-label">ROC-AUC</div>
              <div className="result-metric-value">{metrics.roc_auc}</div>
            </div>
            <div className="result-metric">
              <div className="result-metric-label">PR-AUC</div>
              <div className="result-metric-value" style={{ color: 'var(--accent-emerald)' }}>{metrics.pr_auc}</div>
            </div>
          </div>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-subtle)' }}>
            <TrendingUp size={12} style={{ verticalAlign: '-1px', marginRight: '3px' }} />
            vs. real no-skill baseline (always predict the {(metrics.no_skill_pr_auc * 100).toFixed(1)}% positive rate):
            {' '}<strong style={{ color: 'var(--text-body)' }}>{metrics.no_skill_pr_auc}</strong> PR-AUC
          </p>
        </>
      )}

      {isRegressor && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', marginBottom: '10px' }}>
            <div className="result-metric">
              <div className="result-metric-label">MAE</div>
              <div className="result-metric-value">{metrics.mae}</div>
            </div>
            <div className="result-metric">
              <div className="result-metric-label">RMSE</div>
              <div className="result-metric-value">{metrics.rmse}</div>
            </div>
            <div className="result-metric">
              <div className="result-metric-label">R²</div>
              <div className="result-metric-value" style={{ color: 'var(--accent-emerald)' }}>{metrics.r2}</div>
            </div>
          </div>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-subtle)' }}>
            <TrendingUp size={12} style={{ verticalAlign: '-1px', marginRight: '3px' }} />
            vs. real baseline (always predict the training mean):
            {' '}<strong style={{ color: 'var(--text-body)' }}>{metrics.baseline_mean_mae}</strong> MAE
          </p>
        </>
      )}

      {name === 'anomaly' && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '10px' }}>
            <div className="result-metric">
              <div className="result-metric-label">Flagged (real history)</div>
              <div className="result-metric-value">{metrics.flagged_count} / {metrics.n_samples}</div>
            </div>
            <div className="result-metric">
              <div className="result-metric-label">Contamination</div>
              <div className="result-metric-value">{metrics.contamination}</div>
            </div>
          </div>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-subtle)' }}>
            Unsupervised -- no labeled ground truth exists to score against, so this reports what
            the model actually flagged across {metrics.n_ports} real ports, not an accuracy figure.
          </p>
        </>
      )}

      <p style={{ fontSize: '0.7rem', color: 'var(--text-subtle)', marginTop: '10px' }}>
        Trained {new Date(metrics.trained_at).toLocaleString()}
      </p>
    </div>
  );
}

export default function EvaluationHarness() {
  const [models, setModels] = useState(null);
  const [impact, setImpact] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [m, i] = await Promise.all([getModelMetrics(), getGovernanceImpact()]);
        setModels(m);
        setImpact(i);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="page-wrapper">
      <div className="section-header" style={{ marginBottom: '24px' }}>
        <div>
          <h1 className="section-title" style={{ fontSize: '1.8rem', color: 'var(--text-strong)' }}>
            <FlaskConical size={28} color="var(--accent-teal)" />
            Evaluation Harness
          </h1>
          <p style={{ color: 'var(--text-muted)', marginTop: '4px' }}>
            Real training metrics and governance impact, computed from what each model and agent
            actually did -- not a simulated benchmark.
          </p>
        </div>
      </div>

      {loading ? (
        <LoadingSpinner message="Loading real evaluation data…" />
      ) : error ? (
        <div className="glass-panel" style={{ textAlign: 'center', padding: '40px', borderColor: 'var(--accent-rose)' }}>
          <AlertCircle size={36} color="var(--accent-rose)" style={{ margin: '0 auto 12px' }} />
          <p style={{ color: 'var(--text-main)' }}>{error}</p>
        </div>
      ) : (
        <>
          <div className="glass-panel" style={{ padding: '24px', marginBottom: '24px' }}>
            <div className="section-header" style={{ marginBottom: '14px' }}>
              <h3 className="section-title" style={{ fontSize: '1.15rem' }}>
                <ShieldCheck size={20} color="var(--accent-cyan)" />
                Governance impact
              </h3>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '14px', marginBottom: '14px' }}>
              <div className="result-metric">
                <div className="result-metric-label">Total executions</div>
                <div className="result-metric-value">{impact.total_executions}</div>
              </div>
              <div className="result-metric">
                <div className="result-metric-label">Gated for approval</div>
                <div className="result-metric-value" style={{ color: 'var(--accent-amber)' }}>
                  {impact.gated_for_approval}{impact.gated_rate != null ? ` (${(impact.gated_rate * 100).toFixed(0)}%)` : ''}
                </div>
              </div>
              <div className="result-metric">
                <div className="result-metric-label">Approved</div>
                <div className="result-metric-value" style={{ color: 'var(--accent-emerald)' }}>{impact.approved}</div>
              </div>
              <div className="result-metric">
                <div className="result-metric-label">Rejected at gate</div>
                <div className="result-metric-value" style={{ color: 'var(--accent-rose)' }}>{impact.rejected_at_gate}</div>
              </div>
              <div className="result-metric">
                <div className="result-metric-label">
                  <Gauge size={11} style={{ display: 'inline', marginRight: '3px' }} />
                  Human override rate
                </div>
                <div className="result-metric-value">
                  {impact.override_rate != null ? `${(impact.override_rate * 100).toFixed(0)}%` : '—'}
                </div>
              </div>
            </div>
            <p className="form-note">{impact.note}</p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px' }}>
            {Object.entries(models).map(([name, metrics]) => (
              <ModelMetricCard key={name} name={name} metrics={metrics} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
