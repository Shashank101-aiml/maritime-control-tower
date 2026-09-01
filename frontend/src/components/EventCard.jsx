import React from 'react';
import { AlertTriangle, MapPin, Clock, Ship, ShieldAlert, Wind, Compass, Waves } from 'lucide-react';
import { getSeverityTone, getSeverityLabel } from '../types/Event';

/** "2026-09-01T10:45" -> "01 Sep 10:45 UTC"; passes through relative
 *  strings like "10 minutes ago" unchanged. */
const formatTimestamp = (value) => {
  if (!value) return null;
  const parsed = new Date(value.endsWith('Z') ? value : `${value}Z`);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString('en-GB', {
    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
    timeZone: 'UTC', hour12: false,
  }) + ' UTC';
};

export default function EventCard({ event, onClick }) {
  if (!event) return null;

  const tone = getSeverityTone(event.severity);
  const isSevere = ['CRITICAL', 'HIGH'].includes(event.severity);
  const m = event.conditions || {};

  const icon = (type) => {
    const t = (type || '').toLowerCase();
    if (t.includes('swell') || t.includes('sea') || t.includes('wave')) return <Waves size={19} color={tone.fg} />;
    if (t.includes('storm') || t.includes('wind') || t.includes('weather')) return <Wind size={19} color={tone.fg} />;
    if (t.includes('piracy') || t.includes('security')) return <ShieldAlert size={19} color={tone.fg} />;
    if (t.includes('port') || t.includes('congestion') || t.includes('anchor')) return <Compass size={19} color={tone.fg} />;
    return <AlertTriangle size={19} color={tone.fg} />;
  };

  return (
    <div
      className="agent-item"
      onClick={onClick}
      style={{
        cursor: onClick ? 'pointer' : 'default',
        borderLeft: `3px solid ${tone.fg}`,
        background: isSevere ? tone.bg : 'var(--surface-subtle)',
        padding: '14px 18px',
        alignItems: 'flex-start',
      }}
    >
      <div className="agent-info" style={{ alignItems: 'flex-start' }}>
        <div className="agent-avatar" style={{ background: tone.bg, width: '40px', height: '40px', flexShrink: 0 }}>
          {icon(event.event_type)}
        </div>

        <div style={{ minWidth: 0 }}>
          <div className="agent-name" style={{ fontSize: '0.95rem' }}>
            {event.event_type}
          </div>

          <div className="agent-role" style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', alignItems: 'center', marginTop: '5px' }}>
            {event.location && (
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <MapPin size={12} /> {event.location}
              </span>
            )}

            {/* Coordinates are only shown when the reading actually has
                them — the old fallback rendered 0.0°, 0.0° as if real. */}
            {event.coordinates && (
              <span style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: '0.72rem' }}>
                {event.coordinates.lat.toFixed(2)}°, {event.coordinates.lng.toFixed(2)}°
              </span>
            )}

            {/* Corridor readings have no vessel; this renders only if one
                is genuinely attached. */}
            {event.vessel_id && (
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Ship size={12} /> {event.vessel_id}
              </span>
            )}
          </div>

          {/* The measurements behind the classification, which the card
              previously discarded in favour of a fabricated vessel ID. */}
          {(m.wave_height_m != null || m.wind_gusts_kmh != null) && (
            <div className="agent-role" style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', marginTop: '6px' }}>
              {m.wave_height_m != null && <span>Wave <strong>{m.wave_height_m} m</strong></span>}
              {m.swell_height_m != null && <span>Swell <strong>{m.swell_height_m} m</strong></span>}
              {m.wind_gusts_kmh != null && <span>Gust <strong>{m.wind_gusts_kmh} km/h</strong></span>}
              {m.wave_period_s != null && <span>Period <strong>{m.wave_period_s} s</strong></span>}
            </div>
          )}
        </div>
      </div>

      <div style={{ textAlign: 'right', flexShrink: 0 }}>
        <span
          className="status-badge"
          style={{ background: tone.bg, borderColor: tone.border, color: tone.fg, fontSize: '0.68rem' }}
        >
          {getSeverityLabel(event.severity)}
        </span>
        {event.timestamp && (
          <div style={{ fontSize: '0.72rem', color: 'var(--text-subtle)', marginTop: '6px', display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'flex-end' }}>
            <Clock size={11} /> {formatTimestamp(event.timestamp)}
          </div>
        )}
      </div>
    </div>
  );
}
