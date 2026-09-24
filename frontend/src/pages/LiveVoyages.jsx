import React, { useCallback, useEffect, useState } from 'react';
import { AlertCircle, Anchor, CalendarClock, Info, RefreshCw, Save, Ship } from 'lucide-react';
import LoadingSpinner from '../components/LoadingSpinner';
import { getVoyages, saveVoyagePlan } from '../services/delayService';
import { getTwin } from '../services/twinService';
import { hasRole } from '../utils/permissions';

const STATUS = {
  on_time: { label: 'On time', color: 'var(--accent-emerald)' },
  early: { label: 'Early', color: 'var(--accent-cyan)' },
  late: { label: 'Late', color: 'var(--accent-rose)' },
  no_reference: { label: 'ETA only', color: 'var(--accent-amber)' },
  not_underway: { label: 'Not under way', color: 'var(--text-subtle)' },
  no_destination: { label: 'No destination', color: 'var(--text-subtle)' },
  no_position: { label: 'No position', color: 'var(--text-subtle)' },
};

const SIGNAL_COLOR = { congested: 'var(--accent-rose)', normal: 'var(--text-subtle)', quiet: 'var(--accent-emerald)' };

const when = (iso) => (iso ? new Date(iso).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—');
const asLocalInput = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};
const signed = (hours) => `${hours > 0 ? '+' : ''}${(hours / 24).toFixed(1)} d`;

function PlanEditor({ voyage, ports, onSaved }) {
  const [port, setPort] = useState(voyage.plan?.destination_port || '');
  const [due, setDue] = useState(asLocalInput(voyage.plan?.scheduled_arrival));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await saveVoyagePlan(voyage.vessel_id, { destinationPort: port, scheduledArrival: due });
      await onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'flex-end', marginTop: '12px' }}>
      <div>
        <label htmlFor={`port-${voyage.vessel_id}`} style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-subtle)', marginBottom: '4px' }}>Destination port</label>
        <select id={`port-${voyage.vessel_id}`} className="form-input" value={port} onChange={(e) => setPort(e.target.value)}>
          <option value="">Use what the ship broadcasts</option>
          {ports.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
      </div>
      <div>
        <label htmlFor={`due-${voyage.vessel_id}`} style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-subtle)', marginBottom: '4px' }}>Due to arrive</label>
        <input id={`due-${voyage.vessel_id}`} type="datetime-local" className="form-input" value={due} onChange={(e) => setDue(e.target.value)} />
      </div>
      <button className="btn-action" onClick={save} disabled={saving}><Save size={14} /> {saving ? 'Saving…' : 'Save plan'}</button>
      {error && <span role="alert" style={{ color: 'var(--accent-rose)', fontSize: '0.8rem' }}>{error}</span>}
    </div>
  );
}

function VoyageCard({ voyage, ports, canEdit, onSaved, showOwner }) {
  const [editing, setEditing] = useState(false);
  const meta = STATUS[voyage.status] || STATUS.no_position;
  const dest = voyage.destination;
  const refs = voyage.references || {};
  const signal = voyage.port_signal;

  return (
    <div className="panel" style={{ borderLeft: `4px solid ${meta.color}` }}>
      <div className="section-header">
        <h3 className="section-title" style={{ fontSize: '1.05rem' }}>
          <Ship size={17} /> {voyage.name}
          {showOwner && voyage.owner && <span style={{ fontSize: '0.75rem', color: 'var(--text-subtle)', marginLeft: '8px' }}>{voyage.owner}</span>}
        </h3>
        <span style={{ color: meta.color, fontWeight: 600, fontSize: '0.85rem' }}>{meta.label}</span>
      </div>
      <p style={{ margin: '0 0 12px', color: 'var(--text-body)', fontSize: '0.9rem' }}>{voyage.headline}</p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px' }}>
        <div className="result-metric">
          <div className="result-metric-label"><Anchor size={11} style={{ display: 'inline', marginRight: '3px' }} />Heading to</div>
          <div className="result-metric-value" style={{ fontSize: '1rem' }}>{dest?.port || '—'}</div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-subtle)' }}>
            {dest?.source === 'plan' ? 'your plan' : dest?.source === 'ais' ? `ship broadcasts “${dest.ais_declared}”` : dest?.ais_declared ? `ship says “${dest.ais_declared}”` : 'nothing broadcast'}
          </div>
        </div>
        <div className="result-metric">
          <div className="result-metric-label">Predicted arrival</div>
          <div className="result-metric-value" style={{ fontSize: '1rem' }}>{when(voyage.predicted_arrival)}</div>
          {voyage.remaining && (
            <div style={{ fontSize: '0.7rem', color: 'var(--text-subtle)' }}>
              {Math.round(voyage.remaining.nm).toLocaleString()} nm left{voyage.speed_knots ? ` at ${voyage.speed_knots} kn` : ''}
            </div>
          )}
        </div>
        {refs.scheduled && (
          <div className="result-metric">
            <div className="result-metric-label"><CalendarClock size={11} style={{ display: 'inline', marginRight: '3px' }} />Your due date</div>
            <div className="result-metric-value" style={{ fontSize: '1rem' }}>{when(refs.scheduled.at)}</div>
            <div style={{ fontSize: '0.7rem', color: meta.color }}>{signed(refs.scheduled.delta_hours)} vs predicted</div>
          </div>
        )}
        {refs.ais_eta && (
          <div className="result-metric">
            <div className="result-metric-label">Ship’s broadcast ETA</div>
            <div className="result-metric-value" style={{ fontSize: '1rem' }}>{when(refs.ais_eta.at)}</div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-subtle)' }}>{signed(refs.ais_eta.delta_hours)} vs predicted</div>
          </div>
        )}
      </div>

      {signal && (
        <p style={{ margin: '12px 0 0', fontSize: '0.82rem', color: SIGNAL_COLOR[signal.level] }}>{signal.text}</p>
      )}
      {voyage.port && !signal && dest?.port && (
        <p style={{ margin: '12px 0 0', fontSize: '0.82rem', color: 'var(--text-subtle)' }}>No congestion history exists for {dest.port}, so no waiting-time signal is shown.</p>
      )}
      {voyage.flags?.length > 0 && (
        <ul style={{ margin: '10px 0 0', paddingLeft: '18px', fontSize: '0.78rem', color: 'var(--text-subtle)' }}>
          {voyage.flags.map((f) => <li key={f}>{f}</li>)}
        </ul>
      )}

      {canEdit && (
        <>
          <button className="btn-secondary" style={{ marginTop: '12px', fontSize: '0.8rem' }} onClick={() => setEditing((v) => !v)}>
            {editing ? 'Close' : voyage.plan ? 'Edit voyage plan' : 'Set destination and due date'}
          </button>
          {editing && <PlanEditor voyage={voyage} ports={ports} onSaved={async () => { await onSaved(); setEditing(false); }} />}
        </>
      )}
    </div>
  );
}

export default function LiveVoyages({ user, setActiveTab }) {
  const canSeeAll = hasRole(user, 'supervisor');
  const [scope, setScope] = useState('mine');
  const [data, setData] = useState(null);
  const [ports, setPorts] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setError(null);
    try {
      setData(await getVoyages(scope));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [scope]);

  useEffect(() => { setLoading(true); load(); }, [load]);
  useEffect(() => {
    getTwin().then((t) => setPorts(t.nodes.map((n) => n.id).sort())).catch(() => setPorts([]));
  }, []);

  const summary = data?.summary || {};

  return (
    <div className="page-wrapper">
      <div className="section-header" style={{ marginBottom: '20px' }}>
        <div>
          <h1 className="section-title" style={{ fontSize: '1.8rem', color: 'var(--text-strong)' }}>
            <Ship size={28} color="var(--accent-cyan)" />
            Live voyages
          </h1>
          <p style={{ color: 'var(--text-muted)', marginTop: '4px', maxWidth: '900px' }}>
            When each of your ships will really arrive, worked out from its live AIS position and recent speed along
            the shipping lanes, and whether that is on time against the due date you set, or against the ETA the crew broadcast.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {canSeeAll && (
            <div style={{ display: 'flex', gap: '6px' }} role="group" aria-label="Voyage scope">
              <button className={scope === 'mine' ? 'btn-action' : 'btn-secondary'} onClick={() => setScope('mine')}>My fleet</button>
              <button className={scope === 'all' ? 'btn-action' : 'btn-secondary'} onClick={() => setScope('all')}>All fleets</button>
            </div>
          )}
          <button className="btn-secondary" onClick={load}><RefreshCw size={15} /> Refresh</button>
        </div>
      </div>

      {loading ? (
        <LoadingSpinner message="Working out arrivals…" />
      ) : error ? (
        <div className="glass-panel" style={{ textAlign: 'center', padding: '40px', borderColor: 'var(--accent-rose)' }}>
          <AlertCircle size={36} color="var(--accent-rose)" style={{ margin: '0 auto 12px' }} />
          <p style={{ color: 'var(--text-main)' }}>{error}</p>
        </div>
      ) : data.voyages.length === 0 ? (
        <div className="panel" style={{ textAlign: 'center', padding: '32px' }}>
          <p style={{ color: 'var(--text-body)' }}>No vessels to assess yet.</p>
          {setActiveTab && <button className="btn-action" onClick={() => setActiveTab('fleet')}>Register a vessel in My Fleet</button>}
        </div>
      ) : (
        <>
          <div className="kpi-grid" style={{ marginBottom: '20px' }}>
            {['late', 'on_time', 'early', 'no_reference'].map((key) => (
              <div className="kpi-card" key={key}>
                <div className="kpi-label">{STATUS[key].label}</div>
                <div className="kpi-value" style={{ color: STATUS[key].color }}>{summary[key] || 0}</div>
              </div>
            ))}
            <div className="kpi-card">
              <div className="kpi-label">Can’t be assessed</div>
              <div className="kpi-value">{(summary.no_position || 0) + (summary.no_destination || 0) + (summary.not_underway || 0)}</div>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginBottom: '20px' }}>
            {data.voyages.map((v) => (
              <VoyageCard key={v.vessel_id} voyage={v} ports={ports} canEdit={v.is_mine || hasRole(user, 'admin')} onSaved={load} showOwner={scope === 'all'} />
            ))}
          </div>

          <div className="panel">
            <div className="section-header"><h3 className="section-title"><Info size={17} /> Read this with care</h3></div>
            <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '0.86rem', color: 'var(--text-body)', lineHeight: 1.6 }}>
              <li>Ships have no timetable. “Late” means later than the date you set, or later than the ETA the crew typed into the ship’s AIS, which is often stale, blank or a default.</li>
              <li>The prediction assumes the ship holds its recent speed; weather, canal queues and port waiting can move it. Congestion at the destination is shown from that port’s own history as context, not added to the ETA.</li>
              <li>Distance follows this system’s shipping lanes when the ship is on one, otherwise it is a straight line and says so. Coverage is what coastal AIS receivers hear, so mid-ocean positions can be hours old.</li>
            </ul>
          </div>
        </>
      )}
    </div>
  );
}
