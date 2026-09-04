import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Navigation, ShieldCheck, RefreshCw, AlertCircle, CheckCircle2, MapPin, Sliders } from 'lucide-react';
import { getTwin, lanesCrossingCorridor } from '../services/twinService';
import { getCorridorOptionsFor } from '../services/routeService';
import { useCorridorContext } from '../context/CorridorContext';
import RouteCard from '../components/RouteCard';
import RouteComparisonChart from '../components/Charts/RouteComparisonChart';
import DelayChart from '../components/Charts/DelayChart';
import LoadingSpinner from '../components/LoadingSpinner';

const DEFAULT_WEIGHTS = { risk: 0.4, cost: 0.25, delay: 0.25, emissions: 0.1 };

/** Reconstructs the ordered port sequence a route actually passes
 *  through from its lane_ids -- e.g. ["Hong Kong", "Singapore",
 *  "Rotterdam"] for a 2-hop path -- by walking each real edge in the
 *  digital twin, not just showing the origin and destination. */
const lanePathToPorts = (twin, laneIds, origin) => {
  const ports = [origin];
  let current = origin;
  for (const laneId of laneIds || []) {
    const edge = twin?.edges?.find((e) => e.lane_id === laneId);
    if (!edge) break;
    current = edge.port_a === current ? edge.port_b : edge.port_a;
    ports.push(current);
  }
  return ports;
};

export default function RouteRecommendations() {
  const { selectedCorridor, clearCorridor } = useCorridorContext();

  const [twin, setTwin] = useState(null);
  const [twinError, setTwinError] = useState(null);
  const [origin, setOrigin] = useState('');
  const [destination, setDestination] = useState('');
  const [weights, setWeights] = useState(DEFAULT_WEIGHTS);
  const [autoNote, setAutoNote] = useState(null);

  const [route, setRoute] = useState(null);
  const [corridors, setCorridors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [adoptedId, setAdoptedId] = useState(null);

  // Load the twin once; default to whichever real lane is currently
  // most exposed, fleet-wide -- the same signal the coordinator's own
  // route step uses, rather than an arbitrary port pair.
  useEffect(() => {
    (async () => {
      try {
        const t = await getTwin();
        setTwin(t);
        if (t.edges?.length) {
          const worst = [...t.edges].sort((a, b) => (b.risk ?? 0) - (a.risk ?? 0))[0];
          setOrigin(worst.port_a);
          setDestination(worst.port_b);
        }
      } catch (err) {
        setTwinError('Could not load the digital twin — route optimization is unavailable.');
        setLoading(false);
      }
    })();
  }, []);

  // A corridor selected elsewhere (Vessel Tracking, Risk Analysis)
  // overrides the default with a real lane that actually crosses it --
  // a corridor is a sea-state zone, not a port, so it can't be an
  // origin/destination itself.
  useEffect(() => {
    if (!twin || !selectedCorridor) return;
    const lanes = lanesCrossingCorridor(twin, selectedCorridor.location);
    if (lanes.length === 0) {
      setAutoNote(
        `No monitored shipping lane crosses ${selectedCorridor.location} directly — showing the route below unchanged.`
      );
      return;
    }
    const worst = lanes[0];
    setOrigin(worst.port_a);
    setDestination(worst.port_b);
    setAutoNote(
      `Auto-selected ${worst.port_a} → ${worst.port_b} — the most exposed real lane crossing ${selectedCorridor.location}, which you selected on Vessel Tracking.`
    );
  }, [twin, selectedCorridor]);

  // Guards against a stale response overwriting a fresher one -- the
  // corridor auto-fill effect below can change origin/destination twice
  // in quick succession right after the twin loads (default worst-edge
  // pair, then the corridor-derived pair), firing two requests back to
  // back. Without this, whichever network response happens to resolve
  // last wins, even if it was requested first.
  const requestIdRef = useRef(0);

  const runOptimize = useCallback(async () => {
    if (!origin || !destination) return;
    const requestId = ++requestIdRef.current;
    setLoading(true);
    setError(null);
    try {
      const result = await getCorridorOptionsFor(origin, destination, weights);
      if (requestId !== requestIdRef.current) return;
      setRoute(result.route);
      setCorridors(result.corridors);
      setAdoptedId(result.corridors[0]?.id ?? null);
    } catch (err) {
      if (requestId !== requestIdRef.current) return;
      setError(err.message);
      setRoute(null);
      setCorridors([]);
    } finally {
      if (requestId === requestIdRef.current) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [origin, destination]);

  useEffect(() => {
    if (origin && destination) runOptimize();
  }, [origin, destination, runOptimize]);

  const ports = (twin?.nodes || []).map((n) => n.id).sort();
  const pathPorts = route ? lanePathToPorts(twin, route.lane_ids, route.origin) : [];

  const setWeight = (key, value) => setWeights((w) => ({ ...w, [key]: value }));

  return (
    <div className="page-wrapper">
      <div className="section-header" style={{ marginBottom: '24px' }}>
        <div>
          <h1 className="section-title" style={{ fontSize: '1.8rem', color: 'var(--text-strong)' }}>
            <Navigation size={28} color="var(--accent-teal)" />
            AI Route Optimization &amp; Waypoints
          </h1>
          <p style={{ color: 'var(--text-muted)', marginTop: '4px' }}>
            Real multi-objective routing over the digital twin — ranked alternatives with actual
            distance, transit time, cost, and live risk, not a single fixed corridor label.
          </p>
        </div>

        <button className="btn-action" onClick={runOptimize} disabled={!origin || !destination}>
          <RefreshCw size={16} className={loading ? 'spin' : ''} />
          Recalculate
        </button>
      </div>

      {twinError ? (
        <div className="glass-panel" style={{ textAlign: 'center', padding: '40px', borderColor: 'var(--accent-rose)' }}>
          <AlertCircle size={36} color="var(--accent-rose)" style={{ margin: '0 auto 12px' }} />
          <p style={{ color: 'var(--text-main)' }}>{twinError}</p>
        </div>
      ) : (
        <>
          {/* Origin / destination / weights controls */}
          <div className="glass-panel" style={{ padding: '20px', marginBottom: '20px' }}>
            <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-subtle)', marginBottom: '6px' }}>Origin</label>
                <select className="form-input" value={origin} onChange={(e) => setOrigin(e.target.value)} style={{ minWidth: '180px' }}>
                  {ports.map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-subtle)', marginBottom: '6px' }}>Destination</label>
                <select className="form-input" value={destination} onChange={(e) => setDestination(e.target.value)} style={{ minWidth: '180px' }}>
                  {ports.map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>

              <div style={{ flex: 1, minWidth: '260px', display: 'flex', gap: '14px', flexWrap: 'wrap' }}>
                {Object.entries(weights).map(([key, value]) => (
                  <div key={key} style={{ minWidth: '110px' }}>
                    <label style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', color: 'var(--text-subtle)', textTransform: 'capitalize' }}>
                      <span><Sliders size={11} style={{ verticalAlign: '-1px', marginRight: '3px' }} />{key}</span>
                      <span>{Math.round(value * 100)}%</span>
                    </label>
                    <input
                      type="range" min="0" max="1" step="0.05" value={value}
                      onChange={(e) => setWeight(key, parseFloat(e.target.value))}
                      style={{ width: '100%' }}
                    />
                  </div>
                ))}
              </div>

              <button className="btn-secondary" onClick={runOptimize} disabled={loading} style={{ whiteSpace: 'nowrap' }}>
                Apply weights
              </button>
            </div>
            <p className="form-note" style={{ marginTop: '10px' }}>
              Weights don't need to add up to 100% — they're normalized automatically. Default
              matches the server's own ROUTE_OPTIMIZATION_WEIGHTS config.
            </p>
          </div>

          {selectedCorridor && (
            <div className="workflow-box" style={{
              marginBottom: '20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              background: 'var(--info-soft)', border: '1px solid var(--accent-cyan)',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-strong)', fontSize: '0.88rem' }}>
                <MapPin size={16} color="var(--accent-cyan)" />
                {autoNote || `Focused on ${selectedCorridor.location}.`}
              </div>
              <button className="btn-secondary" onClick={clearCorridor} style={{ padding: '6px 12px', fontSize: '0.8rem' }}>
                Clear
              </button>
            </div>
          )}

          {loading && !route ? (
            <LoadingSpinner message="Optimizing route across the digital twin…" />
          ) : error ? (
            <div className="glass-panel" style={{ textAlign: 'center', padding: '40px', borderColor: 'var(--accent-rose)' }}>
              <AlertCircle size={36} color="var(--accent-rose)" style={{ margin: '0 auto 12px' }} />
              <p style={{ color: 'var(--text-main)' }}>{error}</p>
            </div>
          ) : route ? (
            <>
              {/* Recommended route banner */}
              <div className="workflow-box" style={{ marginBottom: '28px', background: 'var(--info-soft)', border: '1px solid var(--accent-cyan)' }}>
                <div className="workflow-header" style={{ fontSize: '1.15rem' }}>
                  <CheckCircle2 size={22} color="var(--accent-emerald)" />
                  {route.route}
                </div>
                <p style={{ fontSize: '1rem', color: 'var(--text-strong)', margin: '10px 0', lineHeight: 1.5 }}>
                  {route.reason}
                </p>
                <div style={{ display: 'flex', gap: '20px', marginTop: '14px', fontSize: '0.85rem', color: 'var(--text-muted)', flexWrap: 'wrap' }}>
                  <span>Distance: <strong style={{ color: 'var(--text-strong)' }}>{Math.round(route.distance_nm).toLocaleString()} nm</strong></span>
                  <span>Transit: <strong style={{ color: 'var(--text-strong)' }}>{route.transit_days.toFixed(1)} days</strong></span>
                  <span>Risk: <strong style={{ color: route.risk > 50 ? 'var(--accent-rose)' : 'var(--accent-emerald)' }}>{route.risk}/100</strong></span>
                  <span>Alternatives considered: <strong style={{ color: 'var(--text-strong)' }}>{route.alternatives.length}</strong></span>
                </div>
              </div>

              {/* Charts Row: Route Comparison + Delays */}
              <div className="content-grid" style={{ gridTemplateColumns: '1fr 1fr', marginBottom: '28px' }}>
                <RouteComparisonChart recommended={route} alternatives={route.alternatives} />
                <DelayChart twin={twin} ports={pathPorts} />
              </div>

              {/* Corridor Selection List */}
              <div className="glass-panel" style={{ padding: '24px' }}>
                <div className="section-header" style={{ marginBottom: '20px' }}>
                  <h3 className="section-title" style={{ fontSize: '1.2rem' }}>
                    <MapPin size={22} color="var(--accent-amber)" />
                    Ranked Route Candidates ({corridors.length})
                  </h3>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    Every candidate is a real path through the digital twin, ranked by your weights above
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  {corridors.map((c) => (
                    <RouteCard
                      key={c.id}
                      corridor={c}
                      isSelected={adoptedId === c.id}
                      onSelect={setAdoptedId}
                    />
                  ))}
                </div>

                {adoptedId && (
                  <div style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    background: 'var(--success-soft)', border: '1px solid var(--accent-emerald)',
                    padding: '16px 20px', borderRadius: '12px', marginTop: '24px',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', color: 'var(--accent-emerald)', fontWeight: 700 }}>
                      <ShieldCheck size={24} />
                      <div>
                        <div style={{ fontSize: '1.05rem' }}>Selected for this session: {adoptedId}</div>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 400, marginTop: '2px' }}>
                          A local preference for this browser session only — no fleet-wide dispatch action is
                          taken. Route Optimization has no "execute" capability yet.
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </>
          ) : null}
        </>
      )}
    </div>
  );
}
