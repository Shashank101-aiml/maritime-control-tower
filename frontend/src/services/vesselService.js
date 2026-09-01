import { apiFetch } from './apiClient';
import { API_BASE_URL as BASE_URL } from '../config';

/**
 * Live vessel positions from the AISStream collector.
 * The response carries `configured` / `status` so the UI can distinguish
 * "no API key set" from "connected but nothing in range" rather than
 * showing an ambiguous empty list.
 */
export const getVessels = async () => {
  const res = await apiFetch(`${BASE_URL}/vessels`);
  if (!res.ok) throw new Error(`Vessel request failed (${res.status})`);
  return res.json();
};
