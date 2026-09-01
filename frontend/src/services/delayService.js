import { apiFetch } from './apiClient';
import { API_BASE_URL as BASE_URL } from '../config';

/** Calls the delay prediction agent. No mock fallback -- see congestionService.js. */
export const predictDelay = async (payload) => {
  const res = await apiFetch(`${BASE_URL}/delay/predict`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Delay prediction request failed');
  return res.json();
};
