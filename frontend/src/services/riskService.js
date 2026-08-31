import { createRiskAssessment } from '../types/Risk';

const BASE_URL = 'http://localhost:8000/api';

/**
 * Current risk assessment, scored by the trained model on live conditions.
 * No mock fallback — a fabricated risk score is worse than no score.
 */
export const getRisks = async () => {
  const res = await fetch(`${BASE_URL}/risks`);
  if (!res.ok) throw new Error(`Risk request failed (${res.status})`);
  return createRiskAssessment(await res.json());
};

/**
 * Fleet-level risk view. `trends` is intentionally empty: the backend
 * keeps no historical risk time series yet, and inventing a 24h curve
 * would misrepresent made-up numbers as measurements. The chart renders
 * an empty state until real history exists.
 */
export const getFleetRiskAssessment = async () => {
  const [riskRes, dashboardRes] = await Promise.all([
    fetch(`${BASE_URL}/risks`),
    fetch(`${BASE_URL}/dashboard`),
  ]);

  if (!riskRes.ok && !dashboardRes.ok) {
    throw new Error('Backend unreachable — risk data unavailable.');
  }

  const riskData = riskRes.ok ? await riskRes.json() : null;
  const dashboardData = dashboardRes.ok ? await dashboardRes.json() : null;
  const score = riskData?.risk_score ?? dashboardData?.average_fleet_risk ?? null;

  return {
    currentRisk: createRiskAssessment({
      ...(riskData?.details || {}),
      risk_score: score,
    }),
    trends: [],
    fleetSummary: {
      totalVessels: dashboardData?.active_vessels ?? null,
      vesselsAtRisk: null,
      activeAlerts: dashboardData?.active_alerts ?? null,
    },
  };
};
