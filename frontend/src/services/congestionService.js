import { apiFetch } from './apiClient';
const BASE_URL = 'http://localhost:8000/api';

/**
 * Calls the congestion prediction agent. No mock fallback here -- unlike
 * the dashboard, a fabricated prediction number would be actively
 * misleading rather than a harmless placeholder.
 */
export const predictCongestion = async (payload) => {
  const res = await apiFetch(`${BASE_URL}/congestion/predict`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Congestion prediction request failed');
  return res.json();
};
