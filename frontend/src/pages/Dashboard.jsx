import React, { useState, useEffect } from 'react';
import {
  Ship, AlertTriangle, ShieldCheck, Cpu, Play, CheckCircle2,
  Wind, Navigation, RefreshCw, PauseCircle, XCircle, ArrowUpRight
} from 'lucide-react';
import {
  fetchDashboard, fetchAgents, runWorkflow
} from '../services/api';
import { createEvent } from '../types/Event';
import EventCard from '../components/EventCard';
import { useCorridorContext } from '../context/CorridorContext';

export default function Dashboard({ activeTab, setActiveTab }) {
  const [stats, setStats] = useState(null);
  const [agents, setAgents] = useState([]);
  const [workflowRes, setWorkflowRes] = useState(null);
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [error, setError] = useState(null);
  // Shared across tabs (see CorridorContext.jsx) -- picking a corridor
  // from the hazard feed here focuses it on Vessel Tracking's map,
  // highlights it on Risk Analysis, and auto-fills Route Planning, the
  // same as a selection made on any of those pages already does.
  const { selectCorridor } = useCorridorContext();

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [dashboardData, agentsData] = await Promise.all([
        fetchDashboard(),
        fetchAgents()
      ]);
      setStats(dashboardData);
      setAgents(agentsData);
    } catch (err) {
      setError('Could not reach the backend API. Make sure it is running on port 8000.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleRunWorkflow = async () => {
    setExecuting(true);
    try {
      const res = await runWorkflow();
      setWorkflowRes(res);
      await loadData();
    } catch (err) {
      setError('Workflow execution failed.');
    } finally {
      setExecuting(false);
    }
  };

  if (error) {
    return (
      <div className="page-wrapper">
        <div className="panel" style={{ textAlign: 'center', padding: '48px 24px' }}>
          <AlertTriangle size={32} color="var(--danger)" style={{ margin: '0 auto 12px' }} />
          <h2 style={{ fontSize: '1.05rem', marginBottom: '6px' }}>Connection error</h2>
          <p style={{ color: 'var(--text-subtle)', marginBottom: '20px' }}>{error}</p>
          <button className="btn-action" onClick={loadData} style={{ margin: '0 auto' }}>
            <RefreshCw size={15} /> Retry
          </button>
        </div>
      </div>
    );
  }

  const riskScore = stats?.average_fleet_risk;
  const alerts = stats?.active_alerts;

  return (
    <div className="page-wrapper">
      <div className="section-header">
        <div>
          <h1 className="page-title">
            {activeTab === 'workflow' ? 'Agent Pipeline' : 'Fleet Overview'}
          </h1>
          <p className="page-subtitle">
            {activeTab === 'workflow'
              ? 'Run the coordinated agent workflow and inspect each stage of its output.'
              : 'Live fleet posture, hazard feed, and autonomous agent status.'}
          </p>
        </div>
        <button className="btn-secondary" onClick={loadData} disabled={loading}>
          <RefreshCw size={15} className={loading ? 'spin' : ''} /> Refresh
        </button>
      </div>

      <div className="kpi-grid">
        <div className="kpi-card">
          <div>
            <div className="kpi-label">Active vessels</div>
            <div className="kpi-val">{stats?.active_vessels ?? '—'}</div>
          </div>
          <div className="kpi-icon-box" style={{ color: 'var(--info)' }}>
            <Ship size={18} />
          </div>
        </div>

        <div className="kpi-card">
          <div>
            <div className="kpi-label">Weather alerts</div>
            <div className="kpi-val" style={{ color: alerts > 1 ? 'var(--warning)' : undefined }}>
              {alerts ?? '—'}
            </div>
          </div>
          <div className="kpi-icon-box" style={{ color: 'var(--warning)' }}>
            <Wind size={18} />
          </div>
        </div>

        <div className="kpi-card">
          <div>
            <div className="kpi-label">Fleet hazard risk</div>
            <div className="kpi-val" style={{ color: riskScore > 50 ? 'var(--danger)' : undefined }}>
              {riskScore != null ? `${riskScore}` : '—'}
              {riskScore != null && (
                <span style={{ fontSize: '0.9rem', fontWeight: 500, color: 'var(--text-subtle)' }}> /100</span>
              )}
            </div>
          </div>
          <div className="kpi-icon-box" style={{ color: riskScore > 50 ? 'var(--danger)' : 'var(--success)' }}>
            <ShieldCheck size={18} />
          </div>
        </div>

        <div className="kpi-card">
          <div>
            <div className="kpi-label">Active agents</div>
            <div className="kpi-val">{agents.length || '—'}</div>
          </div>
          <div className="kpi-icon-box" style={{ color: 'var(--primary)' }}>
            <Cpu size={18} />
          </div>
        </div>
      </div>

      {activeTab === 'workflow' ? (
        <div className="panel">
          <div className="section-header">
            <div>
              <h2 className="section-title">
                <Cpu size={17} color="var(--primary)" />
                Multi-agent orchestration
              </h2>
              <p className="page-subtitle">
                Ingestion → Risk assessment → Route planning → Explanation, with governance gates between stages.
              </p>
            </div>
            <button className="btn-action" onClick={handleRunWorkflow} disabled={executing}>
              {executing ? <RefreshCw size={15} className="spin" /> : <Play size={15} />}
              {executing ? 'Running…' : 'Run pipeline'}
            </button>
          </div>

          {workflowRes && workflowRes.status === 'PENDING_APPROVAL' ? (
            /* A governance gate stopped the run. Rendering this as
               "completed" would misreport a hold as a success. */
            <div className="workflow-box" style={{ background: 'var(--warning-soft)', borderColor: 'var(--warning-border)' }}>
              <div className="workflow-header" style={{ color: 'var(--warning)' }}>
                <PauseCircle size={17} />
                Paused — human approval required
              </div>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-body)', lineHeight: 1.55 }}>
                {workflowRes.reason}
              </p>
              <div className="workflow-data">
                <div className="data-chunk">
                  <div className="chunk-label">Blocked at</div>
                  <div className="chunk-val">{workflowRes.pending_step}</div>
                </div>
                <div className="data-chunk">
                  <div className="chunk-label">Agent</div>
                  <div className="chunk-val">{workflowRes.agent_id}</div>
                </div>
              </div>
              {setActiveTab && (
                <button
                  className="btn-action"
                  style={{ marginTop: '14px' }}
                  onClick={() => setActiveTab('governance')}
                >
                  Review in Governance <ArrowUpRight size={15} />
                </button>
              )}
            </div>
          ) : workflowRes && (workflowRes.status === 'REJECTED' || workflowRes.status === 'FAILED') ? (
            <div className="workflow-box" style={{ background: 'var(--danger-soft)', borderColor: 'var(--danger-border)' }}>
              <div className="workflow-header" style={{ color: 'var(--danger)' }}>
                <XCircle size={17} />
                Pipeline {workflowRes.status.toLowerCase()}
              </div>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-body)', lineHeight: 1.55 }}>
                {workflowRes.error || 'The run did not complete.'}
              </p>
            </div>
          ) : workflowRes ? (
            <div className="workflow-box">
              <div className="workflow-header">
                <CheckCircle2 size={17} />
                Pipeline completed
              </div>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-body)', lineHeight: 1.55 }}>
                {workflowRes.explanation}
              </p>

              <div className="workflow-data">
                <div className="data-chunk">
                  <div className="chunk-label">Ingested event</div>
                  <div className="chunk-val">
                    {workflowRes.event?.event_type} · {workflowRes.event?.location} ({workflowRes.event?.severity})
                  </div>
                </div>

                <div className="data-chunk">
                  <div className="chunk-label">Assessed hazard score</div>
                  <div className={`chunk-val ${workflowRes.risk_score > 50 ? 'risk-high' : 'risk-low'}`}>
                    {workflowRes.risk_score} / 100
                  </div>
                </div>

                <div className="data-chunk">
                  <div className="chunk-label">Suggested route</div>
                  <div className="chunk-val">{workflowRes.route?.route}</div>
                </div>

                <div className="data-chunk">
                  <div className="chunk-label">Justification</div>
                  <div className="chunk-val" style={{ fontWeight: 400 }}>{workflowRes.route?.reason}</div>
                </div>
              </div>
            </div>
          ) : (
            <div style={{
              textAlign: 'center',
              padding: '48px 20px',
              border: '1px dashed var(--border-strong)',
              borderRadius: 'var(--radius)',
              background: 'var(--surface-subtle)'
            }}>
              <Cpu size={28} color="var(--text-subtle)" style={{ margin: '0 auto 10px' }} />
              <h3 style={{ fontSize: '0.95rem', marginBottom: '4px' }}>Pipeline idle</h3>
              <p style={{ color: 'var(--text-subtle)', maxWidth: '420px', margin: '0 auto' }}>
                Run the pipeline to ingest a live event, score its risk, and generate a routing recommendation.
              </p>
            </div>
          )}
        </div>
      ) : (
        <div className="content-grid">
          <div className="panel">
            <div className="section-header">
              <h2 className="section-title">
                <Navigation size={17} color="var(--primary)" />
                Live hazard feed ({stats?.recent_events?.length || 0} corridors)
              </h2>
            </div>
            <p className="form-note" style={{ marginTop: 0, marginBottom: '14px' }}>
              Every monitored corridor's current real reading -- wave, swell, secondary swell, ocean
              current, visibility, and wind, from Open-Meteo's gridded marine and forecast models.
              Expand a card for the full reading, or focus one to select it everywhere else.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {stats?.recent_events?.length ? stats.recent_events.map((raw) => (
                <EventCard key={raw.id} event={createEvent(raw)} onFocusCorridor={selectCorridor} />
              )) : (
                <p style={{ color: 'var(--text-subtle)' }}>
                  {stats ? 'No live conditions available right now.' : 'Loading…'}
                </p>
              )}
            </div>
          </div>

          <div className="panel">
            <div className="section-header">
              <h2 className="section-title">
                <Cpu size={17} color="var(--primary)" />
                Agent fleet
              </h2>
            </div>

            <div className="agents-list">
              {agents.map((ag, i) => (
                <div key={ag.agent_name || i} className="agent-item">
                  <div className="agent-info">
                    <div className="agent-avatar">
                      <Cpu size={16} />
                    </div>
                    <div>
                      <div className="agent-name">{ag.agent_name}</div>
                      <div className="agent-role">{ag.role}</div>
                    </div>
                  </div>
                  <span className="status-badge">
                    <span className="pulse-dot" />
                    {ag.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
