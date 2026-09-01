import { apiFetch } from './apiClient';
import { API_BASE_URL as BASE_URL } from '../config';

/** Calls the fuel-consumption/cost-savings prediction agent. No mock fallback -- see congestionService.js. */
export const predictFuel = async (payload) => {
  const res = await apiFetch(`${BASE_URL}/fuel/predict`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Fuel prediction request failed');
  return res.json();
};
