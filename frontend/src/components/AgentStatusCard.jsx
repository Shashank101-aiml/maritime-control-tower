import React from 'react';
import { Cpu, CheckCircle2, AlertCircle } from 'lucide-react';

export default function AgentStatusCard({ agent }) {
  const isOnline = (agent?.status || 'ONLINE').toUpperCase() === 'ONLINE';

  return (
    <div className="agent-item" style={{ transition: 'all 0.2s ease', cursor: 'default' }}>
      <div className="agent-info">
        <div 
          className="agent-avatar" 
          style={{ 
            background: isOnline ? 'var(--primary-soft)' : 'var(--danger-soft)',
            color: isOnline ? 'var(--accent-cyan)' : 'var(--accent-rose)'
          }}
        >
          <Cpu size={22} />
        </div>
        <div>
          <div className="agent-name" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {agent?.agent_name || 'Autonomous AI Agent'}
            {isOnline ? (
              <CheckCircle2 size={14} color="var(--accent-emerald)" />
            ) : (
              <AlertCircle size={14} color="var(--accent-rose)" />
            )}
          </div>
          <div className="agent-role">{agent?.role || 'Maritime Orchestration Module'}</div>
        </div>
      </div>
      
      <div style={{ textAlign: 'right' }}>
        <div className="status-badge" style={{ 
          padding: '4px 10px', 
          fontSize: '0.75rem',
          background: isOnline ? 'var(--success-soft)' : 'var(--danger-soft)',
          borderColor: isOnline ? 'var(--success-border)' : 'var(--danger-border)',
          color: isOnline ? 'var(--accent-emerald)' : 'var(--accent-rose)'
        }}>
          <div className="pulse-dot" style={{ 
            width: '6px', 
            height: '6px',
            backgroundColor: isOnline ? 'var(--accent-emerald)' : 'var(--accent-rose)',

          }}></div>
          {agent?.status || 'ONLINE'}
        </div>
        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '4px' }}>
          Active: {agent?.last_active || 'Just now'}
        </div>
      </div>
    </div>
  );
}
