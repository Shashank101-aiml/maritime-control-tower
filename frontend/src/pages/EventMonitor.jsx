import React from 'react';
import { Radio, Filter, RefreshCw, AlertTriangle, MapPin, X } from 'lucide-react';
import { useEvents } from '../hooks/useEvents';
import EventCard from '../components/EventCard';
import EventTimelineChart from '../components/Charts/EventTimelineChart';
import LoadingSpinner from '../components/LoadingSpinner';
import { SEVERITY_LEVELS } from '../types/Event';
import FreshnessIndicator from '../components/FreshnessIndicator';
import { useCorridorContext } from '../context/CorridorContext';

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

  // A corridor selected on Vessel Tracking (or elsewhere) narrows the
  // feed to that location -- on top of the existing severity filter,
  // not instead of it, so both can apply together.
  const { selectedCorridor, clearCorridor } = useCorridorContext();
  const corridorFiltered = selectedCorridor
    ? eventHistory.filter((evt) => evt.location === selectedCorridor.location)
    : eventHistory;

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

      {selectedCorridor && (
        <div className="workflow-box" style={{
          marginBottom: '20px', display: 'flex', alignItems: 'center',
          justifyContent: 'space-between', background: 'var(--info-soft)', border: '1px solid var(--accent-cyan)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-strong)', fontSize: '0.9rem' }}>
            <MapPin size={16} color="var(--accent-cyan)" />
            Showing telemetry for <strong>{selectedCorridor.location}</strong> — selected on Vessel Tracking
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
  );
}
