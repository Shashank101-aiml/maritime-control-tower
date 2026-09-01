import { createEvent } from '../types/Event';
import { apiFetch } from './apiClient';

const BASE_URL = 'http://localhost:8000/api';

/**
 * Current worst-case condition across monitored corridors.
 * Errors propagate: showing invented telemetry would be worse than
 * showing the user that the feed is down.
 */
export const getEvents = async () => {
  const res = await apiFetch(`${BASE_URL}/events`);
  if (!res.ok) throw new Error(`Events request failed (${res.status})`);
  const data = await res.json();
  return Array.isArray(data) ? data.map(createEvent) : [createEvent(data)];
};

/**
 * Live sea state for every monitored corridor, worst first — backed by
 * the Open-Meteo feed via /api/conditions.
 */
export const getEventHistory = async () => {
  const res = await apiFetch(`${BASE_URL}/conditions`);
  if (!res.ok) throw new Error(`Conditions request failed (${res.status})`);
  const data = await res.json();

  if (data.source !== 'live' || !data.conditions?.length) {
    throw new Error(data.error || 'Live conditions feed is unavailable.');
  }

  return data.conditions.map((c, i) =>
    createEvent({
      id: `${c.location}-${i}`,
      event_type: c.event_type,
      location: c.location,
      severity: String(c.severity || '').toUpperCase(),
      timestamp: c.conditions?.observed_at || c.timestamp,
      description: c.description,
      coordinates: { lat: c.latitude, lng: c.longitude },
      conditions: c.conditions,
    })
  );
};
