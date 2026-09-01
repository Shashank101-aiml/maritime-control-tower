import React, { useState } from 'react';
import {
  AlertTriangle, MapPin, Clock, Ship, ShieldAlert, Wind, Compass, Waves,
  ChevronDown, Navigation, Info,
} from 'lucide-react';
import { getSeverityTone, getSeverityLabel } from '../types/Event';

/** "2026-09-01T11:00" -> "01 Sept, 11:00 UTC"; passes relative strings
 *  like "10 minutes ago" through unchanged. */
const formatTimestamp = (value) => {
  if (!value) return null;
  const parsed = new Date(value.endsWith('Z') ? value : `${value}Z`);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString('en-GB', {
    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
    timeZone: 'UTC', hour12: false,
  }) + ' UTC';
};

/** 238° -> "238° WSW" */
const bearing = (deg) => {
  if (deg == null) return null;
  const points = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
    'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
  return `${Math.round(deg)}° ${points[Math.round(deg / 22.5) % 16]}`;
};

const Metric = ({ label, value, unit }) =>
  value == null ? null : (
    <div className="reading">
      <div className="reading-label">{label}</div>
      <div className="reading-value">
        {value}{unit ? <span className="reading-unit"> {unit}</span> : null}
      </div>
    </div>
  );

export default function EventCard({ event }) {
  const [open, setOpen] = useState(false);
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
    <div className={`event-card ${open ? 'open' : ''} ${isSevere ? 'severe' : ''}`} style={{ borderLeftColor: tone.fg }}>
      <button
        type="button"
        className="event-card-head"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        title={open ? 'Hide reading detail' : 'Show reading detail'}
      >
        <span className="event-card-icon" style={{ background: tone.bg }}>
          {icon(event.event_type)}
        </span>

        <span className="event-card-main">
          <span className="event-card-title">{event.event_type}</span>
          <span className="event-card-meta">
            {event.location && (
              <span><MapPin size={12} /> {event.location}</span>
            )}
            {event.coordinates && (
              <span className="mono">
                {event.coordinates.lat.toFixed(2)}°, {event.coordinates.lng.toFixed(2)}°
              </span>
            )}
            {event.vessel_id && (
              <span><Ship size={12} /> {event.vessel_id}</span>
            )}
          </span>
        </span>

        <span className="event-card-right">
          <span className="status-badge" style={{ background: tone.bg, borderColor: tone.border, color: tone.fg, fontSize: '0.68rem' }}>
            {getSeverityLabel(event.severity)}
          </span>
          {event.timestamp && (
            <span className="event-card-time">
              <Clock size={11} /> {formatTimestamp(event.timestamp)}
            </span>
          )}
        </span>

        <ChevronDown size={16} className="event-card-chevron" />
      </button>

      {open && (
        <div className="event-card-detail">
          {/* Why this reading was classified the way it was. Generated
              server-side from the same thresholds that made the call. */}
          {event.classification_reason && (
            <div className="event-reason" style={{ borderColor: tone.border, background: tone.bg }}>
              <Info size={14} color={tone.fg} style={{ flexShrink: 0, marginTop: 2 }} />
              <span>{event.classification_reason}</span>
            </div>
          )}

          <div className="reading-grid">
            <Metric label="Significant wave" value={m.wave_height_m} unit="m" />
            <Metric label="Swell" value={m.swell_height_m} unit="m" />
            <Metric label="Wind wave" value={m.wind_wave_height_m} unit="m" />
            <Metric label="Wave period" value={m.wave_period_s} unit="s" />
            <Metric label="Wind speed" value={m.wind_speed_kmh} unit="km/h" />
            <Metric label="Gusts" value={m.wind_gusts_kmh} unit="km/h" />
            {m.wind_direction_deg != null && (
              <div className="reading">
                <div className="reading-label">
                  <Navigation size={10} style={{ display: 'inline', marginRight: 3 }} />
                  Wind direction
                </div>
                <div className="reading-value">{bearing(m.wind_direction_deg)}</div>
              </div>
            )}
          </div>

          {event.description && (
            <p className="event-card-desc">{event.description}</p>
          )}

          <div className="event-card-source">
            {event.coordinates && (
              <span className="mono">
                {event.coordinates.lat.toFixed(4)}, {event.coordinates.lng.toFixed(4)}
              </span>
            )}
            {m.observed_at && <span>Observed {formatTimestamp(m.observed_at)}</span>}
            <span>Source: Open-Meteo marine &amp; forecast</span>
          </div>
        </div>
      )}
    </div>
  );
}
