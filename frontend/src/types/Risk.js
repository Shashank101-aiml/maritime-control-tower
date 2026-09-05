/**
 * @typedef {Object} RiskAssessment
 * @property {number} risk_score - Numeric risk score between 0 and 100
 * @property {string} category - Risk category (e.g., Weather Hazard, Security, Operational)
 * @property {string} impact - Impact severity: "HIGH" | "MEDIUM" | "LOW"
 * @property {string} likelihood - Probability: "HIGH" | "MEDIUM" | "LOW"
 * @property {string|null} mitigation_plan - No longer sourced here; the real
 *   recommendation comes from the Decision Agent (see RiskContext's
 *   requestDecision()) and is rendered separately from this object.
 * @property {string} status - Assessment status (e.g., "OPEN", "MITIGATED")
 * @property {string|null} location - Which monitored corridor this score is about
 * @property {number|null} vessel_count - Vessels currently positioned in that corridor
 * @property {Array} vessels - Compact per-vessel summary (mmsi, name, ship_type, destination)
 * @property {boolean} vessels_configured - Whether AIS tracking is set up at all
 */

/**
 * Normalizes a risk assessment object from the backend API.
 * @param {Object} rawRisk
 * @returns {RiskAssessment}
 */
export const createRiskAssessment = (rawRisk = {}) => {
  const score = typeof rawRisk.risk_score === 'number' ? rawRisk.risk_score : (typeof rawRisk === 'number' ? rawRisk : 25);

  return {
    risk_score: Math.min(100, Math.max(0, score)),
    category: rawRisk.category || (score > 60 ? 'Severe Weather Hazard' : 'Navigational Advisory'),
    impact: rawRisk.impact || (score > 60 ? 'HIGH' : score > 30 ? 'MEDIUM' : 'LOW'),
    likelihood: rawRisk.likelihood || (score > 50 ? 'HIGH' : 'MEDIUM'),
    // No fallback text -- RiskAssessment (backend/app/schemas/agent_io.py)
    // has never had a mitigation_plan field, so this was always a
    // fabricated string standing in for data the API never sent. The
    // real recommendation is the Decision Agent's output, fetched
    // on-demand and rendered separately (see RiskCard's decision prop).
    mitigation_plan: rawRisk.mitigation_plan ?? null,
    status: rawRisk.status || (score > 50 ? 'ACTION REQUIRED' : 'NORMAL'),
    // Passed through as-is, no fallback -- there's no honest default for
    // "which corridor" or "which ships" when the backend didn't say.
    location: rawRisk.location ?? null,
    latitude: rawRisk.latitude ?? null,
    longitude: rawRisk.longitude ?? null,
    vessel_count: rawRisk.vessel_count ?? null,
    vessels: rawRisk.vessels ?? [],
    vessels_configured: rawRisk.vessels_configured ?? false,
  };
};

/**
 * Returns risk level string based on score
 * @param {number} score
 * @returns {"CRITICAL" | "ELEVATED" | "NORMAL"}
 */
export const getRiskLevel = (score) => {
  if (score >= 60) return 'CRITICAL';
  if (score >= 35) return 'ELEVATED';
  return 'NORMAL';
};
