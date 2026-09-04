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
 *
 * No invented defaults: /api/recommendations already reports an honest
 * status and message when the pipeline is gated (PENDING_APPROVAL) or
 * hasn't produced a route, so a missing suggested_route/assessed_risk
 * here means exactly that -- not "everything is fine". A previous
 * version filled the gap with a fabricated 'Corridor Alpha (Standard
 * Direct)' route and a hardcoded risk of 15, which looked like a real
 * recommendation even when the backend had reported none.
 * @param {Object} rawRec
 * @returns {RouteRecommendation}
 */
export const createRecommendation = (rawRec = {}) => {
  return {
    status: rawRec.status || 'UNKNOWN',
    timestamp: rawRec.timestamp ?? null,
    action_required: typeof rawRec.action_required === 'boolean' ? rawRec.action_required : (rawRec.assessed_risk > 50),
    primary_recommendation: rawRec.primary_recommendation || rawRec.explanation || null,
    suggested_route: rawRec.suggested_route || rawRec.route || null,
    assessed_risk: typeof rawRec.assessed_risk === 'number' ? rawRec.assessed_risk : (typeof rawRec.risk_score === 'number' ? rawRec.risk_score : null),
  };
};
