import { useRiskContext } from '../context/RiskContext';

/**
 * Custom hook to access fleet hazard risk scores, trends, the real
 * Decision Agent recommendation (Slice 07), and real human feedback on
 * it (Slice 11).
 */
export const useRisks = () => {
  const {
    currentRisk,
    trends,
    trendsByCorridor,
    fleetSummary,
    loading,
    error,
    decision,
    decisionExecutionId,
    decisionStatus,
    decisionMessage,
    requestDecision,
    feedbackStatus,
    feedbackError,
    submitDecisionFeedback,
    refreshRisk
  } = useRiskContext();

  const isHighRisk = (currentRisk?.risk_score ?? 0) > 50;

  return {
    currentRisk,
    trends,
    trendsByCorridor,
    fleetSummary,
    isHighRisk,
    loading,
    error,
    decision,
    decisionExecutionId,
    decisionStatus,
    decisionMessage,
    requestDecision,
    feedbackStatus,
    feedbackError,
    submitDecisionFeedback,
    refreshRisk
  };
};

export default useRisks;
