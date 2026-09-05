import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Navigation, ShieldCheck, RefreshCw, AlertCircle, CheckCircle2, MapPin, Sliders, X, Waves,
  Route as RouteIcon, ArrowLeftRight, ShieldAlert, Gauge, DollarSign, Scale, Leaf, Link2,
} from 'lucide-react';
import { getTwin, lanesCrossingCorridor } from '../services/twinService';
import { getCorridorOptionsFor } from '../services/routeService';
import { getEventHistory } from '../services/eventService';
import { getSeverityTone, getSeverityLabel } from '../types/Event';
import { useCorridorContext } from '../context/CorridorContext';
import RouteCard from '../components/RouteCard';
import RouteMap from '../components/RouteMap';
import RouteComparisonChart from '../components/Charts/RouteComparisonChart';
import DelayChart from '../components/Charts/DelayChart';
import LoadingSpinner from '../components/LoadingSpinner';

const DEFAULT_WEIGHTS = { risk: 0.4, cost: 0.25, delay: 0.25, emissions: 0.1 };

// One-click starting points for the weight sliders -- each is a real,
// usable combination (they still run through the same normalized
// weighted-sum optimizer), not just the default rebalanced. Lets a
// reader see how the ranking actually shifts without dragging four
// sliders by hand first.
const WEIGHT_PRESETS = [
  { id: 'balanced', label: 'Balanced', icon: Scale, weights: DEFAULT_WEIGHTS },
  { id: 'safety', label: 'Safety first', icon: ShieldAlert, weights: { risk: 0.7, cost: 0.1, delay: 0.1, emissions: 0.1 } },
  { id: 'speed', label: 'Fastest', icon: Gauge, weights: { risk: 0.15, cost: 0.1, delay: 0.65, emissions: 0.1 } },
  { id: 'cost', label: 'Cheapest', icon: DollarSign, weights: { risk: 0.15, cost: 0.65, delay: 0.1, emissions: 0.1 } },
  { id: 'green', label: 'Lowest emissions', icon: Leaf, weights: { risk: 0.15, cost: 0.1, delay: 0.1, emissions: 0.65 } },
];

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

/** Real coordinates for every point a route might pass through: ports
 *  from the digital twin's own nodes, monitored corridors from the
 *  live conditions feed (the same data the Selected Corridor panel and
 *  Event Monitor use) -- nothing interpolated or invented. */
const buildCoordLookup = (twin, corridorReadings) => {
  const map = {};
  (twin?.nodes || []).forEach((n) => {
    if (n.lat != null && n.lon != null) map[n.id] = { lat: n.lat, lon: n.lon, type: 'port' };
  });
  (corridorReadings || []).forEach((r) => {
    if (r.coordinates) map[r.location] = { lat: r.coordinates.lat, lon: r.coordinates.lng, type: 'corridor', severity: r.severity };
  });
  return map;
};

/** Full ordered geometry for one candidate -- ports AND the real
 *  monitored corridors each hop's lane actually crosses, in travel
 *  order (a lane's stored waypoints run port_a -> port_b, so they're
 *  reversed when a candidate traverses it the other way). This is what
 *  RouteMap plots; lanePathToPorts above stays port-only for DelayChart. */
const lanePathToPoints = (twin, laneIds, origin, coordLookup) => {
  const points = [];
  let current = origin;
  if (coordLookup[current]) points.push({ name: current, ...coordLookup[current] });
  for (const laneId of laneIds || []) {
    const edge = twin?.edges?.find((e) => e.lane_id === laneId);
    if (!edge) break;
    const forward = edge.port_a === current;
    const next = forward ? edge.port_b : edge.port_a;
    const wps = forward ? (edge.waypoints || []) : [...(edge.waypoints || [])].reverse();
    wps.forEach((name) => { if (coordLookup[name]) points.push({ name, ...coordLookup[name] }); });
    if (coordLookup[next]) points.push({ name: next, ...coordLookup[next] });
    current = next;
  }
  return points;
};

export default function RouteRecommendations({ setActiveTab }) {
  const { selectedCorridor, clearCorridor } = useCorridorContext();

  const [twin, setTwin] = useState(null);
  const [twinError, setTwinError] = useState(null);
  const [origin, setOrigin] = useState('');
  const [destination, setDestination] = useState('');
  const [weights, setWeights] = useState(DEFAULT_WEIGHTS);
  const [autoNote, setAutoNote] = useState(null);

  // Live sea-state for every monitored corridor -- fetched once. Powers
  // the Selected Corridor panel's current-conditions readout AND gives
  // RouteMap real coordinates for the corridors a lane's waypoints cross
  // (not just the ports), so the map isn't limited to whichever corridor
  // happens to be selected.
  const [corridorReadings, setCorridorReadings] = useState(null);
  useEffect(() => {
    getEventHistory().then((r) => setCorridorReadings(r.readings)).catch(() => setCorridorReadings([]));
  }, []);
  const activeReading = corridorReadings?.find((r) => r.location === selectedCorridor?.location) ?? null;

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
    setAutoNote(null);
    const lanes = lanesCrossingCorridor(twin, selectedCorridor.location);
    if (lanes.length === 0) return;
    const worst = lanes[0];
    setOrigin(worst.port_a);
    setDestination(worst.port_b);
    setAutoNote(`Auto-selected the most exposed lane below — pick a different one any time.`);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [twin, selectedCorridor?.location]);

  // Guards against a stale response overwriting a fresher one -- the
  // corridor auto-fill effect below can change origin/destination twice
  // in quick succession right after the twin loads (default worst-edge
  // pair, then the corridor-derived pair), firing two requests back to
  // back. Without this, whichever network response happens to resolve
  // last wins, even if it was requested first.
  const requestIdRef = useRef(0);

  // Takes weights explicitly rather than closing over the `weights`
  // state, so preset buttons can set new weights and run the query in
  // the same click without hitting a stale-closure value from before
  // the state update lands.
  const runOptimize = useCallback(async (weightsArg) => {
    if (!origin || !destination) return;
    const requestId = ++requestIdRef.current;
    setLoading(true);
    setError(null);
    try {
      const result = await getCorridorOptionsFor(origin, destination, weightsArg);
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
  }, [origin, destination]);

  useEffect(() => {
    if (origin && destination) runOptimize(weights);
    // Only origin/destination changing should auto-run; a weight-slider
    // drag alone waits for "Apply weights" so it isn't a request per tick.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [origin, destination, runOptimize]);

  const applyPreset = (presetWeights) => {
    setWeights(presetWeights);
    runOptimize(presetWeights);
  };

  const swapOriginDestination = () => {
    setOrigin(destination);
    setDestination(origin);
  };

  const ports = (twin?.nodes || []).map((n) => n.id).sort();
  const pathPorts = route ? lanePathToPorts(twin, route.lane_ids, route.origin) : [];

  const coordLookup = useMemo(() => buildCoordLookup(twin, corridorReadings), [twin, corridorReadings]);
  const mapCandidates = useMemo(() => {
    if (!route) return [];
    // Every candidate -- recommended and alternatives alike -- is a
    // path between the same query's origin/destination; only `route`
    // itself (not RouteAlternative) carries those fields, per
    // backend/app/schemas/agent_io.py.
    return [route, ...(route.alternatives || [])].map((c, i) => ({
      id: (c.lane_ids || []).join('+') || `alt-${i}`,
      label: (c.lane_ids || []).join(' + '),
      origin: route.origin,
      destination: route.destination,
      distance_nm: c.distance_nm,
      risk: c.risk,
      points: lanePathToPoints(twin, c.lane_ids, route.origin, coordLookup),
    }));
  }, [route, twin, coordLookup]);

  // Per-hop breakdown for a multi-hop route -- the banner's headline
  // risk is the worst single hop (RouteOptimizer's own aggregation), so
  // for a 2+ hop path it's otherwise invisible which specific leg is
  // driving that number.
  const hops = route && route.lane_ids?.length > 1
    ? (() => {
        const pts = lanePathToPorts(twin, route.lane_ids, route.origin);
        return route.lane_ids.map((laneId, i) => {
          const edge = twin?.edges?.find((e) => e.lane_id === laneId);
          return {
            laneId,
            from: pts[i],
            to: pts[i + 1],
            distance_nm: edge?.distance_nm,
            risk: edge?.risk,
          };
        });
      })()
    : [];

  const setWeight = (key, value) => setWeights((w) => ({ ...w, [key]: value }));

  // Every real lane crossing the selected corridor, not just the worst
  // one the auto-fill effect above picked by default -- lets the reader
  // choose which exposed lane to actually route around, instead of only
  // ever seeing the single option the page picked for them.
  const crossingLanes = twin && selectedCorridor ? lanesCrossingCorridor(twin, selectedCorridor.location) : [];
  const selectLane = (lane) => {
    setOrigin(lane.port_a);
    setDestination(lane.port_b);
    setAutoNote(`${lane.port_a} → ${lane.port_b} — selected from the lanes crossing ${selectedCorridor.location}.`);
  };

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

        <button className="btn-action" onClick={() => runOptimize(weights)} disabled={!origin || !destination}>
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
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-subtle)', marginBottom: '6px' }}>Origin</label>
                <select className="form-input" value={origin} onChange={(e) => setOrigin(e.target.value)} style={{ minWidth: '180px' }}>
                  {ports.map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>

              <button
                type="button" onClick={swapOriginDestination} title="Swap origin and destination"
                className="btn-secondary" style={{ padding: '9px', marginBottom: '1px' }}
              >
                <ArrowLeftRight size={15} />
              </button>

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

              <button className="btn-secondary" onClick={() => runOptimize(weights)} disabled={loading} style={{ whiteSpace: 'nowrap' }}>
                Apply weights
              </button>
            </div>

            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '14px', paddingTop: '14px', borderTop: '1px solid var(--border)' }}>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-subtle)', alignSelf: 'center', marginRight: '4px' }}>Quick presets:</span>
              {WEIGHT_PRESETS.map((preset) => {
                const Icon = preset.icon;
                const isActive = Object.entries(preset.weights).every(([k, v]) => weights[k] === v);
                return (
                  <button
                    key={preset.id}
                    type="button"
                    onClick={() => applyPreset(preset.weights)}
                    className={isActive ? 'btn-action' : 'btn-secondary'}
                    style={{ fontSize: '0.76rem', padding: '6px 12px' }}
                  >
                    <Icon size={13} /> {preset.label}
                  </button>
                );
              })}
            </div>

            <p className="form-note" style={{ marginTop: '10px' }}>
              Weights don't need to add up to 100% — they're normalized automatically. Default
              matches the server's own ROUTE_OPTIMIZATION_WEIGHTS config.
            </p>
          </div>

          {/* Selected Corridor -- live conditions plus every real lane
              that actually crosses it, picked from directly instead of
              only ever seeing the one lane the auto-fill effect chose. */}
          {selectedCorridor && (
            <div className="glass-panel" style={{
              padding: '24px', marginBottom: '20px',
              borderColor: activeReading ? getSeverityTone(activeReading.severity).border : 'var(--accent-cyan)',
            }}>
              <div className="section-header" style={{ marginBottom: '14px' }}>
                <h3 className="section-title" style={{ fontSize: '1.1rem' }}>
                  <MapPin size={18} color="var(--accent-cyan)" />
                  Selected Corridor — {selectedCorridor.location}
                </h3>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  {activeReading && (
                    <span className="status-badge" style={{
                      background: getSeverityTone(activeReading.severity).bg,
                      borderColor: getSeverityTone(activeReading.severity).border,
                      color: getSeverityTone(activeReading.severity).fg,
                    }}>
                      {getSeverityLabel(activeReading.severity)}
                    </span>
                  )}
                  <button className="btn-secondary" onClick={clearCorridor} style={{ padding: '6px 12px', fontSize: '0.8rem' }}>
                    <X size={14} /> Clear
                  </button>
                </div>
              </div>

              {activeReading && (
                <div style={{ display: 'flex', gap: '18px', flexWrap: 'wrap', fontSize: '0.82rem', color: 'var(--text-body)', marginBottom: '16px' }}>
                  <span><Waves size={13} style={{ verticalAlign: '-2px', marginRight: '4px' }} />Wave <strong>{activeReading.conditions?.wave_height_m ?? '—'} m</strong></span>
                  <span>Swell <strong>{activeReading.conditions?.swell_height_m ?? '—'} m</strong></span>
                  <span>Gusts <strong>{activeReading.conditions?.wind_gusts_kmh ?? '—'} km/h</strong></span>
                  {activeReading.event_type && <span style={{ color: 'var(--text-subtle)' }}>{activeReading.event_type}</span>}
                </div>
              )}

              {crossingLanes.length === 0 ? (
                <p style={{ fontSize: '0.85rem', color: 'var(--text-subtle)' }}>
                  No monitored shipping lane crosses {selectedCorridor.location} directly — the route below is
                  unchanged. This corridor is tracked for sea state but isn't on a curated lane path.
                </p>
              ) : (
                <>
                  <p style={{ fontSize: '0.78rem', color: 'var(--text-subtle)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>
                    <RouteIcon size={12} style={{ verticalAlign: '-1px', marginRight: '4px' }} />
                    Real lanes crossing this corridor ({crossingLanes.length}) — pick one to route around
                  </p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {crossingLanes.map((lane) => {
                      const isActive = (origin === lane.port_a && destination === lane.port_b)
                        || (origin === lane.port_b && destination === lane.port_a);
                      const laneTone = lane.risk >= 60 ? 'var(--accent-rose)' : lane.risk >= 35 ? 'var(--accent-amber)' : 'var(--accent-emerald)';
                      return (
                        <button
                          key={lane.lane_id}
                          type="button"
                          onClick={() => selectLane(lane)}
                          title={isActive ? 'Currently routing this lane' : `Route via ${lane.port_a} → ${lane.port_b}`}
                          className={`agent-item corridor-row ${isActive ? 'focused' : ''}`}
                          style={{ width: '100%' }}
                        >
                          <div className="agent-info">
                            <div className="agent-avatar" style={{ background: 'var(--surface-sunken)', color: laneTone }}>
                              <RouteIcon size={14} />
                            </div>
                            <div style={{ textAlign: 'left' }}>
                              <div className="agent-name">{lane.port_a} → {lane.port_b}</div>
                              <div className="agent-role">{Math.round(lane.distance_nm).toLocaleString()} nm</div>
                            </div>
                          </div>
                          <span className="status-badge" style={{ background: 'transparent', borderColor: laneTone, color: laneTone, fontSize: '0.68rem' }}>
                            RISK {lane.risk}/100
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </>
              )}

              {autoNote && (
                <p className="form-note" style={{ marginTop: '12px' }}>{autoNote}</p>
              )}
              {setActiveTab && (
                <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginTop: '14px', paddingTop: '14px', borderTop: '1px solid var(--border)' }}>
                  <button className="btn-secondary" onClick={() => setActiveTab('tracking')} style={{ fontSize: '0.8rem' }}>
                    <MapPin size={14} /> View on map
                  </button>
                  <button className="btn-secondary" onClick={() => setActiveTab('risk')} style={{ fontSize: '0.8rem' }}>
                    <Waves size={14} /> View risk detail
                  </button>
                </div>
              )}
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

                {/* The banner's risk is the worst single hop -- for a
                    multi-hop path that number alone doesn't say which
                    leg is actually driving it. */}
                {hops.length > 0 && (
                  <div style={{ marginTop: '16px', paddingTop: '14px', borderTop: '1px solid var(--border-strong)' }}>
                    <p style={{ fontSize: '0.72rem', color: 'var(--text-subtle)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>
                      <Link2 size={12} style={{ verticalAlign: '-1px', marginRight: '4px' }} />
                      Hop-by-hop breakdown ({hops.length} legs)
                    </p>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      {hops.map((h, i) => (
                        <div key={h.laneId} style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.82rem', color: 'var(--text-body)' }}>
                          <span style={{ color: 'var(--text-subtle)', minWidth: '16px' }}>{i + 1}.</span>
                          <span style={{ flex: 1 }}>{h.from} → {h.to}</span>
                          <span style={{ color: 'var(--text-subtle)' }}>{h.distance_nm != null ? `${Math.round(h.distance_nm).toLocaleString()} nm` : '—'}</span>
                          <span style={{
                            fontWeight: 600,
                            color: h.risk >= 60 ? 'var(--accent-rose)' : h.risk >= 35 ? 'var(--accent-amber)' : 'var(--accent-emerald)',
                          }}>
                            {h.risk != null ? `${h.risk}/100` : '—'}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Real geography for the selected candidate, clickable
                  alternatives drawn alongside it. */}
              <div style={{ marginBottom: '28px' }}>
                <RouteMap candidates={mapCandidates} selectedId={adoptedId} onSelect={setAdoptedId} height={420} />
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
