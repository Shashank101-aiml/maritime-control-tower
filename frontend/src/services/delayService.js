import { apiFetch } from './apiClient';
import { failureMessage, jsonRequest } from './apiErrors';
import { API_BASE_URL as BASE_URL } from '../config';

/**
 * What the real container-journey data covers: journey and lane counts, the
 * date range, which lanes have enough history to report on, what cleaning
 * dropped and why, and the backtest that decided the service reports lane
 * statistics rather than a model score.
 */
export const getDelayOverview = async () => {
  const res = await apiFetch(`${BASE_URL}/delay/overview`);
  if (!res.ok) throw new Error(await failureMessage(res, `Delay overview request failed (${res.status})`));
  return res.json();
};

/**
 * Real transit statistics for one lane, run through governance.
 * Resolves to the agent's response ({ status, assessment | reason | error });
 * a lane without enough history rejects with the server's reason.
 */
export const assessDelay = async ({ origin, destination, loadingDate }) => {
  const res = await apiFetch(
    `${BASE_URL}/delay/assess`,
    jsonRequest('POST', { origin, destination, loading_date: loadingDate || null }),
  );
  if (!res.ok) throw new Error(await failureMessage(res, 'Delay assessment failed'));
  return res.json();
};

/**
 * Live ETA and on-time verdict for each fleet vessel, from its AIS position and
 * speed. scope is 'mine' or (supervisor and up) 'all'.
 */
export const getVoyages = async (scope = 'mine') => {
  const res = await apiFetch(`${BASE_URL}/delay/voyages?scope=${encodeURIComponent(scope)}`);
  if (!res.ok) throw new Error(await failureMessage(res, `Voyage request failed (${res.status})`));
  return res.json();
};

/** Set (or, with both fields empty, clear) where a vessel is due and when. */
export const saveVoyagePlan = async (vesselId, { destinationPort, scheduledArrival }) => {
  const res = await apiFetch(
    `${BASE_URL}/delay/voyages/${vesselId}`,
    jsonRequest('PUT', {
      destination_port: destinationPort || null,
      scheduled_arrival: scheduledArrival ? new Date(scheduledArrival).toISOString() : null,
    }),
  );
  if (!res.ok) throw new Error(await failureMessage(res, 'Could not save the voyage plan'));
  return res.json();
};
