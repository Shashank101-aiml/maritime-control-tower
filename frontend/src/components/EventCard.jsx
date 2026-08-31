import React from 'react';
import { AlertTriangle, MapPin, Clock, Ship, ShieldAlert, Wind, Compass } from 'lucide-react';
import { getSeverityColor } from '../types/Event';

export default function EventCard({ event, onClick }) {
  if (!event) return null;

  const severityColor = getSeverityColor(event.severity);
  const isHigh = event.severity === 'HIGH' || event.severity === 'CRITICAL';

  const getEventIcon = (type) => {
    const t = (type || '').toLowerCase();
    if (t.includes('storm') || t.includes('weather') || t.includes('swell')) return <Wind size={20} color={severityColor} />;
    if (t.includes('piracy') || t.includes('security') || t.includes('spoofing')) return <ShieldAlert size={20} color={severityColor} />;
    if (t.includes('port') || t.includes('delay') || t.includes('anchor')) return <Compass size={20} color={severityColor} />;
    return <AlertTriangle size={20} color={severityColor} />;
  };

  return (
    <div 
      className="agent-item" 
      onClick={onClick}
      style={{ 
        cursor: onClick ? 'pointer' : 'default',
        borderLeft: `4px solid ${severityColor}`,
        background: isHigh ? 'var(--danger-soft)' : 'var(--surface-subtle)',
        transition: 'all 0.2s ease',
        padding: '16px 20px'
      }}
    >
      <div className="agent-info">
        <div 
          className="agent-avatar" 
          style={{ 
            background: isHigh ? 'var(--danger-soft)' : 'var(--primary-soft)',
            width: '44px',
            height: '44px'
          }}
        >
          {getEventIcon(event.event_type)}
        </div>
        <div>
          <div className="agent-name" style={{ fontSize: '1.05rem', color: 'var(--text-strong)' }}>
            {event.event_type}
          </div>
          <div className="agent-role" style={{ display: 'flex', flexWrap: 'wrap', gap: '14px', alignItems: 'center', marginTop: '6px' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--text-main)' }}>
              <MapPin size={13} color="var(--accent-cyan)" /> {event.location}
            </span>
            {event.vessel_id && (
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--text-muted)' }}>
                <Ship size={13} /> {event.vessel_id}
              </span>
            )}
            {event.coordinates && (
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                [{event.coordinates.lat?.toFixed(1)}°, {event.coordinates.lng?.toFixed(1)}°]
              </span>
            )}
          </div>
        </div>
      </div>

      <div style={{ textAlign: 'right' }}>
        <span 
          className="status-badge" 
          style={{ 
            background: isHigh ? 'var(--danger-soft)' : 'var(--primary-soft)',
            borderColor: severityColor,
            color: severityColor,
            fontWeight: 700
          }}
        >
          {event.severity} HAZARD
        </span>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '4px', fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '8px' }}>
          <Clock size={12} /> {event.timestamp}
        </div>
      </div>
    </div>
  );
}
