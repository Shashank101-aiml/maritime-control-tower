import React, { useEffect, useState } from 'react';
import { ShieldAlert, ShieldCheck, AlertTriangle, Activity, RefreshCw, Waves } from 'lucide-react';
import { useRisks } from '../hooks/useRisks';
import RiskCard from '../components/RiskCard';
import RiskTrendChart from '../components/Charts/RiskTrendChart';
import LoadingSpinner from '../components/LoadingSpinner';
import { apiFetch } from '../services/apiClient';

import { API_BASE_URL as BASE_URL } from '../config';

const TONES = {
  CRITICAL: { fg: 'var(--danger)', bg: 'var(--danger-soft)', border: 'var(--danger-border)' },
  HIGH: { fg: 'var(--danger)', bg: 'var(--danger-soft)', border: 'var(--danger-border)' },
  WARNING: { fg: 'var(--warning)', bg: 'var(--warning-soft)', border: 'var(--warning-border)' },
  LOW: { fg: 'var(--info)', bg: 'var(--info-soft)', border: 'var(--info-border)' },
  INFO: { fg: 'var(--success)', bg: 'var(--success-soft)', border: 'var(--success-border)' },
};

export default function RiskAnalysis() {
  const {
    currentRisk, trends, fleetSummary, isHighRisk,
    loading, error, mitigationActive, activateMitigation, refreshRisk
  } = useRisks();

  const [conditions, setConditions] = useState([]);
  const [conditionsError, setConditionsError] = useState(null);
  const [conditionsLoading, setConditionsLoading] = useState(true);

  const loadConditions = async () => {
    setConditionsLoading(true);
    setConditionsError(null);
    try {
      const res = await apiFetch(`${BASE_URL}/conditions`);
      if (!res.ok) throw new Error(`Request failed (${res.status})`);
      const data = await res.json();
      if (data.source !== 'live') throw new Error(data.error || 'Live feed unavailable.');
      setConditions(data.conditions || []);
    } catch (err) {
      setConditionsError(err.message);
      setConditions([]);
    } finally {
      setConditionsLoading(false);
    }
  };

  useEffect(() => {
    loadConditions();
    const interval = setInterval(loadConditions, 60000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="page-wrapper">
      <div className="section-header" style={{ marginBottom: '24px' }}>
        <div>
          <h1 className="page-title">
            <ShieldAlert size={24} color="var(--danger)" />
            Navigational Hazard &amp; Risk Analysis
          </h1>
          <p className="page-subtitle">
            Model-scored risk over live sea state across monitored maritime corridors.
          </p>
        </div>

        <button className="btn-action" onClick={() => { refreshRisk(); loadConditions(); }}>
          <RefreshCw size={15} className={loading ? 'spin' : ''} />
          Recalculate
        </button>
      </div>

      {loading && !currentRisk ? (
        <LoadingSpinner message="Scoring current conditions…" />
      ) : error ? (
        <div className="panel" style={{ textAlign: 'center', padding: '40px', borderColor: 'var(--danger-border)' }}>
          <AlertTriangle size={30} color="var(--danger)" style={{ margin: '0 auto 12px' }} />
          <p style={{ color: 'var(--text-body)' }}>{error}</p>
        </div>
      ) : (
        <>
          <div className="content-grid" style={{ gridTemplateColumns: '1.3fr 1fr', marginBottom: '24px' }}>
            <RiskCard
              risk={currentRisk}
              onMitigate={activateMitigation}
              mitigationActive={mitigationActive}
            />

            <div className="panel" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
              <div>
                <div className="section-header">
                  <h3 className="section-title">
                    <Activity size={17} color="var(--warning)" />
                    Fleet Vulnerability Overview
                  </h3>
                </div>
                <p style={{ fontSize: '0.875rem', color: 'var(--text-subtle)', lineHeight: 1.55 }}>
                  The Risk Assessment Agent scores live sea state from the monitored corridors
                  through the trained risk model.
                </p>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', margin: '18px 0' }}>
                <div className="result-metric">
                  <div className="result-metric-label">Corridors monitored</div>
                  <div className="result-metric-value">{conditions.length || '—'}</div>
                </div>

                <div className="result-metric">
                  <div className="result-metric-label">Active alerts</div>
                  <div className="result-metric-value" style={{ color: 'var(--warning)' }}>
                    {fleetSummary.activeAlerts ?? '—'}
                  </div>
                </div>
              </div>

              <div style={{
                display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.82rem',
                color: 'var(--success)', background: 'var(--success-soft)',
                border: '1px solid var(--success-border)',
                padding: '10px 14px', borderRadius: 'var(--radius)'
              }}>
                <ShieldCheck size={15} /> Autonomous governance safety guardrails active.
              </div>
            </div>
          </div>

          <div style={{ marginBottom: '24px' }}>
            <RiskTrendChart trends={trends} />
          </div>

          <div className="panel">
            <div className="section-header">
              <h3 className="section-title">
                <Waves size={17} color="var(--info)" />
                Live corridor conditions
              </h3>
              {conditionsLoading && <RefreshCw size={15} className="spin" color="var(--text-subtle)" />}
            </div>

            {conditionsError ? (
              <div style={{ padding: '28px', textAlign: 'center', color: 'var(--text-subtle)' }}>
                <AlertTriangle size={22} color="var(--warning)" style={{ margin: '0 auto 10px' }} />
                <p>Live conditions feed unavailable — {conditionsError}</p>
              </div>
            ) : conditions.length === 0 && !conditionsLoading ? (
              <p style={{ color: 'var(--text-subtle)' }}>No corridor readings returned.</p>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '14px' }}>
                {conditions.map((c) => {
                  const key = String(c.severity || '').toUpperCase();
                  const tone = TONES[key] || TONES.INFO;
                  const m = c.conditions || {};
                  return (
                    <div key={c.location} style={{
                      background: 'var(--surface-subtle)',
                      border: '1px solid var(--border)',
                      borderLeft: `3px solid ${tone.fg}`,
                      padding: '16px',
                      borderRadius: 'var(--radius)'
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '10px', marginBottom: '6px' }}>
                        <h4 style={{ fontSize: '0.9rem' }}>{c.location}</h4>
                        <span className="status-badge" style={{ fontSize: '0.68rem', background: tone.bg, borderColor: tone.border, color: tone.fg }}>
                          {key}
                        </span>
                      </div>
                      <p style={{ fontSize: '0.82rem', color: 'var(--text-subtle)', marginBottom: '10px' }}>
                        {c.event_type}
                      </p>
                      <div style={{ display: 'flex', gap: '16px', fontSize: '0.78rem', color: 'var(--text-body)' }}>
                        <span>Wave <strong>{m.wave_height_m ?? '—'} m</strong></span>
                        <span>Swell <strong>{m.swell_height_m ?? '—'} m</strong></span>
                        <span>Gust <strong>{m.wind_gusts_kmh ?? '—'} km/h</strong></span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            <p className="form-note">
              Live marine observations from Open-Meteo, refreshed every 60s. Severity bands follow
              Douglas sea-scale / Beaufort thresholds.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
