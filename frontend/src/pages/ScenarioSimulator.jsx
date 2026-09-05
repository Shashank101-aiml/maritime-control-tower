import React, { useEffect, useMemo, useState } from 'react';
import {
  FlaskConical, RefreshCw, AlertCircle, MapPin, ShieldCheck, ShieldAlert, XOctagon, ArrowRight,
} from 'lucide-react';
import { getTwin } from '../services/twinService';
import { simulateScenario } from '../services/routeService';
import { getEventHistory } from '../services/eventService';
import RouteMap from '../components/RouteMap';
import LoadingSpinner from '../components/LoadingSpinner';

const SCENARIOS = [
  { id: 'NONE', label: 'No disruption', description: "Today's real recommendation, unchanged." },
  { id: 'MODERATE', label: 'Moderate disruption', description: 'The corridor\'s risk rises to an elevated (70/100) band.' },
  { id: 'SEVERE', label: 'Severe disruption', description: 'Every lane crossing the corridor is treated as impassable.' },
];

/** Same real-geometry reconstruction RouteRecommendations.jsx uses --
 *  ports from the digital twin, monitored corridors from the live
 *  conditions feed, in real travel order per hop. */
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

export default function ScenarioSimulator() {
  const [twin, setTwin] = useState(null);
  const [twinError, setTwinError] = useState(null);
  const [corridorReadings, setCorridorReadings] = useState(null);

  const [origin, setOrigin] = useState('');
  const [destination, setDestination] = useState('');
  const [corridor, setCorridor] = useState('');
  const [scenario, setScenario] = useState('MODERATE');

  const [result, setResult] = useState(null);
  const [selectedId, setSelectedId] = useState('scenario');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

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
        setTwinError('Could not load the digital twin -- the scenario simulator is unavailable.');
      }
    })();
    getEventHistory().then((r) => {
      setCorridorReadings(r.readings);
      if (r.readings.length) setCorridor(r.readings[0].location);
    }).catch(() => setCorridorReadings([]));
  }, []);

  const ports = (twin?.nodes || []).map((n) => n.id).sort();
  const corridorNames = (corridorReadings || []).map((r) => r.location);
  const coordLookup = useMemo(() => buildCoordLookup(twin, corridorReadings), [twin, corridorReadings]);

  const runSimulation = async () => {
    if (!origin || !destination || !corridor) return;
    setLoading(true);
    setError(null);
    try {
      const r = await simulateScenario(origin, destination, corridor, scenario);
      setResult(r);
      setSelectedId(r.scenario === 'NONE' ? 'baseline' : 'scenario');
    } catch (err) {
      setError(err.message);
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  const mapCandidates = useMemo(() => {
    if (!result) return [];
    const baseline = {
      id: 'baseline',
      label: `Baseline: ${result.baseline_lane_ids.join(' + ')}`,
      risk: result.baseline_risk,
      distance_nm: result.baseline_distance_nm,
      points: lanePathToPoints(twin, result.baseline_lane_ids, result.origin, coordLookup),
    };
    if (!result.scenario_lane_ids) return [baseline];
    const scenarioCandidate = {
      id: 'scenario',
      label: `${result.scenario === 'NONE' ? 'Current' : result.scenario.charAt(0) + result.scenario.slice(1).toLowerCase()}: ${result.scenario_lane_ids.join(' + ')}`,
      risk: result.scenario_risk,
      distance_nm: result.scenario_distance_nm,
      points: lanePathToPoints(twin, result.scenario_lane_ids, result.origin, coordLookup),
    };
    return result.route_changed ? [baseline, scenarioCandidate] : [scenarioCandidate];
  }, [result, twin, coordLookup]);

  return (
    <div className="page-wrapper">
      <div className="section-header" style={{ marginBottom: '24px' }}>
        <div>
          <h1 className="section-title" style={{ fontSize: '1.8rem', color: 'var(--text-strong)' }}>
            <FlaskConical size={28} color="var(--accent-teal)" />
            Scenario Simulator
          </h1>
          <p style={{ color: 'var(--text-muted)', marginTop: '4px' }}>
            What would the real route optimizer recommend if a monitored corridor's conditions worsen or it
            closed entirely -- run on a copy of the digital twin, compared against today's real baseline.
          </p>
        </div>
      </div>

      {twinError ? (
        <div className="glass-panel" style={{ textAlign: 'center', padding: '40px', borderColor: 'var(--accent-rose)' }}>
          <AlertCircle size={36} color="var(--accent-rose)" style={{ margin: '0 auto 12px' }} />
          <p style={{ color: 'var(--text-main)' }}>{twinError}</p>
        </div>
      ) : (
        <>
          <div className="glass-panel" style={{ padding: '20px', marginBottom: '20px' }}>
            <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-subtle)', marginBottom: '6px' }}>Origin</label>
                <select className="form-input" value={origin} onChange={(e) => setOrigin(e.target.value)} style={{ minWidth: '170px' }}>
                  {ports.map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
              <ArrowRight size={16} color="var(--text-subtle)" style={{ marginBottom: '10px' }} />
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-subtle)', marginBottom: '6px' }}>Destination</label>
                <select className="form-input" value={destination} onChange={(e) => setDestination(e.target.value)} style={{ minWidth: '170px' }}>
                  {ports.map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-subtle)', marginBottom: '6px' }}>
                  <MapPin size={11} style={{ verticalAlign: '-1px', marginRight: '3px' }} />
                  Corridor to disrupt
                </label>
                <select className="form-input" value={corridor} onChange={(e) => setCorridor(e.target.value)} style={{ minWidth: '210px' }}>
                  {corridorNames.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>

              <button className="btn-action" onClick={runSimulation} disabled={loading || !origin || !destination || !corridor}>
                <RefreshCw size={16} className={loading ? 'spin' : ''} />
                Run simulation
              </button>
            </div>

            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginTop: '16px', paddingTop: '16px', borderTop: '1px solid var(--border)' }}>
              {SCENARIOS.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setScenario(s.id)}
                  title={s.description}
                  className={scenario === s.id ? 'btn-action' : 'btn-secondary'}
                  style={{ fontSize: '0.8rem' }}
                >
                  {s.id === 'SEVERE' ? <XOctagon size={14} /> : s.id === 'MODERATE' ? <ShieldAlert size={14} /> : <ShieldCheck size={14} />}
                  {s.label}
                </button>
              ))}
            </div>
            <p className="form-note" style={{ marginTop: '10px' }}>
              {SCENARIOS.find((s) => s.id === scenario)?.description}
            </p>
          </div>

          {loading ? (
            <LoadingSpinner message="Running the optimizer against the simulated twin…" />
          ) : error ? (
            <div className="glass-panel" style={{ textAlign: 'center', padding: '40px', borderColor: 'var(--accent-rose)' }}>
              <AlertCircle size={36} color="var(--accent-rose)" style={{ margin: '0 auto 12px' }} />
              <p style={{ color: 'var(--text-main)' }}>{error}</p>
            </div>
          ) : result ? (
            <>
              <div className="workflow-box" style={{
                marginBottom: '24px',
                background: result.no_viable_route ? 'var(--danger-soft)' : result.route_changed ? 'var(--warning-soft)' : 'var(--info-soft)',
                border: `1px solid ${result.no_viable_route ? 'var(--accent-rose)' : result.route_changed ? 'var(--accent-amber)' : 'var(--accent-cyan)'}`,
              }}>
                <div className="workflow-header" style={{ fontSize: '1.05rem' }}>
                  {result.no_viable_route ? <XOctagon size={20} color="var(--accent-rose)" />
                    : result.route_changed ? <ShieldAlert size={20} color="var(--accent-amber)" />
                    : <ShieldCheck size={20} color="var(--accent-cyan)" />}
                  {result.no_viable_route ? 'No route survives this scenario'
                    : result.route_changed ? 'This scenario would change the recommendation'
                    : 'This scenario would not change the recommendation'}
                </div>
                <p style={{ fontSize: '0.95rem', color: 'var(--text-strong)', margin: '10px 0 0', lineHeight: 1.5 }}>
                  {result.summary}
                </p>
              </div>

              <div className="content-grid" style={{ gridTemplateColumns: result.scenario === 'NONE' ? '1fr' : '1fr 1fr', marginBottom: '24px' }}>
                <div className="panel">
                  <div className="section-header">
                    <h3 className="section-title" style={{ fontSize: '1rem' }}>Baseline (today, real)</h3>
                  </div>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-body)' }}>{result.baseline_lane_ids.join(' + ')}</p>
                  <div style={{ display: 'flex', gap: '16px', marginTop: '8px', fontSize: '0.8rem', color: 'var(--text-subtle)' }}>
                    <span>Risk <strong style={{ color: 'var(--text-strong)' }}>{result.baseline_risk}/100</strong></span>
                    <span>Distance <strong style={{ color: 'var(--text-strong)' }}>{Math.round(result.baseline_distance_nm).toLocaleString()} nm</strong></span>
                  </div>
                </div>

                {result.scenario !== 'NONE' && (
                  <div className="panel" style={{ borderColor: result.no_viable_route ? 'var(--accent-rose)' : undefined }}>
                    <div className="section-header">
                      <h3 className="section-title" style={{ fontSize: '1rem' }}>Under this scenario</h3>
                    </div>
                    {result.no_viable_route ? (
                      <p style={{ fontSize: '0.85rem', color: 'var(--accent-rose)' }}>
                        No path within the optimizer's hop limit -- {result.origin} and {result.destination} would be disconnected.
                      </p>
                    ) : (
                      <>
                        <p style={{ fontSize: '0.85rem', color: 'var(--text-body)' }}>{result.scenario_lane_ids.join(' + ')}</p>
                        <div style={{ display: 'flex', gap: '16px', marginTop: '8px', fontSize: '0.8rem', color: 'var(--text-subtle)' }}>
                          <span>Risk <strong style={{ color: 'var(--text-strong)' }}>{result.scenario_risk}/100</strong></span>
                          <span>Distance <strong style={{ color: 'var(--text-strong)' }}>{Math.round(result.scenario_distance_nm).toLocaleString()} nm</strong></span>
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>

              {mapCandidates.length > 0 && (
                <RouteMap candidates={mapCandidates} selectedId={selectedId} onSelect={setSelectedId} height={400} />
              )}
            </>
          ) : (
            <div className="glass-panel" style={{ textAlign: 'center', padding: '48px' }}>
              <FlaskConical size={32} color="var(--text-subtle)" style={{ margin: '0 auto 12px' }} />
              <p style={{ color: 'var(--text-subtle)' }}>
                Pick an origin, destination, corridor, and scenario above, then run the simulation.
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
