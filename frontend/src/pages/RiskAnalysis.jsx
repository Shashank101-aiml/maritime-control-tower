import React, { useEffect, useState } from 'react';
import { ShieldAlert, ShieldCheck, AlertTriangle, Activity, RefreshCw, Waves, MapPin, Ship } from 'lucide-react';
import { useRisks } from '../hooks/useRisks';
import RiskCard from '../components/RiskCard';
import RiskTrendChart from '../components/Charts/RiskTrendChart';
import LoadingSpinner from '../components/LoadingSpinner';
import { getRiskCorridors } from '../services/riskService';
import { useCorridorContext } from '../context/CorridorContext';

const TONES = {
  CRITICAL: { fg: 'var(--danger)', bg: 'var(--danger-soft)', border: 'var(--danger-border)' },
  HIGH: { fg: 'var(--danger)', bg: 'var(--danger-soft)', border: 'var(--danger-border)' },
  WARNING: { fg: 'var(--warning)', bg: 'var(--warning-soft)', border: 'var(--warning-border)' },
  LOW: { fg: 'var(--info)', bg: 'var(--info-soft)', border: 'var(--info-border)' },
  INFO: { fg: 'var(--success)', bg: 'var(--success-soft)', border: 'var(--success-border)' },
};

const scoreTone = (score) => {
  if (score >= 60) return TONES.CRITICAL;
  if (score >= 35) return TONES.WARNING;
  return TONES.INFO;
};

export default function RiskAnalysis() {
  const {
    currentRisk, trends, trendsByCorridor, fleetSummary, isHighRisk,
    loading, error, mitigationActive, activateMitigation, refreshRisk
  } = useRisks();

  // One risk-scored card per monitored corridor -- this is what makes the
  // page a breakdown rather than a single aggregate number with no sense
  // of which corridor it's about or what's actually passing through it.
  const [corridors, setCorridors] = useState([]);
  const [corridorsError, setCorridorsError] = useState(null);
  const [corridorsLoading, setCorridorsLoading] = useState(true);
  const [vesselsConfigured, setVesselsConfigured] = useState(true);

  const loadCorridors = async () => {
    setCorridorsLoading(true);
    setCorridorsError(null);
    try {
      const data = await getRiskCorridors();
      if (data.error) throw new Error(data.error);
      setCorridors(data.corridors || []);
      setVesselsConfigured(data.vessels_configured ?? true);
    } catch (err) {
      setCorridorsError(err.message);
      setCorridors([]);
    } finally {
      setCorridorsLoading(false);
    }
  };

  useEffect(() => {
    loadCorridors();
    const interval = setInterval(loadCorridors, 60000);
    return () => clearInterval(interval);
  }, []);

  // A corridor selected on Vessel Tracking scrolls its card into view
  // and stays highlighted here, instead of the two pages being unaware
  // of each other.
  const { selectedCorridor } = useCorridorContext();
  useEffect(() => {
    if (!selectedCorridor || corridors.length === 0) return;
    const el = document.getElementById(`corridor-card-${selectedCorridor.location}`);
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [selectedCorridor, corridors]);

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

        <button className="btn-action" onClick={() => { refreshRisk(); loadCorridors(); }}>
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
                  The card on the left is the single worst corridor right now — the table below
                  scores every monitored corridor individually, with who's currently in it.
                </p>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', margin: '18px 0' }}>
                <div className="result-metric">
                  <div className="result-metric-label">Corridors monitored</div>
                  <div className="result-metric-value">{corridors.length || '—'}</div>
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
            <RiskTrendChart trends={trends} trendsByCorridor={trendsByCorridor} />
          </div>

          <div className="panel">
            <div className="section-header">
              <h3 className="section-title">
                <Waves size={17} color="var(--info)" />
                Risk by corridor
              </h3>
              {corridorsLoading && <RefreshCw size={15} className="spin" color="var(--text-subtle)" />}
            </div>

            {corridorsError ? (
              <div style={{ padding: '28px', textAlign: 'center', color: 'var(--text-subtle)' }}>
                <AlertTriangle size={22} color="var(--warning)" style={{ margin: '0 auto 10px' }} />
                <p>Live conditions feed unavailable — {corridorsError}</p>
              </div>
            ) : corridors.length === 0 && !corridorsLoading ? (
              <p style={{ color: 'var(--text-subtle)' }}>No corridor readings returned.</p>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '14px' }}>
                {corridors.map((c) => {
                  const tone = scoreTone(c.score);
                  const m = c.conditions || {};
                  const isSelected = selectedCorridor?.location === c.location;
                  return (
                    <div key={c.location} id={`corridor-card-${c.location}`} style={{
                      background: isSelected ? 'var(--primary-soft)' : 'var(--surface-subtle)',
                      border: isSelected ? '1px solid var(--accent-cyan)' : '1px solid var(--border)',
                      borderLeft: `3px solid ${tone.fg}`,
                      boxShadow: isSelected ? '0 0 0 1px var(--accent-cyan)' : 'none',
                      padding: '16px',
                      borderRadius: 'var(--radius)',
                      transition: 'background 0.3s ease, box-shadow 0.3s ease'
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '10px', marginBottom: '4px' }}>
                        <h4 style={{ fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '5px' }}>
                          <MapPin size={13} color="var(--text-subtle)" />
                          {c.location}
                        </h4>
                        <span className="status-badge" style={{ fontSize: '0.68rem', background: tone.bg, borderColor: tone.border, color: tone.fg }}>
                          {c.score}/100
                        </span>
                      </div>
                      <p style={{ fontSize: '0.82rem', color: 'var(--text-subtle)', marginBottom: '10px' }}>
                        {c.category}
                      </p>
                      <div style={{ display: 'flex', gap: '16px', fontSize: '0.78rem', color: 'var(--text-body)', marginBottom: '10px' }}>
                        <span>Wave <strong>{m.wave_height_m ?? '—'} m</strong></span>
                        <span>Swell <strong>{m.swell_height_m ?? '—'} m</strong></span>
                        <span>Gust <strong>{m.wind_gusts_kmh ?? '—'} km/h</strong></span>
                      </div>
                      <div style={{
                        display: 'flex', alignItems: 'center', gap: '5px',
                        fontSize: '0.76rem', color: 'var(--text-subtle)',
                        paddingTop: '8px', borderTop: '1px solid var(--border)'
                      }}>
                        <Ship size={12} />
                        {!vesselsConfigured
                          ? 'Vessel tracking not configured'
                          : `${c.vessel_count} vessel${c.vessel_count === 1 ? '' : 's'} here`}
                        {c.vessels?.length > 0 && (
                          <span style={{ color: 'var(--text-body)' }}>
                            — {c.vessels.slice(0, 2).map((v) => v.name || `MMSI ${v.mmsi}`).join(', ')}
                            {c.vessel_count > 2 ? `, +${c.vessel_count - 2} more` : ''}
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            <p className="form-note">
              Live marine observations from Open-Meteo, refreshed every 60s. Severity bands follow
              Douglas sea-scale / Beaufort thresholds. Vessel positions from AISStream — a vessel is
              counted against a corridor when its last reported position falls inside that
              corridor's monitored area.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
