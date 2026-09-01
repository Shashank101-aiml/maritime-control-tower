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
 * The backend exposes a single recommended route, not a scored set of
 * alternative corridors, so `corridors` is empty until a real
 * multi-option route API exists. It previously returned three
 * hardcoded corridors with invented distances, fuel figures, and risk
 * scores presented as model output.
 */
export const getCorridorOptions = async () => {
  const primary = await getRecommendations();
  return { primary, corridors: [] };
};
