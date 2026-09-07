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
 * threshold on the same congestion prediction above. Each entry also
 * carries a real `live_conditions` reading (current wind/wave/visibility
 * from Open-Meteo at that port's coordinates) -- genuinely live, unlike
 * the anomaly score itself, which only advances when new training data
 * lands.
 */
export const getAnomalies = async () => {
  const res = await apiFetch(`${BASE_URL}/anomalies`);
  if (!res.ok) throw new Error(`Anomaly request failed (${res.status})`);
  const data = await res.json();
  return {
    anomalies: data.anomalies,
    freshness: {
      fetchedAt: data.live_conditions_status?.fetched_at ?? null,
      refreshInSeconds: data.live_conditions_status?.refresh_in_seconds ?? null,
      stale: data.live_conditions_status?.stale ?? null,
      refreshing: data.live_conditions_status?.refreshing ?? null,
    },
  };
};

/**
 * One port's real recent trend (for a sparkline) plus the real feature
 * values a manual congestion prediction for it would use -- fetched on
 * demand when a card is expanded, not bundled into getAnomalies() above,
 * so a routine poll of all 20 ports doesn't drag 26 weeks of history
 * along for every one of them.
 */
export const getPortSnapshot = async (port) => {
  const res = await apiFetch(`${BASE_URL}/anomalies/${encodeURIComponent(port)}/snapshot`);
  if (!res.ok) throw new Error(`Port snapshot request failed (${res.status})`);
  return res.json();
};
