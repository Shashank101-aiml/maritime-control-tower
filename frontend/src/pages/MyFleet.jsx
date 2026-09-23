import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Container, Plus, RefreshCw, AlertCircle, CheckCircle, BadgeCheck, TriangleAlert, Pause, Play,
  Trash2, MapPin, Gauge, Radio, Waves, Route as RouteIcon, X,
} from 'lucide-react';
import FleetMap, { RISK_COLORS } from '../components/FleetMap';
import LoadingSpinner from '../components/LoadingSpinner';
import { getTwin, buildCoordLookup, lanePathToPoints } from '../services/twinService';
import {
  VESSEL_TYPES, listFleet, getVessel, registerVessel, updateVessel, removeVessel,
} from '../services/fleetService';
import { hasRole } from '../utils/permissions';

const POLL_MS = 30 * 1000;
const EMPTY_FORM = { name: '', mmsi: '', imo: '', vessel_type: 'container_ship', call_sign: '', flag: '' };

const STATUS = {
  tracking: { label: 'Live', color: 'var(--accent-emerald)' },
  no_signal: { label: 'Signal lost', color: 'var(--accent-amber)' },
  awaiting_signal: { label: 'Awaiting first signal', color: 'var(--text-subtle)' },
  paused: { label: 'Paused', color: 'var(--text-subtle)' },
};

const SEVERITY_COLOR = { critical: '#fb7185', high: '#fb7185', warning: '#fbbf24' };

const label = { display: 'block', fontSize: '0.78rem', color: 'var(--text-subtle)', marginBottom: '6px' };

const coord = (value, pos, neg) => `${Math.abs(value).toFixed(2)}°${value >= 0 ? pos : neg}`;

const ago = (minutes) => {
  if (minutes == null) return '—';
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${Math.round(minutes)} min ago`;
  if (minutes < 60 * 48) return `${Math.round(minutes / 60)} h ago`;
  return `${Math.round(minutes / 1440)} days ago`;
};

/** Keeps a path continuous across the antimeridian (e.g. trans-Pacific
 *  lanes) so it draws as one line instead of streaking across the world. */
const unwrapLongitudes = (points) => {
  const out = [];
  points.forEach(([lat, lon], i) => {
    let adjusted = lon;
    if (i > 0) {
      const prev = out[i - 1][1];
      while (adjusted - prev > 180) adjusted -= 360;
      while (adjusted - prev < -180) adjusted += 360;
    }
    out.push([lat, adjusted]);
  });
  return out;
};

function Chip({ color, children, title }) {
  return (
    <span
      title={title}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '2px 8px', borderRadius: '999px',
        border: `1px solid ${color}`, color, fontSize: '0.7rem', fontWeight: 600, whiteSpace: 'nowrap',
      }}
    >
      {children}
    </span>
  );
}

function Stat({ title, value, tone }) {
  return (
    <div className="panel" style={{ border: '1px solid var(--border-light)' }}>
      <div style={{ color: 'var(--text-muted)', fontSize: '0.82rem', marginBottom: '6px' }}>{title}</div>
      <div style={{ fontSize: '1.9rem', fontWeight: 'bold', color: tone || 'var(--text-strong)' }}>{value}</div>
    </div>
  );
}

function VerificationBadge({ identity }) {
  if (identity.verification === 'verified') {
    return <Chip color="var(--accent-emerald)" title="The ship's own AIS broadcast matches what you registered"><BadgeCheck size={12} /> Verified by AIS</Chip>;
  }
  if (identity.verification === 'mismatch') {
    return <Chip color="var(--accent-rose)" title={identity.note}><TriangleAlert size={12} /> Identity mismatch</Chip>;
  }
  return <Chip color="var(--text-subtle)" title="Verified automatically once the ship's own AIS identity message is received"><Radio size={12} /> Not yet verified</Chip>;
}

export default function MyFleet({ user, setActiveTab }) {
  const canSeeAll = hasRole(user, 'supervisor');
  const [scope, setScope] = useState('mine');
  const [fleet, setFleet] = useState(null);
  const [error, setError] = useState(null);
  const [twin, setTwin] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState(null);
  const [confirmingRemove, setConfirmingRemove] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setFleet(await listFleet(scope));
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  }, [scope]);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, POLL_MS);
    return () => clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    getTwin().then(setTwin).catch(() => setTwin(null));
  }, []);

  // The selected vessel's track and alert history, refreshed with the list.
  useEffect(() => {
    if (selectedId == null) { setDetail(null); return undefined; }
    let cancelled = false;
    const load = () => getVessel(selectedId)
      .then((d) => { if (!cancelled) setDetail(d); })
      .catch(() => { if (!cancelled) setDetail(null); });
    load();
    const timer = setInterval(load, POLL_MS);
    return () => { cancelled = true; clearInterval(timer); };
  }, [selectedId]);

  useEffect(() => { setConfirmingRemove(false); }, [selectedId]);

  const lanes = useMemo(() => {
    if (!twin?.edges) return [];
    const lookup = buildCoordLookup(twin, null);
    return twin.edges
      .map((e) => ({
        id: e.lane_id,
        risk: e.risk,
        points: unwrapLongitudes(lanePathToPoints(twin, [e.lane_id], e.port_a, lookup).map((p) => [p.lat, p.lon])),
      }))
      .filter((l) => l.points.length >= 2);
  }, [twin]);

  const vessels = fleet?.vessels ?? [];
  const selected = vessels.find((v) => v.id === selectedId) ? (detail && detail.id === selectedId ? detail : vessels.find((v) => v.id === selectedId)) : null;

  const run = async (action, successText) => {
    setNotice(null);
    try {
      await action();
      if (successText) setNotice({ kind: 'ok', text: successText });
      await refresh();
      return true;
    } catch (err) {
      setNotice({ kind: 'error', text: err.message });
      return false;
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    let created = null;
    const ok = await run(async () => {
      created = await registerVessel({
        name: form.name, mmsi: form.mmsi, imo: form.imo || null, vessel_type: form.vessel_type,
        call_sign: form.call_sign || null, flag: form.flag || null,
      });
    }, `${form.name.toUpperCase()} registered. It will appear on the map as soon as AIS hears it.`);
    setSubmitting(false);
    if (ok) {
      setForm(EMPTY_FORM);
      setShowForm(false);
      if (created) setSelectedId(created.id);
    }
  };

  if (error && !fleet) {
    return (
      <div className="page-wrapper">
        <div className="glass-panel" style={{ textAlign: 'center', padding: '40px', borderColor: 'var(--accent-rose)' }}>
          <AlertCircle size={36} color="var(--accent-rose)" style={{ margin: '0 auto 12px' }} />
          <p style={{ color: 'var(--text-main)' }}>{error}</p>
        </div>
      </div>
    );
  }
  if (!fleet) return <LoadingSpinner message="Loading your fleet…" />;

  const { summary, tracking } = fleet;
  const viewingAll = scope === 'all';

  return (
    <div className="page-wrapper">
      <div className="section-header" style={{ marginBottom: '20px' }}>
        <div>
          <h1 className="section-title" style={{ fontSize: '1.8rem', color: 'var(--text-strong)' }}>
            <Container size={28} color="var(--accent-teal)" />
            {viewingAll ? 'All Fleets' : 'My Fleet'}
          </h1>
          <p style={{ color: 'var(--text-muted)', marginTop: '4px' }}>
            Register your ships by IMO / MMSI. They are tracked live over AIS and watched around the clock by the
            Fleet Monitoring Agent, placed on the digital twin's shipping lanes with the sea state at their position.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
          {canSeeAll && (
            <div style={{ display: 'flex', gap: '6px' }} role="group" aria-label="Fleet scope">
              <button className={scope === 'mine' ? 'btn-action' : 'btn-secondary'} onClick={() => { setScope('mine'); setSelectedId(null); }}>My fleet</button>
              <button className={scope === 'all' ? 'btn-action' : 'btn-secondary'} onClick={() => { setScope('all'); setSelectedId(null); }}>All fleets</button>
            </div>
          )}
          <button className="btn-secondary" onClick={refresh}><RefreshCw size={15} /> Refresh</button>
          {!viewingAll && (
            <button className="btn-action" onClick={() => setShowForm((s) => !s)}>
              {showForm ? <X size={16} /> : <Plus size={16} />} {showForm ? 'Cancel' : 'Add vessel'}
            </button>
          )}
        </div>
      </div>

      {!tracking.configured && (
        <div className="glass-panel" role="status" style={{ padding: '12px 16px', marginBottom: '16px', borderColor: 'var(--accent-amber)' }}>
          <span style={{ color: 'var(--text-main)', fontSize: '0.9rem' }}>
            Live AIS tracking isn't connected on this server (no AISStream key), so vessels can be registered but no
            positions will arrive.
          </span>
        </div>
      )}

      {notice && (
        <div
          className="glass-panel"
          role={notice.kind === 'error' ? 'alert' : 'status'}
          style={{ padding: '12px 16px', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '10px',
            borderColor: notice.kind === 'error' ? 'var(--accent-rose)' : 'var(--accent-emerald)' }}
        >
          {notice.kind === 'error' ? <AlertCircle size={18} color="var(--accent-rose)" /> : <CheckCircle size={18} color="var(--accent-emerald)" />}
          <span style={{ color: 'var(--text-main)', fontSize: '0.9rem' }}>{notice.text}</span>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '16px', marginBottom: '20px' }}>
        <Stat title="Vessels" value={summary.total} />
        <Stat title="Live now" value={summary.tracking} tone="var(--accent-emerald)" />
        <Stat title="Elevated sea-state risk" value={summary.elevated_risk} tone={summary.elevated_risk ? 'var(--accent-amber)' : undefined} />
        <Stat title="Open alerts" value={summary.open_alerts} tone={summary.open_alerts ? 'var(--accent-rose)' : undefined} />
      </div>

      {showForm && (
        <div className="panel" style={{ marginBottom: '20px' }}>
          <div className="section-header">
            <h3 className="section-title"><Plus size={17} /> Register a vessel</h3>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-subtle)' }}>
              {tracking.tracked} of {tracking.capacity} tracking slots used
            </span>
          </div>
          <form onSubmit={handleRegister}>
            <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
              <div>
                <label htmlFor="v-name" style={label}>Vessel name</label>
                <input id="v-name" className="form-input" required maxLength={128} autoComplete="off" placeholder="e.g. EVER GIVEN"
                  value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              </div>
              <div>
                <label htmlFor="v-mmsi" style={label}>MMSI (9 digits)</label>
                <input id="v-mmsi" className="form-input" required inputMode="numeric" pattern="[2-7][0-9]{8}" maxLength={9}
                  title="9 digits, starting with a ship country code (201-775)" autoComplete="off" placeholder="e.g. 353136000"
                  value={form.mmsi} onChange={(e) => setForm({ ...form, mmsi: e.target.value.replace(/\D/g, '') })} />
              </div>
              <div>
                <label htmlFor="v-imo" style={label}>IMO number (optional)</label>
                <input id="v-imo" className="form-input" maxLength={12} autoComplete="off" placeholder="e.g. 9811000"
                  value={form.imo} onChange={(e) => setForm({ ...form, imo: e.target.value })} />
              </div>
              <div>
                <label htmlFor="v-type" style={label}>Type</label>
                <select id="v-type" className="form-input" value={form.vessel_type} onChange={(e) => setForm({ ...form, vessel_type: e.target.value })}>
                  {VESSEL_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
              <div>
                <label htmlFor="v-call" style={label}>Call sign (optional)</label>
                <input id="v-call" className="form-input" maxLength={16} autoComplete="off"
                  value={form.call_sign} onChange={(e) => setForm({ ...form, call_sign: e.target.value })} />
              </div>
              <div>
                <label htmlFor="v-flag" style={label}>Flag (optional)</label>
                <input id="v-flag" className="form-input" maxLength={64} autoComplete="off"
                  value={form.flag} onChange={(e) => setForm({ ...form, flag: e.target.value })} />
              </div>
              <button className="btn-action" type="submit" disabled={submitting}>
                <Plus size={16} /> {submitting ? 'Registering…' : 'Register vessel'}
              </button>
            </div>
            <p className="form-note" style={{ marginTop: '10px' }}>
              Use the ship's international identifiers: the MMSI is what its AIS transmitter broadcasts, and the IMO number
              (7 digits, with a check digit) is its permanent hull ID. Once the ship broadcasts its own identity, we check it
              against what you entered and flag any mismatch, so a mistyped MMSI can't quietly track another ship.
            </p>
          </form>
        </div>
      )}

      {vessels.length === 0 ? (
        <div className="glass-panel" style={{ textAlign: 'center', padding: '48px' }}>
          <Container size={34} color="var(--text-subtle)" style={{ margin: '0 auto 12px' }} />
          <p style={{ color: 'var(--text-main)', marginBottom: '6px' }}>
            {viewingAll ? 'No vessels have been registered yet.' : 'You haven\'t registered any vessels yet.'}
          </p>
          {!viewingAll && (
            <p style={{ color: 'var(--text-subtle)', fontSize: '0.88rem' }}>
              Choose "Add vessel" to register your first ship and start watching it live.
            </p>
          )}
        </div>
      ) : (
        <>
          <FleetMap
            lanes={lanes}
            vessels={vessels}
            selectedId={selectedId}
            onSelect={setSelectedId}
            trail={detail && detail.id === selectedId ? detail.trail : []}
          />

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '20px', marginTop: '20px', alignItems: 'start' }}>
            <div className="panel">
              <div className="section-header">
                <h3 className="section-title">Vessels ({vessels.length})</h3>
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', color: 'var(--text-light)' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-light)', textAlign: 'left', color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase' }}>
                      <th style={{ padding: '10px 8px' }}>Vessel</th>
                      <th style={{ padding: '10px 8px' }}>Status</th>
                      <th style={{ padding: '10px 8px' }}>Speed</th>
                      <th style={{ padding: '10px 8px' }}>Sea state</th>
                    </tr>
                  </thead>
                  <tbody>
                    {vessels.map((v) => {
                      const st = STATUS[v.status] || STATUS.awaiting_signal;
                      return (
                        <tr
                          key={v.id}
                          onClick={() => setSelectedId(v.id)}
                          style={{
                            borderBottom: '1px solid var(--border-light)', cursor: 'pointer',
                            background: v.id === selectedId ? 'var(--surface-subtle)' : 'transparent',
                          }}
                        >
                          <td style={{ padding: '10px 8px' }}>
                            <button
                              type="button"
                              onClick={(e) => { e.stopPropagation(); setSelectedId(v.id); }}
                              style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', textAlign: 'left', color: 'inherit' }}
                            >
                              <div style={{ fontWeight: 'bold', color: 'var(--text-strong)' }}>
                                {v.name}
                                {v.open_alerts > 0 && <span style={{ marginLeft: '6px', color: 'var(--accent-rose)' }} title={`${v.open_alerts} open alert(s)`}>●</span>}
                              </div>
                              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                                {v.vessel_type_label} · MMSI {v.mmsi}{viewingAll && v.owner ? ` · ${v.owner}` : ''}
                              </div>
                            </button>
                          </td>
                          <td style={{ padding: '10px 8px' }}><Chip color={st.color}>{st.label}</Chip></td>
                          <td style={{ padding: '10px 8px', fontSize: '0.85rem' }}>
                            {v.position?.sog_knots != null ? `${v.position.sog_knots.toFixed(1)} kn` : '—'}
                          </td>
                          <td style={{ padding: '10px 8px' }}>
                            {v.risk
                              ? <Chip color={RISK_COLORS[v.risk.level]}>{v.risk.level}</Chip>
                              : <span style={{ color: 'var(--text-muted)' }}>—</span>}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="panel">
              {!selected ? (
                <p style={{ color: 'var(--text-subtle)', padding: '24px 8px', textAlign: 'center' }}>
                  Select a vessel to see its position, sea state, place on the digital twin and alerts.
                </p>
              ) : (
                <VesselDetail
                  vessel={selected}
                  alerts={detail && detail.id === selected.id ? detail.alerts : []}
                  canEdit={selected.is_mine || hasRole(user, 'admin')}
                  confirmingRemove={confirmingRemove}
                  onAskRemove={() => setConfirmingRemove(true)}
                  onCancelRemove={() => setConfirmingRemove(false)}
                  onRemove={() => run(async () => { await removeVessel(selected.id); setSelectedId(null); }, `${selected.name} removed from the fleet.`)}
                  onToggleMonitoring={() => run(
                    () => updateVessel(selected.id, { monitoring_enabled: !selected.monitoring_enabled }),
                    selected.monitoring_enabled ? `Monitoring paused for ${selected.name}.` : `Monitoring resumed for ${selected.name}.`,
                  )}
                  onPlanRoute={setActiveTab ? () => setActiveTab('routes') : null}
                />
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function Row({ icon: Icon, title, children }) {
  return (
    <div style={{ display: 'flex', gap: '10px', padding: '8px 0', borderBottom: '1px solid var(--border-light)' }}>
      <Icon size={15} color="var(--text-subtle)" style={{ marginTop: '2px', flex: 'none' }} />
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: '0.72rem', color: 'var(--text-subtle)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{title}</div>
        <div style={{ fontSize: '0.88rem', color: 'var(--text-main)', marginTop: '2px' }}>{children}</div>
      </div>
    </div>
  );
}

function VesselDetail({ vessel: v, alerts, canEdit, confirmingRemove, onAskRemove, onCancelRemove, onRemove, onToggleMonitoring, onPlanRoute }) {
  const st = STATUS[v.status] || STATUS.awaiting_signal;
  const p = v.position;
  const openAlerts = alerts.filter((a) => !a.resolved_at);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <div>
          <h3 style={{ color: 'var(--text-strong)', fontSize: '1.15rem', margin: 0 }}>{v.name}</h3>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '3px' }}>
            {v.vessel_type_label}{v.flag ? ` · ${v.flag}` : ''} · MMSI {v.mmsi}{v.imo ? ` · IMO ${v.imo}` : ''}{v.call_sign ? ` · ${v.call_sign}` : ''}
          </div>
        </div>
        <Chip color={st.color}>{st.label}</Chip>
      </div>

      <div style={{ margin: '10px 0' }}><VerificationBadge identity={v.identity} /></div>
      {v.identity.verification === 'mismatch' && (
        <p role="alert" style={{ color: 'var(--accent-rose)', fontSize: '0.82rem', margin: '0 0 8px' }}>{v.identity.note} Check the MMSI you entered.</p>
      )}

      <Row icon={MapPin} title="Position">
        {p ? (
          <>
            {coord(p.latitude, 'N', 'S')}, {coord(p.longitude, 'E', 'W')}
            <span style={{ color: 'var(--text-muted)' }}> · {ago(p.age_minutes)}{p.live ? '' : ' (last known)'}</span>
          </>
        ) : (
          <span style={{ color: 'var(--text-muted)' }}>{v.status_detail}</span>
        )}
      </Row>

      {p && (
        <Row icon={Gauge} title="Movement">
          {p.sog_knots != null ? `${p.sog_knots.toFixed(1)} kn` : 'speed n/a'}
          {p.cog_degrees != null ? ` · course ${Math.round(p.cog_degrees)}°` : ''}
          {p.nav_status ? ` · ${p.nav_status}` : ''}
        </Row>
      )}

      <Row icon={Waves} title="Sea state at the vessel">
        {v.risk ? (
          <>
            <Chip color={RISK_COLORS[v.risk.level]}>{v.risk.level} risk</Chip>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>
              {v.risk.wave_height_m != null ? `Waves ${v.risk.wave_height_m} m` : ''}
              {v.risk.wind_gusts_kmh != null ? ` · gusts ${v.risk.wind_gusts_kmh} km/h` : ''}
            </div>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '2px' }}>{v.risk.detail}</div>
          </>
        ) : (
          <span style={{ color: 'var(--text-muted)' }}>{p ? 'Sea-state feed unavailable for this position right now.' : 'Available once the vessel reports a position.'}</span>
        )}
      </Row>

      <Row icon={RouteIcon} title="On the digital twin">
        {v.twin.lane_id ? (
          <>
            On lane <strong>{v.twin.lane_id}</strong> ({v.twin.lane_offset_nm} nm off the track)
            {v.twin.lane_risk != null && <span style={{ color: 'var(--text-muted)' }}> · lane risk {v.twin.lane_risk}/100</span>}
          </>
        ) : p ? 'Not on any known shipping lane.' : '—'}
        {v.twin.corridor && <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Inside the {v.twin.corridor} monitored corridor.</div>}
        {v.twin.nearest_port && (
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Nearest port: {v.twin.nearest_port} ({Math.round(v.twin.nearest_port_nm)} nm)</div>
        )}
      </Row>

      <div style={{ padding: '10px 0' }}>
        <div style={{ fontSize: '0.72rem', color: 'var(--text-subtle)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '6px' }}>
          Alerts {openAlerts.length > 0 ? `(${openAlerts.length} open)` : ''}
        </div>
        {alerts.length === 0 ? (
          <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>No alerts. The agent re-checks this vessel every few minutes.</div>
        ) : alerts.slice(0, 6).map((a) => (
          <div key={a.id} style={{ display: 'flex', gap: '8px', fontSize: '0.82rem', padding: '4px 0', opacity: a.resolved_at ? 0.55 : 1 }}>
            <TriangleAlert size={14} color={SEVERITY_COLOR[a.severity] || 'var(--text-subtle)'} style={{ flex: 'none', marginTop: '2px' }} />
            <span style={{ color: 'var(--text-main)' }}>{a.message}{a.resolved_at ? ' (resolved)' : ''}</span>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '6px' }}>
        {onPlanRoute && v.twin.lane_id && (
          <button className="btn-secondary" style={{ fontSize: '0.8rem' }} onClick={onPlanRoute}><RouteIcon size={14} /> Plan routes</button>
        )}
        {canEdit && (
          <button className="btn-secondary" style={{ fontSize: '0.8rem' }} onClick={onToggleMonitoring}>
            {v.monitoring_enabled ? <><Pause size={14} /> Pause monitoring</> : <><Play size={14} /> Resume monitoring</>}
          </button>
        )}
        {canEdit && !confirmingRemove && (
          <button className="btn-secondary" style={{ fontSize: '0.8rem', color: 'var(--accent-rose)' }} onClick={onAskRemove}><Trash2 size={14} /> Remove</button>
        )}
        {canEdit && confirmingRemove && (
          <>
            <button className="btn-action" style={{ fontSize: '0.8rem', background: 'var(--accent-rose)' }} onClick={onRemove}>Yes, remove {v.name}</button>
            <button className="btn-secondary" style={{ fontSize: '0.8rem' }} onClick={onCancelRemove}>Keep</button>
          </>
        )}
      </div>
      {v.owner && !v.is_mine && <p className="form-note" style={{ marginTop: '10px' }}>Registered by {v.owner}.</p>}
    </div>
  );
}
