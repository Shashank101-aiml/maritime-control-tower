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

/** Ship classes, fuels, routes (with distance and nearest price hub) and price hubs the form offers. */
export const getFuelOptions = async () => {
  const res = await apiFetch(`${BASE_URL}/fuel/options`);
  if (!res.ok) throw new Error('Could not load the fuel options');
  return res.json();
};

/** Live bunker price for every fuel at one hub. */
export const getFuelPrices = async (hub) => {
  const res = await apiFetch(`${BASE_URL}/fuel/prices?hub=${encodeURIComponent(hub)}`);
  if (!res.ok) throw new Error('Could not load bunker prices');
  return res.json();
};
