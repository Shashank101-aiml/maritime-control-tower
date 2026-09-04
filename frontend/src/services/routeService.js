import { createRecommendation } from '../types/Recommendation';
import { apiFetch } from './apiClient';

import { API_BASE_URL as BASE_URL } from '../config';

/**
 * Route recommendation produced by the agent workflow.
 * May come back with status PENDING_APPROVAL / REJECTED when a
 * governance gate stopped the run — the caller shows that honestly
 * rather than substituting an invented recommendation.
 */
export const getRecommendations = async () => {
  const res = await apiFetch(`${BASE_URL}/recommendations`);
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
const toCorridorCard = (candidate, { recommended, index }) => ({
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
    toCorridorCard(route, { recommended: true, index: 0 }),
    ...route.alternatives.map((alt, i) => toCorridorCard(alt, { recommended: false, index: i + 1 })),
  ];

  return { primary, corridors };
};
