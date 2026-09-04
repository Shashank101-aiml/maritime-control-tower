import { apiFetch } from './apiClient';

import { API_BASE_URL as BASE_URL } from '../config';

/**
 * The full digital twin graph -- 20 real ports as nodes, real shipping
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
 * first. Turns "the user selected a corridor on Vessel Tracking" into
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
