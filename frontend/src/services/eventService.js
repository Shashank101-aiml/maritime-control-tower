import { createEvent } from '../types/Event';
import { apiFetch } from './apiClient';

import { API_BASE_URL as BASE_URL } from '../config';

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

  const readings = data.conditions.map((c, i) =>
    createEvent({
      id: `${c.location}-${i}`,
      event_type: c.event_type,
      location: c.location,
      severity: String(c.severity || '').toUpperCase(),
      timestamp: c.conditions?.observed_at || c.timestamp,
      description: c.description,
      coordinates: { lat: c.latitude, lng: c.longitude },
      conditions: c.conditions,
      classification_reason: c.classification_reason,
    })
  );

  // Freshness travels with the data so the UI can show how current it
  // is — otherwise a feed that legitimately updates every 15 minutes is
  // indistinguishable from one that has stopped.
  return {
    readings,
    freshness: {
      fetchedAt: data.fetched_at ?? null,
      refreshInSeconds: data.refresh_in_seconds ?? null,
      sourceIntervalSeconds: data.source_interval_seconds ?? null,
      observedAt: data.conditions[0]?.conditions?.observed_at ?? null,
    },
  };
};
