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

/**
 * Real historical shape of the training data -- overall/per-category
 * late rates, every real value each field takes, and the real
 * plant->port mapping -- so the manual form can offer real dropdown
 * options instead of free text against a single static example.
 */
export const getDelayOverview = async () => {
  const res = await apiFetch(`${BASE_URL}/delay/overview`);
  if (!res.ok) throw new Error(`Delay overview request failed (${res.status})`);
  return res.json();
};

/** One plant's real historical profile (median/most-common real feature
 * values), for a "use this plant's real profile" prefill. */
export const getPlantProfile = async (plantCode) => {
  const res = await apiFetch(`${BASE_URL}/delay/plant/${encodeURIComponent(plantCode)}/profile`);
  if (!res.ok) throw new Error(`Plant profile request failed (${res.status})`);
  return res.json();
};
