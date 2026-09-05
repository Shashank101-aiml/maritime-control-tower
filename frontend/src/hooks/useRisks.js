import { useRiskContext } from '../context/RiskContext';

/**
 * Custom hook to access fleet hazard risk scores, trends, and the
 * real Decision Agent recommendation (Slice 07).
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
    decisionStatus,
    decisionMessage,
    requestDecision,
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
    decisionStatus,
    decisionMessage,
    requestDecision,
    refreshRisk
  };
};

export default useRisks;
