import { createRiskAssessment } from '../types/Risk';
import { apiFetch } from './apiClient';

import { API_BASE_URL as BASE_URL } from '../config';

/**
 * Current risk assessment, scored by the trained model on live conditions.
 * No mock fallback — a fabricated risk score is worse than no score.
 */
export const getRisks = async () => {
  const res = await apiFetch(`${BASE_URL}/risks`);
  if (!res.ok) throw new Error(`Risk request failed (${res.status})`);
  return createRiskAssessment(await res.json());
};

/** Recorded risk scores over time, for the trajectory chart. */
export const getRiskHistory = async (hours = 24) => {
  const res = await apiFetch(`${BASE_URL}/risks/history?hours=${hours}`);
  if (!res.ok) throw new Error(`Risk history request failed (${res.status})`);
  return res.json();
};

/**
 * Risk score for every monitored corridor, each with its own location,
 * sea-state metrics, and the vessels currently positioned there.
 * GET /risks alone only ever describes a single (the worst) corridor.
 */
export const getRiskCorridors = async () => {
  const res = await apiFetch(`${BASE_URL}/risks/corridors`);
  if (!res.ok) throw new Error(`Corridor risk request failed (${res.status})`);
  return res.json();
};

/**
 * Fleet-level risk view. `trends` now comes from recorded history
 * (risk_readings), not an invented curve — buckets with no reading stay
 * null rather than being plotted as zero.
 */
export const getFleetRiskAssessment = async () => {
  const [riskRes, dashboardRes, historyRes] = await Promise.all([
    apiFetch(`${BASE_URL}/risks`),
    apiFetch(`${BASE_URL}/dashboard`),
    apiFetch(`${BASE_URL}/risks/history?hours=24`),
  ]);

  if (!riskRes.ok && !dashboardRes.ok) {
    throw new Error('Backend unreachable — risk data unavailable.');
  }

  const riskData = riskRes.ok ? await riskRes.json() : null;
  const dashboardData = dashboardRes.ok ? await dashboardRes.json() : null;
  const history = historyRes.ok ? await historyRes.json() : null;
  const score = riskData?.risk_score ?? dashboardData?.average_fleet_risk ?? null;

  return {
    currentRisk: createRiskAssessment({
      ...(riskData?.details || {}),
      risk_score: score,
    }),
    trends: history?.series?.filter((p) => p.score !== null) || [],
    history,
    fleetSummary: {
      totalVessels: dashboardData?.active_vessels ?? null,
      vesselsAtRisk: null,
      activeAlerts: dashboardData?.active_alerts ?? null,
    },
  };
};
