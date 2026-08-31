/**
 * @typedef {Object} RouteRecommendation
 * @property {string} status - Execution status (e.g., "SUCCESS")
 * @property {string} timestamp - Time of AI reasoning
 * @property {boolean} action_required - Whether intervention is required
 * @property {string} primary_recommendation - NLP explanation from Explanation Agent
 * @property {Object|string} suggested_route - Route details or corridor name
 * @property {number} assessed_risk - Associated risk score
 */

/**
 * Normalizes a recommendation object from the backend API.
 * @param {Object} rawRec
 * @returns {RouteRecommendation}
 */
export const createRecommendation = (rawRec = {}) => {
  return {
    status: rawRec.status || 'SUCCESS',
    timestamp: rawRec.timestamp || 'Real-time AI Analysis',
    action_required: typeof rawRec.action_required === 'boolean' ? rawRec.action_required : (rawRec.assessed_risk > 50),
    primary_recommendation: rawRec.primary_recommendation || rawRec.explanation || 'Optimal routing maintained across active fleet corridors.',
    suggested_route: rawRec.suggested_route || rawRec.route || { route: 'Corridor Alpha (Standard Direct)', reason: 'No severe weather or security risks detected.' },
    assessed_risk: typeof rawRec.assessed_risk === 'number' ? rawRec.assessed_risk : (rawRec.risk_score || 15),
  };
};
