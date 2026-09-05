import { createRecommendation } from '../types/Recommendation';
import { apiFetch } from './apiClient';

import { API_BASE_URL as BASE_URL } from '../config';

/**
 * Route recommendation produced by the agent workflow.
 * May come back with status PENDING_APPROVAL / REJECTED when a
 * governance gate stopped the run — the caller shows that honestly
 * rather than substituting an invented recommendation.
 */
export const getRecommendations = async (sessionId = null) => {
  const url = sessionId
    ? `${BASE_URL}/recommendations?session_id=${encodeURIComponent(sessionId)}`
    : `${BASE_URL}/recommendations`;
  const res = await apiFetch(url);
  if (!res.ok) throw new Error(`Recommendation request failed (${res.status})`);
  return createRecommendation(await res.json());
};

/**
 * Turns one real RouteOptimizer candidate (the top pick from
 * suggested_route, or one of its `alternatives`) into the shape
 * RouteCard.jsx renders. Every value here is real -- distance_nm and
 * transit_days come from actual great-circle geometry through the
 * digital twin (backend/app/twin/digital_twin.py), risk is live. cost
 * is shown as an explicit estimate because backend/app/twin/digital_twin.py's
 * own docstring is explicit that cost_usd is a distance-based
 * placeholder, not sourced freight data -- labelling it plainly here
 * rather than presenting it as a real fuel/cost figure.
 */
export const candidateToCorridorCard = (candidate, { recommended, index }) => ({
  id: candidate.lane_ids.join('+') || `alt-${index}`,
  name: candidate.lane_ids.join(' + '),
  distance: `${Math.round(candidate.distance_nm).toLocaleString()} nm`,
  estTime: `${candidate.transit_days.toFixed(1)} days`,
  fuelConsumption: `~$${Math.round(candidate.cost_usd).toLocaleString()} est.`,
  reason: candidate.risk >= 60
    ? `Risk ${candidate.risk}/100 -- elevated exposure on this lane right now.`
    : `Risk ${candidate.risk}/100 -- no severe conditions currently reported.`,
  status: candidate.risk >= 60 ? 'ELEVATED RISK' : 'OPTIMAL SAFE',
  riskScore: candidate.risk,
  recommended,
});

/**
 * Real ranked alternatives, sourced from the same RouteRecommendation
 * GET /recommendations already returns -- suggested_route carries the
 * top pick plus its `alternatives`, computed by RouteOptimizer over the
 * digital twin (Slice 06), so no second request is needed here.
 */
export const getCorridorOptions = async () => {
  const primary = await getRecommendations();
  const route = primary.suggested_route;

  if (!route || !Array.isArray(route.alternatives)) {
    return { primary, corridors: [] };
  }

  const corridors = [
    candidateToCorridorCard(route, { recommended: true, index: 0 }),
    ...route.alternatives.map((alt, i) => candidateToCorridorCard(alt, { recommended: false, index: i + 1 })),
  ];

  return { primary, corridors };
};

/**
 * Real point-to-point route optimization -- unlike GET /recommendations
 * (via getRecommendations() above), this calls RouteOptimizer directly
 * and is unaffected by the coordinator's governance session gate: that
 * pipeline starts a fresh session on every call and can only complete
 * once something drives the *same* session_id past its approval step,
 * which never happens through normal page loads. This endpoint has no
 * such gate -- a real ranked result comes back every time.
 */
export const optimizeRoute = async (origin, destination, weights = null) => {
  const params = new URLSearchParams({ origin, destination });
  if (weights) {
    params.set('weights', Object.entries(weights).map(([k, v]) => `${k}:${v}`).join(','));
  }
  const res = await apiFetch(`${BASE_URL}/route/optimize?${params.toString()}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Route optimization failed (${res.status})`);
  }
  return res.json();
};

/**
 * Real what-if scenario (Slice 08): what the optimizer would recommend
 * if the given monitored corridor's conditions worsen (MODERATE) or it
 * became fully impassable (SEVERE), versus today's real baseline for
 * the same origin/destination. See SimulationAgent -- runs on a copy of
 * the digital twin, never the shared live one.
 */
export const simulateScenario = async (origin, destination, corridor, scenario, weights = null) => {
  const params = new URLSearchParams({ origin, destination, corridor, scenario });
  if (weights) {
    params.set('weights', Object.entries(weights).map(([k, v]) => `${k}:${v}`).join(','));
  }
  const res = await apiFetch(`${BASE_URL}/simulate?${params.toString()}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Simulation failed (${res.status})`);
  }
  return res.json();
};

/** optimizeRoute()'s response reshaped into the same corridor-card list
 *  getCorridorOptions() produces, for a specific origin/destination
 *  chosen by the user (or derived from a selected corridor) rather than
 *  whichever lane the coordinator's fleet-wide flow picked. */
export const getCorridorOptionsFor = async (origin, destination, weights = null) => {
  const route = await optimizeRoute(origin, destination, weights);
  return {
    route,
    corridors: [
      candidateToCorridorCard(route, { recommended: true, index: 0 }),
      ...route.alternatives.map((alt, i) => candidateToCorridorCard(alt, { recommended: false, index: i + 1 })),
    ],
  };
};
