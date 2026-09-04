import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { getFleetRiskAssessment } from '../services/riskService';

const RiskContext = createContext(null);

export const RiskProvider = ({ children }) => {
  const [riskData, setRiskData] = useState({
    currentRisk: null,
    trends: [],
    trendsByCorridor: {},
    fleetSummary: { totalVessels: '--', vesselsAtRisk: '--', activeAlerts: '--' }
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [mitigationActive, setMitigationActive] = useState(false);

  const fetchRiskAssessment = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getFleetRiskAssessment();
      setRiskData(data);
    } catch (err) {
      setError('Failed to load fleet risk assessment.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRiskAssessment();
    const interval = setInterval(fetchRiskAssessment, 20000); // 20-second risk recalculation loop
    return () => clearInterval(interval);
  }, [fetchRiskAssessment]);

  const activateMitigation = () => {
    setMitigationActive(true);
    // Simulate immediate risk score reduction when mitigation protocol is executed
    setRiskData(prev => ({
      ...prev,
      currentRisk: prev.currentRisk ? {
        ...prev.currentRisk,
        risk_score: Math.max(15, prev.currentRisk.risk_score - 35),
        status: 'MITIGATING VIA SOUTHERN CORRIDOR'
      } : null
    }));
  };

  return (
    <RiskContext.Provider
      value={{
        currentRisk: riskData.currentRisk,
        trends: riskData.trends,
        trendsByCorridor: riskData.trendsByCorridor,
        fleetSummary: riskData.fleetSummary,
        loading,
        error,
        mitigationActive,
        activateMitigation,
        refreshRisk: fetchRiskAssessment
      }}
    >
      {children}
    </RiskContext.Provider>
  );
};

export const useRiskContext = () => {
  const context = useContext(RiskContext);
  if (!context) {
    throw new Error('useRiskContext must be used within a RiskProvider');
  }
  return context;
};
