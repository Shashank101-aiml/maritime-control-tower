import React, { useState, useEffect } from 'react';
import { ShieldAlert, Activity, Cpu, CheckCircle, XCircle, AlertTriangle, Play, Lock } from 'lucide-react';
import { 
  fetchGovernanceAgents, 
  fetchGovernanceExecutions, 
  fetchGovernanceAudit, 
  fetchGovernanceApprovals, 
  approveGovernanceRequest, 
  rejectGovernanceRequest,
  updateAgentStatus
} from '../services/api';

export default function GovernanceDashboard() {
  const [agents, setAgents] = useState([]);
  const [executions, setExecutions] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [approvals, setApprovals] = useState([]);
  const [activeTab, setActiveTab] = useState('registry');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [agData, exData, auData, apData] = await Promise.all([
        fetchGovernanceAgents(),
        fetchGovernanceExecutions(),
        fetchGovernanceAudit(),
        fetchGovernanceApprovals()
      ]);
      setAgents(agData);
      setExecutions(exData);
      setAuditLogs(auData);
      setApprovals(apData);
    } catch (error) {
      console.error("Failed to load governance data:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (id) => {
    await approveGovernanceRequest(id);
    loadData();
  };

  const handleReject = async (id) => {
    await rejectGovernanceRequest(id);
    loadData();
  };
  
  const handleStatusChange = async (agentId, status) => {
    await updateAgentStatus(agentId, status);
    loadData();
  };

  if (loading && agents.length === 0) {
    return <div style={{ color: 'var(--text-strong)', padding: '20px' }}>Loading Governance Layer...</div>;
  }

  return (
    <div className="page-wrapper" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div className="section-header">
        <div>
          <h1 className="section-title" style={{ fontSize: '1.8rem', color: 'var(--text-strong)' }}>
            <ShieldAlert size={28} color="var(--accent-red)" />
            Agent Governance & Policy Control
          </h1>
          <p style={{ color: 'var(--text-muted)', marginTop: '4px' }}>
            Centralized authorization, human-in-the-loop workflows, and audit trail for autonomous agents.
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
        <MetricCard title="Total Agents" value={agents.length} icon={<Cpu />} />
        <MetricCard title="Active Executions" value={executions.length} icon={<Activity />} />
        <MetricCard title="Pending Approvals" value={approvals.length} icon={<AlertTriangle color="var(--accent-amber)" />} highlight={approvals.length > 0} />
        <MetricCard title="Policy Violations" value={auditLogs.filter(l => l.event_type === 'POLICY_VIOLATION').length} icon={<Lock color="var(--accent-red)" />} />
      </div>

      <div className="panel" style={{ padding: '0', display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', borderBottom: '1px solid var(--border-light)' }}>
          <TabButton active={activeTab === 'registry'} onClick={() => setActiveTab('registry')}>Agent Registry</TabButton>
          <TabButton active={activeTab === 'approvals'} onClick={() => setActiveTab('approvals')}>
            Human Approvals {approvals.length > 0 && <span style={{ background: 'var(--accent-red)', color: 'var(--text-strong)', padding: '2px 6px', borderRadius: '10px', fontSize: '0.75rem', marginLeft: '6px' }}>{approvals.length}</span>}
          </TabButton>
          <TabButton active={activeTab === 'executions'} onClick={() => setActiveTab('executions')}>Execution Trace</TabButton>
          <TabButton active={activeTab === 'audit'} onClick={() => setActiveTab('audit')}>Audit Log</TabButton>
        </div>

        <div style={{ padding: '20px' }}>
          {activeTab === 'registry' && <AgentRegistryTable agents={agents} onStatusChange={handleStatusChange} />}
          {activeTab === 'approvals' && <PendingApprovals approvals={approvals} onApprove={handleApprove} onReject={handleReject} />}
          {activeTab === 'executions' && <ExecutionTrace executions={executions} />}
          {activeTab === 'audit' && <AuditLogTable logs={auditLogs} />}
        </div>
      </div>
    </div>
  );
}

function MetricCard({ title, value, icon, highlight }) {
  return (
    <div className="panel" style={{ border: highlight ? '1px solid var(--accent-amber)' : '1px solid var(--border-light)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '8px' }}>{title}</div>
          <div style={{ fontSize: '2rem', fontWeight: 'bold', color: 'var(--text-strong)' }}>{value}</div>
        </div>
        <div style={{ color: 'var(--text-muted)' }}>{icon}</div>
      </div>
    </div>
  );
}

function TabButton({ children, active, onClick }) {
  return (
    <button 
      onClick={onClick}
      style={{ 
        padding: '12px 24px', 
        background: 'transparent', 
        border: 'none', 
        borderBottom: active ? '2px solid var(--accent-cyan)' : '2px solid transparent',
        color: active ? 'var(--primary)' : 'var(--text-muted)',
        cursor: 'pointer',
        fontSize: '0.9rem',
        fontWeight: active ? 'bold' : 'normal',
        display: 'flex',
        alignItems: 'center'
      }}>
      {children}
    </button>
  );
}

function AgentRegistryTable({ agents, onStatusChange }) {
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', color: 'var(--text-light)' }}>
      <thead>
        <tr style={{ borderBottom: '1px solid var(--border-light)', textAlign: 'left', color: 'var(--text-muted)', fontSize: '0.8rem', textTransform: 'uppercase' }}>
          <th style={{ padding: '12px 8px' }}>Agent Identity</th>
          <th style={{ padding: '12px 8px' }}>Risk / Criticality</th>
          <th style={{ padding: '12px 8px' }}>Version</th>
          <th style={{ padding: '12px 8px' }}>Health</th>
          <th style={{ padding: '12px 8px' }}>Trust</th>
          <th style={{ padding: '12px 8px' }}>Status</th>
          <th style={{ padding: '12px 8px' }}>Actions</th>
        </tr>
      </thead>
      <tbody>
        {agents.map(a => (
          <tr key={a.id} style={{ borderBottom: '1px solid var(--border-light)' }}>
            <td style={{ padding: '12px 8px' }}>
              <div style={{ fontWeight: 'bold', color: 'var(--text-strong)' }}>{a.agent_name}</div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{a.id}</div>
            </td>
            <td style={{ padding: '12px 8px' }}>
              <Badge color={a.risk_level === 'HIGH' || a.risk_level === 'CRITICAL' ? 'var(--accent-red)' : 'var(--accent-emerald)'}>{a.risk_level}</Badge>
            </td>
            <td style={{ padding: '12px 8px', fontSize: '0.85rem' }}>{a.version}</td>
            <td style={{ padding: '12px 8px' }}>
              <Badge color={a.health === 'HEALTHY' ? 'var(--accent-emerald)' : 'var(--accent-red)'}>{a.health}</Badge>
            </td>
            <td style={{ padding: '12px 8px', fontSize: '0.85rem' }}>
              {a.trust_score == null ? (
                <span style={{ color: 'var(--text-muted)' }} title="No recorded executions yet">—</span>
              ) : (
                <span
                  title="success rate x (1 - denial rate) x (1 - policy-violation rate) x (1 - human-override rate)"
                  style={{ color: a.trust_score >= 0.8 ? 'var(--accent-emerald)' : a.trust_score >= 0.5 ? 'var(--accent-amber)' : 'var(--accent-red)', fontWeight: 600 }}
                >
                  {Math.round(a.trust_score * 100)}%
                </span>
              )}
            </td>
            <td style={{ padding: '12px 8px' }}>
              <Badge color={a.status === 'ACTIVE' ? 'var(--accent-cyan)' : 'var(--accent-amber)'}>{a.status}</Badge>
            </td>
            <td style={{ padding: '12px 8px' }}>
              {a.status === 'ACTIVE' ? (
                <button 
                  onClick={() => onStatusChange(a.id, 'QUARANTINED')}
                  style={{ background: 'var(--accent-red)', color: 'var(--text-strong)', border: 'none', padding: '4px 8px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.75rem' }}>
                  Quarantine
                </button>
              ) : (
                <button 
                  onClick={() => onStatusChange(a.id, 'ACTIVE')}
                  style={{ background: 'var(--accent-emerald)', color: '#ffffff', border: 'none', padding: '4px 8px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 'bold' }}>
                  Enable
                </button>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function PendingApprovals({ approvals, onApprove, onReject }) {
  if (approvals.length === 0) {
    return <div style={{ color: 'var(--text-muted)', padding: '20px', textAlign: 'center' }}>No pending approvals.</div>;
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {approvals.map(a => (
        <div key={a.id} style={{ border: '1px solid var(--accent-amber)', borderRadius: '8px', padding: '16px', background: 'var(--warning-soft)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <AlertTriangle color="var(--accent-amber)" size={20} />
              <strong style={{ color: 'var(--text-strong)', fontSize: '1.1rem' }}>Approval Required: {a.agent_name}</strong>
            </div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Execution ID: {a.execution_id}</div>
          </div>
          
          <div style={{ marginBottom: '16px', display: 'flex', gap: '16px' }}>
            <div><span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Risk Level:</span> <Badge color="var(--accent-red)">{a.risk_level}</Badge></div>
            <div><span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Confidence:</span> <span style={{ color: 'var(--text-strong)', fontWeight: 'bold' }}>{(a.confidence * 100).toFixed(1)}%</span></div>
          </div>

          <div style={{ color: 'var(--text-light)', marginBottom: '16px', background: 'var(--bg-darker)', padding: '12px', borderRadius: '4px', fontSize: '0.9rem' }}>
            <strong>Reason:</strong> {a.reason}
          </div>

          <div style={{ display: 'flex', gap: '12px' }}>
            <button 
              onClick={() => onApprove(a.id)}
              style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'var(--accent-emerald)', color: '#ffffff', fontWeight: 'bold', border: 'none', padding: '8px 16px', borderRadius: '4px', cursor: 'pointer' }}>
              <CheckCircle size={16} /> Approve Execution
            </button>
            <button 
              onClick={() => onReject(a.id)}
              style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'transparent', color: 'var(--accent-red)', border: '1px solid var(--accent-red)', padding: '8px 16px', borderRadius: '4px', cursor: 'pointer' }}>
              <XCircle size={16} /> Reject
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

function ExecutionTrace({ executions }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {executions.map(e => (
        <div key={e.id} style={{ display: 'flex', alignItems: 'center', padding: '12px', border: '1px solid var(--border-light)', borderRadius: '6px', background: 'var(--bg-darker)' }}>
          <div style={{ width: '150px', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
            {new Date(e.started_at).toLocaleTimeString()}
          </div>
          <div style={{ width: '200px', fontWeight: 'bold', color: 'var(--accent-cyan)' }}>
            {e.agent_id}
          </div>
          <div style={{ flex: 1, display: 'flex', gap: '12px', alignItems: 'center' }}>
            {e.confidence !== null && (
              <span style={{ fontSize: '0.8rem', color: 'var(--text-light)' }}>
                Conf: {(e.confidence * 100).toFixed(0)}%
              </span>
            )}
            <Badge color={
              e.approval_status === 'PENDING' ? 'var(--accent-amber)' : 
              e.approval_status === 'APPROVED' ? 'var(--accent-emerald)' : 
              e.approval_status === 'NOT_REQUIRED' ? 'var(--text-muted)' : 'var(--accent-red)'
            }>
              {e.approval_status || 'UNKNOWN'}
            </Badge>
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
            {e.id.substring(0, 8)}
          </div>
        </div>
      ))}
    </div>
  );
}

function AuditLogTable({ logs }) {
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', color: 'var(--text-light)' }}>
      <thead>
        <tr style={{ borderBottom: '1px solid var(--border-light)', textAlign: 'left', color: 'var(--text-muted)', fontSize: '0.8rem', textTransform: 'uppercase' }}>
          <th style={{ padding: '12px 8px' }}>Timestamp</th>
          <th style={{ padding: '12px 8px' }}>Event</th>
          <th style={{ padding: '12px 8px' }}>Actor/Agent</th>
          <th style={{ padding: '12px 8px' }}>Action</th>
          <th style={{ padding: '12px 8px' }}>Result</th>
        </tr>
      </thead>
      <tbody>
        {logs.map(l => (
          <tr key={l.id} style={{ borderBottom: '1px solid var(--border-light)', fontSize: '0.85rem' }}>
            <td style={{ padding: '12px 8px', color: 'var(--text-muted)' }}>{new Date(l.timestamp).toLocaleString()}</td>
            <td style={{ padding: '12px 8px', fontWeight: 'bold' }}>{l.event_type}</td>
            <td style={{ padding: '12px 8px' }}>{l.actor}</td>
            <td style={{ padding: '12px 8px' }}>{l.action}</td>
            <td style={{ padding: '12px 8px' }}>
              <Badge color={l.result === 'COMPLETED' || l.result === 'APPROVED' ? 'var(--accent-emerald)' : (l.result === 'DENIED' || l.result === 'FAILED' ? 'var(--accent-red)' : 'var(--accent-cyan)')}>
                {l.result || 'N/A'}
              </Badge>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Badge({ children, color }) {
  return (
    <span style={{ 
      background: 'transparent', 
      color: color, 
      border: `1px solid ${color}`, 
      padding: '2px 8px', 
      borderRadius: '12px', 
      fontSize: '0.7rem',
      fontWeight: 'bold',
      display: 'inline-block'
    }}>
      {children}
    </span>
  );
}
