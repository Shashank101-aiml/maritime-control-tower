/**
 * @typedef {Object} RiskAssessment
 * @property {number} risk_score - Numeric risk score between 0 and 100
 * @property {string} category - Risk category (e.g., Weather Hazard, Security, Operational)
 * @property {string} impact - Impact severity: "HIGH" | "MEDIUM" | "LOW"
 * @property {string} likelihood - Probability: "HIGH" | "MEDIUM" | "LOW"
 * @property {string} mitigation_plan - Recommended action or mitigation protocol
 * @property {string} status - Assessment status (e.g., "OPEN", "MITIGATED")
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
    mitigation_plan: rawRisk.mitigation_plan || (score > 50 ? 'Reroute via Southern Maritime Corridor to avoid storm cells.' : 'Maintain standard cruise speed and monitor telemetry.'),
    status: rawRisk.status || (score > 50 ? 'ACTION REQUIRED' : 'NORMAL'),
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
