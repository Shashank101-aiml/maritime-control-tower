import React, { useEffect, useState } from 'react';
import {
  ShieldAlert, ShieldCheck, AlertTriangle, Activity, RefreshCw, Waves, MapPin, Ship,
  X, TrendingUp, TrendingDown, Minus, Navigation, Anchor,
} from 'lucide-react';
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

/** Tiny inline trend line for the selected corridor's own score history --
 *  scaled to its own min/max (not the big chart's shared scale), since
 *  this is a detail view of one series, not a comparison across eight. */
const Sparkline = ({ points, color }) => {
  if (!points || points.length < 2) return null;
  const width = 160;
  const height = 40;
  const scores = points.map((p) => p.score);
  const min = Math.min(...scores);
  const max = Math.max(...scores);
  const span = max - min || 1;
  const xFor = (i) => (i / (points.length - 1)) * width;
  const yFor = (s) => height - ((s - min) / span) * (height - 6) - 3;
  const line = points.map((p, i) => `${xFor(i)},${yFor(p.score)}`).join(' ');
  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', maxWidth: `${width}px`, height: `${height}px` }}>
      <polyline fill="none" stroke={color} strokeWidth="2" points={line} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={xFor(points.length - 1)} cy={yFor(points[points.length - 1].score)} r="3" fill={color} />
    </svg>
  );
};

export default function RiskAnalysis({ setActiveTab }) {
  const {
    currentRisk, trends, trendsByCorridor, weakSignalsByCorridor, fleetSummary, isHighRisk,
    loading, error, decision, decisionStatus, decisionMessage, requestDecision,
    feedbackStatus, feedbackError, submitDecisionFeedback, refreshRisk
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
  const { selectedCorridor, selectCorridor, clearCorridor } = useCorridorContext();
  useEffect(() => {
    if (!selectedCorridor || corridors.length === 0) return;
    const el = document.getElementById(`corridor-card-${selectedCorridor.location}`);
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [selectedCorridor, corridors]);

  const toggleCorridor = (location) => {
    if (selectedCorridor?.location === location) clearCorridor();
    else selectCorridor(location);
  };

  // Full detail for whichever corridor is selected -- the per-corridor
  // score/conditions/vessels breakdown, plus its own real score history
  // (not the fleet-wide trend) so a direction and delta can be shown.
  const activeCorridor = selectedCorridor
    ? corridors.find((c) => c.location === selectedCorridor.location)
    : null;
  const activeHistory = selectedCorridor
    ? [...(trendsByCorridor[selectedCorridor.location] || [])].sort((a, b) => new Date(a.time) - new Date(b.time))
    : [];
  const activeTone = activeCorridor ? scoreTone(activeCorridor.score) : null;
  const activeColor = activeCorridor
    ? (activeCorridor.score >= 60 ? '#fb7185' : activeCorridor.score >= 35 ? '#fbbf24' : '#34d399')
    : null;
  const trendDelta = activeHistory.length >= 2
    ? activeHistory[activeHistory.length - 1].score - activeHistory[0].score
    : null;

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
          {/* Selected Corridor -- Risk Detail. A dedicated breakdown for
              whichever corridor is selected (from Vessel Tracking, Event
              Monitor, or the trend chart / corridor grid below), not just
              a highlighted card. Every field here is real: score,
              likelihood/impact from the same model call that scores the
              headline card, the corridor's own score history (not the
              fleet-wide trend), and who's actually in it. */}
          {selectedCorridor && (
            <div className="glass-panel" style={{
              padding: '24px', marginBottom: '24px',
              borderColor: activeTone ? activeTone.border : 'var(--accent-cyan)',
            }}>
              <div className="section-header" style={{ marginBottom: '16px' }}>
                <h3 className="section-title" style={{ fontSize: '1.15rem' }}>
                  <MapPin size={20} color="var(--accent-cyan)" />
                  Selected Corridor — {selectedCorridor.location}
                </h3>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  {activeCorridor && (
                    <span className="status-badge" style={{ background: activeTone.bg, borderColor: activeTone.border, color: activeTone.fg }}>
                      {activeCorridor.score}/100
                    </span>
                  )}
                  <button className="btn-secondary" onClick={clearCorridor} style={{ padding: '6px 12px', fontSize: '0.8rem' }}>
                    <X size={14} /> Clear
                  </button>
                </div>
              </div>

              {!activeCorridor ? (
                <p style={{ color: 'var(--text-subtle)', fontSize: '0.85rem' }}>
                  No current risk reading for {selectedCorridor.location}.
                </p>
              ) : (
                <>
                  <div className="content-grid" style={{ gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '16px' }}>
                    <div>
                      <p style={{ fontSize: '0.95rem', color: 'var(--text-strong)', fontWeight: 600, marginBottom: '10px' }}>
                        {activeCorridor.category}
                      </p>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '14px' }}>
                        <div className="result-metric">
                          <div className="result-metric-label">Impact severity</div>
                          <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-strong)' }}>{activeCorridor.impact}</div>
                        </div>
                        <div className="result-metric">
                          <div className="result-metric-label">Probability</div>
                          <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-strong)' }}>{activeCorridor.likelihood}</div>
                        </div>
                      </div>

                      <div className="reading-grid">
                        <div className="reading">
                          <div className="reading-label">Significant wave</div>
                          <div className="reading-value">{activeCorridor.conditions?.wave_height_m ?? '—'}<span className="reading-unit"> m</span></div>
                        </div>
                        <div className="reading">
                          <div className="reading-label">Swell</div>
                          <div className="reading-value">{activeCorridor.conditions?.swell_height_m ?? '—'}<span className="reading-unit"> m</span></div>
                        </div>
                        <div className="reading">
                          <div className="reading-label">Wind speed</div>
                          <div className="reading-value">{activeCorridor.conditions?.wind_speed_kmh ?? '—'}<span className="reading-unit"> km/h</span></div>
                        </div>
                        <div className="reading">
                          <div className="reading-label">Gusts</div>
                          <div className="reading-value">{activeCorridor.conditions?.wind_gusts_kmh ?? '—'}<span className="reading-unit"> km/h</span></div>
                        </div>
                      </div>
                    </div>

                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '6px' }}>
                        <span style={{ fontSize: '0.78rem', color: 'var(--text-subtle)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                          Score history ({activeHistory.length} reading{activeHistory.length === 1 ? '' : 's'})
                        </span>
                        {trendDelta != null && (
                          <span style={{
                            display: 'flex', alignItems: 'center', gap: '3px', fontSize: '0.78rem', fontWeight: 600,
                            color: trendDelta > 3 ? 'var(--danger)' : trendDelta < -3 ? 'var(--success)' : 'var(--text-subtle)',
                          }}>
                            {trendDelta > 3 ? <TrendingUp size={13} /> : trendDelta < -3 ? <TrendingDown size={13} /> : <Minus size={13} />}
                            {trendDelta > 0 ? '+' : ''}{trendDelta} over window
                          </span>
                        )}
                      </div>
                      {activeHistory.length >= 2 ? (
                        <Sparkline points={activeHistory} color={activeColor} />
                      ) : (
                        <p style={{ fontSize: '0.8rem', color: 'var(--text-subtle)' }}>
                          Not enough recorded history yet to show a trend for this corridor.
                        </p>
                      )}

                      <div style={{
                        display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.82rem',
                        color: 'var(--text-body)', marginTop: '14px', marginBottom: '6px',
                      }}>
                        <Ship size={13} />
                        {!vesselsConfigured
                          ? 'Vessel tracking not configured'
                          : `${activeCorridor.vessel_count} vessel${activeCorridor.vessel_count === 1 ? '' : 's'} here`}
                      </div>
                      {activeCorridor.vessels?.length > 0 && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '5px', maxHeight: '108px', overflowY: 'auto' }}>
                          {activeCorridor.vessels.map((v) => (
                            <div key={v.mmsi} style={{ fontSize: '0.76rem', color: 'var(--text-subtle)' }}>
                              <strong style={{ color: 'var(--text-body)' }}>{v.name || `MMSI ${v.mmsi}`}</strong>
                              {v.ship_type ? ` · ${v.ship_type}` : ''}
                              {v.destination ? ` · → ${v.destination}` : ''}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Interactive: hand this exact corridor selection off
                      to the pages that can act on it, instead of leaving
                      the reader to re-select it there themselves. */}
                  {setActiveTab && (
                    <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', paddingTop: '14px', borderTop: '1px solid var(--border)' }}>
                      <button className="btn-secondary" onClick={() => setActiveTab('tracking')} style={{ fontSize: '0.8rem' }}>
                        <Anchor size={14} /> View on map
                      </button>
                      <button className="btn-secondary" onClick={() => setActiveTab('routes')} style={{ fontSize: '0.8rem' }}>
                        <Navigation size={14} /> Plan a route around this corridor
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          <div className="content-grid" style={{ gridTemplateColumns: '1.3fr 1fr', marginBottom: '24px' }}>
            <RiskCard
              risk={currentRisk}
              decision={decision}
              decisionStatus={decisionStatus}
              decisionMessage={decisionMessage}
              onRequestDecision={requestDecision}
              feedbackStatus={feedbackStatus}
              feedbackError={feedbackError}
              onSubmitFeedback={submitDecisionFeedback}
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
            <RiskTrendChart
              trends={trends}
              trendsByCorridor={trendsByCorridor}
              selectedLocation={selectedCorridor?.location ?? null}
              onSelectLocation={toggleCorridor}
            />
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
                  // Real least-squares trend (Slice 15) over this
                  // corridor's own recorded score history -- "risk is
                  // increasing/decreasing/stable", not a re-derived guess.
                  const signal = weakSignalsByCorridor?.[c.location];
                  return (
                    <button
                      key={c.location}
                      type="button"
                      id={`corridor-card-${c.location}`}
                      onClick={() => toggleCorridor(c.location)}
                      title={isSelected ? `Clear ${c.location} selection` : `Select ${c.location} — shows full detail above`}
                      style={{
                        textAlign: 'left', cursor: 'pointer', font: 'inherit',
                        background: isSelected ? 'var(--primary-soft)' : 'var(--surface-subtle)',
                        border: isSelected ? '1px solid var(--accent-cyan)' : '1px solid var(--border)',
                        borderLeft: `3px solid ${tone.fg}`,
                        boxShadow: isSelected ? '0 0 0 1px var(--accent-cyan)' : 'none',
                        padding: '16px',
                        borderRadius: 'var(--radius)',
                        transition: 'background 0.3s ease, box-shadow 0.3s ease'
                      }}
                    >
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
                      {signal && signal.direction !== 'insufficient_data' && (
                        <div
                          title={`Least-squares fit over its own recorded history: ${signal.slope_per_hour > 0 ? '+' : ''}${signal.slope_per_hour} pts/hr, r²=${signal.r_squared} (${signal.n_points} readings)`}
                          style={{
                            display: 'flex', alignItems: 'center', gap: '5px', fontSize: '0.74rem', marginBottom: '10px',
                            color: signal.direction === 'increasing' ? 'var(--accent-rose)'
                              : signal.direction === 'decreasing' ? 'var(--accent-emerald)' : 'var(--text-subtle)',
                          }}
                        >
                          {signal.direction === 'increasing' ? <TrendingUp size={13} />
                            : signal.direction === 'decreasing' ? <TrendingDown size={13} /> : <Minus size={13} />}
                          Risk {signal.direction} over recorded history
                        </div>
                      )}
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
                    </button>
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
