import { useRiskContext } from '../context/RiskContext';

/**
 * Custom hook to access fleet hazard risk scores, trends, and mitigation controls
 */
export const useRisks = () => {
  const {
    currentRisk,
    trends,
    fleetSummary,
    loading,
    error,
    mitigationActive,
    activateMitigation,
    refreshRisk
  } = useRiskContext();

  const isHighRisk = (currentRisk?.risk_score ?? 0) > 50;

  return {
    currentRisk,
    trends,
    fleetSummary,
    isHighRisk,
    loading,
    error,
    mitigationActive,
    activateMitigation,
    refreshRisk
  };
};

export default useRisks;
