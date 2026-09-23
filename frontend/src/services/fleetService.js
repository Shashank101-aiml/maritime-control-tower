import { apiFetch } from './apiClient';
import { failureMessage, jsonRequest } from './apiErrors';
import { API_BASE_URL as BASE_URL } from '../config';

/** Vessel types the backend accepts, with the labels operators see. */
export const VESSEL_TYPES = [
  { value: 'container_ship', label: 'Container ship' },
  { value: 'tanker', label: 'Tanker' },
  { value: 'bulk_carrier', label: 'Bulk carrier' },
  { value: 'general_cargo', label: 'General cargo' },
  { value: 'ro_ro', label: 'Ro-Ro / vehicle carrier' },
  { value: 'gas_carrier', label: 'LNG / LPG carrier' },
  { value: 'passenger', label: 'Passenger / cruise' },
  { value: 'other', label: 'Other' },
];

/** The signed-in user's fleet (scope "mine"), or every fleet (scope "all",
 *  supervisors and admins only) -- vessels, a summary, and tracker status. */
export const listFleet = async (scope = 'mine') => {
  const res = await apiFetch(`${BASE_URL}/fleet/vessels?scope=${scope}`);
  if (!res.ok) throw new Error(await failureMessage(res, 'Could not load the fleet'));
  return res.json();
};

/** One vessel with its recent track and alert history. */
export const getVessel = async (id) => {
  const res = await apiFetch(`${BASE_URL}/fleet/vessels/${id}`);
  if (!res.ok) throw new Error(await failureMessage(res, 'Could not load the vessel'));
  return res.json();
};

export const registerVessel = async (payload) => {
  const res = await apiFetch(`${BASE_URL}/fleet/vessels`, jsonRequest('POST', payload));
  if (!res.ok) throw new Error(await failureMessage(res, 'Could not register the vessel'));
  return res.json();
};

export const updateVessel = async (id, changes) => {
  const res = await apiFetch(`${BASE_URL}/fleet/vessels/${id}`, jsonRequest('PATCH', changes));
  if (!res.ok) throw new Error(await failureMessage(res, 'Could not update the vessel'));
  return res.json();
};

export const removeVessel = async (id) => {
  const res = await apiFetch(`${BASE_URL}/fleet/vessels/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(await failureMessage(res, 'Could not remove the vessel'));
};
