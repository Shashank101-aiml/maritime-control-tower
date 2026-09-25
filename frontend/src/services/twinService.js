import { apiFetch } from './apiClient';

import { API_BASE_URL as BASE_URL } from '../config';

/**
 * The full digital twin graph -- 25 real ports as nodes (20 with congestion data, 5 Indian ports without), real shipping
 * lanes as edges, each edge's risk freshly computed from live sea
 * state on every request. See backend/app/twin/digital_twin.py's
 * module docstring for exactly which fields are real data, which are
 * labeled assumptions, and which are distance-based placeholders.
 */
export const getTwin = async () => {
  const res = await apiFetch(`${BASE_URL}/twin`);
  if (!res.ok) throw new Error(`Digital twin request failed (${res.status})`);
  return res.json();
};

/**
 * Real lanes whose real waypoints include this corridor, worst risk
 * first. Turns "the user selected a corridor on Corridors & Vessels" into
 * a real port pair to route-optimize around -- a corridor is a sea-
 * state monitoring zone, not a port, so it can't be an origin or
 * destination itself; this finds the actual shipping lanes that
 * genuinely cross it instead of inventing one.
 */
export const lanesCrossingCorridor = (twin, corridorLocation) => {
  if (!twin?.edges || !corridorLocation) return [];
  return twin.edges
    .filter((e) => (e.waypoints || []).includes(corridorLocation))
    .sort((a, b) => (b.risk ?? 0) - (a.risk ?? 0));
};

/**
 * Real coordinates for every point a route might pass through: ports
 * from the digital twin's own nodes, plus every waypoint any edge
 * actually crosses -- from `twin.waypoints` (backend/app/twin/
 * digital_twin.py's to_dict()), not the live conditions feed. A
 * waypoint's coordinate is real either way, live-monitored or not
 * (e.g. the Strait of Gibraltar has no live sea-state feed at all);
 * `corridorReadings`, when available, only adds a live severity color
 * on top for the ones that are actually monitored.
 */
export const buildCoordLookup = (twin, corridorReadings) => {
  const map = {};
  (twin?.nodes || []).forEach((n) => {
    if (n.lat != null && n.lon != null) map[n.id] = { lat: n.lat, lon: n.lon, type: 'port' };
  });

  const severityByName = {};
  (corridorReadings || []).forEach((r) => {
    if (r.location) severityByName[r.location] = r.severity;
  });

  Object.entries(twin?.waypoints || {}).forEach(([name, w]) => {
    map[name] = { lat: w.lat, lon: w.lon, type: 'corridor', severity: severityByName[name] };
  });

  return map;
};

/**
 * Full ordered geometry for one candidate -- ports AND every real
 * waypoint each hop's lane actually crosses, in travel order (a
 * lane's stored waypoints run port_a -> port_b, so they're reversed
 * when a candidate traverses it the other way).
 */
export const lanePathToPoints = (twin, laneIds, origin, coordLookup) => {
  const points = [];
  let current = origin;
  for (const laneId of laneIds || []) {
    const edge = twin?.edges?.find((e) => e.lane_id === laneId);
    if (!edge) break;
    const forward = edge.port_a === current;
    const next = forward ? edge.port_b : edge.port_a;
    // The lane's own sea-only path (backend lane_geometry.py): it starts and ends at
    // each port's open-water approach and includes turning points that keep it off
    // land. Unnamed points are pure geometry -- they draw the line but get no marker.
    const path = forward ? (edge.path || []) : [...(edge.path || [])].reverse();
    path.forEach((p) => {
      points.push(p.name
        ? { ...(coordLookup[p.name] || {}), name: p.name, lat: p.lat, lon: p.lon }
        : { name: null, type: 'geometry', lat: p.lat, lon: p.lon });
    });
    current = next;
  }
  return points;
};
