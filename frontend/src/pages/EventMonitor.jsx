import React from 'react';
import { Radio, Filter, RefreshCw, AlertTriangle, MapPin, X, Waves, Info } from 'lucide-react';
import { useEvents } from '../hooks/useEvents';
import EventCard from '../components/EventCard';
import EventTimelineChart from '../components/Charts/EventTimelineChart';
import LoadingSpinner from '../components/LoadingSpinner';
import { SEVERITY_LEVELS, getSeverityTone, getSeverityLabel } from '../types/Event';
import FreshnessIndicator from '../components/FreshnessIndicator';
import { useCorridorContext } from '../context/CorridorContext';

/** "2026-09-01T11:00" -> "11:00 UTC"; passes anything unparsable through. */
const formatTime = (value) => {
  if (!value) return null;
  const parsed = new Date(value.endsWith('Z') ? value : `${value}Z`);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC', hour12: false }) + ' UTC';
};

export default function EventMonitor() {
  const {
    eventHistory,
    rawHistory,
    highSeverityCount,
    loading,
    error,
    filterSeverity,
    setFilterSeverity,
    refreshEvents,
    freshness
  } = useEvents();

  // Shared across tabs (see CorridorContext.jsx). This page both reads a
  // selection made elsewhere (to filter the log feed below) and writes
  // one from the Corridor Status panel further down -- so a corridor
  // picked here shows up on Vessel Tracking's map, Risk Analysis's
  // highlighted card, and Route Planning's auto-filled origin/destination,
  // exactly as a selection made on Vessel Tracking shows up here.
  const { selectedCorridor, selectCorridor, clearCorridor } = useCorridorContext();
  const corridorFiltered = selectedCorridor
    ? eventHistory.filter((evt) => evt.location === selectedCorridor.location)
    : eventHistory;

  const toggleCorridor = (location) => {
    if (selectedCorridor?.location === location) clearCorridor();
    else selectCorridor(location);
  };

  return (
    <div className="page-wrapper">
      <div className="section-header" style={{ marginBottom: '24px' }}>
        <div>
          <h1 className="section-title" style={{ fontSize: '1.8rem', color: 'var(--text-strong)' }}>
            <Radio size={28} color="var(--accent-cyan)" />
            Real-Time Telemetry & Hazard Stream
          </h1>
          <p style={{ color: 'var(--text-muted)', marginTop: '4px' }}>
            Live sensor data ingested from active maritime weather buoys, satellite feeds, and vessel telemetry.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <div style={{ display: 'flex', background: 'var(--surface-subtle)', border: '1px solid var(--border-subtle)', borderRadius: '10px', padding: '4px' }}>
            {['ALL', ...SEVERITY_LEVELS].map(sev => (
              <button
                key={sev}
                onClick={() => setFilterSeverity(sev)}
                style={{
                  background: filterSeverity === sev ? 'var(--accent-cyan)' : 'transparent',
                  color: filterSeverity === sev ? '#ffffff' : 'var(--text-muted)',
                  border: 'none',
                  padding: '6px 11px',
                  borderRadius: '6px',
                  fontWeight: 600,
                  fontSize: '0.74rem',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease'
                }}
              >
                {sev}
              </button>
            ))}
          </div>

          <button className="btn-action" onClick={refreshEvents} style={{ padding: '10px 18px' }}>
            <RefreshCw size={16} className={loading ? 'spin' : ''} />
          </button>
        </div>
      </div>

      {/* Timeline Chart */}
      <div style={{ marginBottom: '24px' }}>
        <EventTimelineChart />
      </div>

      <div className="content-grid" style={{ gridTemplateColumns: '1.4fr 1fr', alignItems: 'start' }}>
        <div>
          {selectedCorridor && (
            <div className="workflow-box" style={{
              marginBottom: '20px', display: 'flex', alignItems: 'center',
              justifyContent: 'space-between', background: 'var(--info-soft)', border: '1px solid var(--accent-cyan)',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-strong)', fontSize: '0.9rem' }}>
                <MapPin size={16} color="var(--accent-cyan)" />
                Showing telemetry for <strong>{selectedCorridor.location}</strong>
              </div>
              <button className="btn-secondary" onClick={clearCorridor} style={{ padding: '6px 12px', fontSize: '0.8rem' }}>
                <X size={14} /> Clear
              </button>
            </div>
          )}

          {/* Events Feed Grid */}
          <div className="glass-panel" style={{ padding: '24px' }}>
            <div className="section-header" style={{ marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '14px', flexWrap: 'wrap' }}>
                <h3 className="section-title" style={{ fontSize: '1.15rem' }}>
                  <Filter size={20} color="var(--accent-amber)" />
                  Telemetry Logs ({corridorFiltered.length} Recorded)
                </h3>
                <FreshnessIndicator freshness={freshness} />
              </div>
              {highSeverityCount > 0 && (
                <span className="status-badge" style={{ background: 'var(--danger-soft)', borderColor: 'var(--accent-rose)', color: 'var(--accent-rose)' }}>
                  <AlertTriangle size={14} /> {highSeverityCount} CRITICAL HAZARDS ACTIVE
                </span>
              )}
            </div>

            {loading && eventHistory.length === 0 ? (
              <LoadingSpinner message="Ingesting maritime telemetry stream..." />
            ) : error ? (
              <div style={{ textAlign: 'center', padding: '40px', color: 'var(--accent-rose)' }}>
                <AlertTriangle size={36} style={{ margin: '0 auto 12px' }} />
                <p>{error}</p>
              </div>
            ) : corridorFiltered.length === 0 ? (
              /* Distinguish "the feed returned nothing", "the severity
                 filter excluded everything", and "the corridor filter
                 excluded everything" -- three different real causes, not
                 one message blaming whichever filter happens to be active. */
              <p style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                {rawHistory.length === 0
                  ? 'No telemetry readings available from the live feed.'
                  : eventHistory.length === 0
                    ? `No readings at ${filterSeverity} severity — ${rawHistory.length} reading${rawHistory.length === 1 ? '' : 's'} at other levels.`
                    : `No readings for ${selectedCorridor.location} at ${filterSeverity === 'ALL' ? 'any' : filterSeverity} severity.`}
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {corridorFiltered.map((evt, i) => (
                  <EventCard key={evt.id || i} event={evt} />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Corridor Status -- a standalone monitoring surface for this
            tab, not just a passive readout of a selection made on Vessel
            Tracking. Sourced from rawHistory (already fetched by
            useEvents() for the log feed above -- one live reading per
            monitored corridor, worst-first), so no extra network call.
            Clicking a corridor here both narrows the log feed on this
            page AND updates the shared CorridorContext, so the same pick
            is reflected on Vessel Tracking's map, Risk Analysis's
            highlighted card, and Route Planning's auto-filled route. */}
        <div className="panel">
          <div className="section-header">
            <h3 className="section-title">
              <Waves size={17} color="var(--info)" />
              Corridor Status ({rawHistory.length})
            </h3>
          </div>
          <p className="form-note" style={{ marginTop: 0, marginBottom: '14px' }}>
            Live sea state per monitored corridor. Select one to filter the log feed here and
            focus it across Vessel Tracking, Risk Analysis, and Route Planning.
          </p>

          {loading && rawHistory.length === 0 ? (
            <LoadingSpinner message="Loading corridor readings..." />
          ) : rawHistory.length === 0 ? (
            <p style={{ color: 'var(--text-subtle)' }}>No corridor readings available.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '620px', overflowY: 'auto' }}>
              {rawHistory.map((c) => {
                const tone = getSeverityTone(c.severity);
                const m = c.conditions || {};
                const isSelected = selectedCorridor?.location === c.location;
                return (
                  <button
                    key={c.location}
                    type="button"
                    className={`agent-item corridor-row ${isSelected ? 'focused' : ''}`}
                    onClick={() => toggleCorridor(c.location)}
                    title={isSelected ? `Clear ${c.location} selection` : `Monitor ${c.location} across all tabs`}
                  >
                    <div className="agent-info">
                      <div className="agent-avatar" style={{ background: 'var(--surface-sunken)', color: tone.fg }}>
                        <Waves size={15} />
                      </div>
                      <div style={{ textAlign: 'left' }}>
                        <div className="agent-name">{c.location}</div>
                        <div className="agent-role">
                          {m.wave_height_m ?? '—'} m wave · gust {m.wind_gusts_kmh ?? '—'} km/h
                          {c.timestamp ? ` · ${formatTime(c.timestamp)}` : ''}
                        </div>
                      </div>
                    </div>
                    <span className="status-badge" style={{ background: 'transparent', borderColor: tone.fg, color: tone.fg, fontSize: '0.68rem' }}>
                      {getSeverityLabel(c.severity)}
                    </span>
                  </button>
                );
              })}
            </div>
          )}

          {selectedCorridor && (() => {
            const active = rawHistory.find((c) => c.location === selectedCorridor.location);
            return active?.classification_reason ? (
              <div className="event-reason" style={{
                marginTop: '14px', borderColor: getSeverityTone(active.severity).border,
                background: getSeverityTone(active.severity).bg,
              }}>
                <Info size={14} color={getSeverityTone(active.severity).fg} style={{ flexShrink: 0, marginTop: 2 }} />
                <span>{active.classification_reason}</span>
              </div>
            ) : null;
          })()}
        </div>
      </div>
    </div>
  );
}
