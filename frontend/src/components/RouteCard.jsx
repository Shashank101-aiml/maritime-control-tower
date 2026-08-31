import React from 'react';
import { Navigation, Fuel, Clock, MapPin, CheckCircle2, ShieldCheck, AlertTriangle } from 'lucide-react';

export default function RouteCard({ corridor, isSelected, onSelect }) {
  if (!corridor) return null;

  const isSafe = corridor.status === 'OPTIMAL SAFE' || corridor.riskScore < 30;

  return (
    <div 
      className="glass-panel" 
      onClick={() => onSelect && onSelect(corridor.id)}
      style={{ 
        cursor: 'pointer',
        borderColor: isSelected ? 'var(--accent-cyan)' : isSafe ? 'var(--success-border)' : 'var(--border-subtle)',
        background: isSelected ? 'var(--primary-soft)' : 'var(--bg-panel)',
        boxShadow: isSelected ? '0 0 24px var(--primary-border)' : 'none',
        transition: 'all 0.2s ease',
        position: 'relative'
      }}
    >
      {corridor.recommended && (
        <div style={{
          position: 'absolute',
          top: '-1px',
          right: '20px',
          background: 'linear-gradient(90deg, var(--accent-teal), var(--accent-cyan))',
          color: '#ffffff',
          fontSize: '0.75rem',
          fontWeight: 800,
          padding: '4px 12px',
          borderRadius: '0 0 8px 8px',
          boxShadow: '0 4px 12px var(--primary-border)',
          display: 'flex',
          alignItems: 'center',
          gap: '4px'
        }}>
          <CheckCircle2 size={12} /> AI OPTIMAL CORRIDOR
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '14px', paddingRight: corridor.recommended ? '160px' : '0' }}>
        <div>
          <h3 style={{ fontSize: '1.2rem', color: 'var(--text-strong)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Navigation size={20} color={isSelected ? 'var(--accent-cyan)' : 'var(--text-muted)'} />
            {corridor.name}
          </h3>
          <div style={{ display: 'flex', gap: '16px', marginTop: '8px', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <MapPin size={14} /> {corridor.distance}
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Clock size={14} /> {corridor.estTime}
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: corridor.fuelConsumption.includes('save') ? 'var(--accent-emerald)' : 'var(--text-muted)' }}>
              <Fuel size={14} /> {corridor.fuelConsumption}
            </span>
          </div>
        </div>
      </div>

      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between',
        background: 'var(--surface-subtle)', 
        padding: '12px 16px', 
        borderRadius: '10px',
        marginTop: '14px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.9rem', color: 'var(--text-main)', maxWidth: '75%' }}>
          {isSafe ? <ShieldCheck size={18} color="var(--accent-emerald)" /> : <AlertTriangle size={18} color="var(--accent-rose)" />}
          <span>{corridor.reason}</span>
        </div>
        <span className="status-badge" style={{ 
          background: isSafe ? 'var(--success-soft)' : 'var(--danger-soft)',
          borderColor: isSafe ? 'var(--accent-emerald)' : 'var(--accent-rose)',
          color: isSafe ? 'var(--accent-emerald)' : 'var(--accent-rose)'
        }}>
          {corridor.status}
        </span>
      </div>
    </div>
  );
}
