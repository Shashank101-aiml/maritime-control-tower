import { apiFetch } from './apiClient';
import { API_BASE_URL as BASE_URL } from '../config';

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

/**
 * Real anomaly score for every port (Slice 09) -- Isolation Forest
 * scored against each port's own historical congestion, not a
 * threshold on the same congestion prediction above.
 */
export const getAnomalies = async () => {
  const res = await apiFetch(`${BASE_URL}/anomalies`);
  if (!res.ok) throw new Error(`Anomaly request failed (${res.status})`);
  const data = await res.json();
  return data.anomalies;
};
