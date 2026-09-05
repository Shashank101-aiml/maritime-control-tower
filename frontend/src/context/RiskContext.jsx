import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { getFleetRiskAssessment } from '../services/riskService';
import { getRecommendations } from '../services/routeService';

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

  // Real Decision Agent output (Slice 07), fetched on demand rather than
  // polled -- running the full coordinator pipeline on every 20s tick
  // would be wasteful for something the reader only needs when they ask.
  const [decision, setDecision] = useState(null);
  const [decisionStatus, setDecisionStatus] = useState('idle'); // idle | loading | success | pending_approval | rejected | error
  const [decisionMessage, setDecisionMessage] = useState(null);

  // Persists the coordinator session across requestDecision() calls --
  // without this, every click started a brand new session, so a human
  // approving a gated step in Governance had nothing to actually resume:
  // the next click just hit a fresh pending approval on a fresh session.
  const sessionIdRef = useRef(null);

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

  // Calls the real coordinator pipeline (GET /api/recommendations, which
  // now runs ingestion -> risk -> route -> Decision Agent -> explanation)
  // and surfaces whatever it honestly reports -- a completed decision, a
  // pending governance approval, or a rejection -- rather than faking an
  // immediate risk-score drop the way the old local-only version did.
  const requestDecision = useCallback(async () => {
    setDecisionStatus('loading');
    setDecisionMessage(null);
    try {
      const rec = await getRecommendations(sessionIdRef.current);
      sessionIdRef.current = rec.session_id || null;
      if (rec.status === 'PENDING_APPROVAL') {
        setDecision(null);
        setDecisionStatus('pending_approval');
        setDecisionMessage(
          (rec.pending_step ? `${rec.pending_step}: ` : '')
          + (rec.primary_recommendation || 'Awaiting human approval in Governance.')
          + ' Approve it there, then try again to resume this same session.'
        );
      } else if (rec.status === 'REJECTED') {
        setDecision(null);
        setDecisionStatus('rejected');
        setDecisionMessage(rec.primary_recommendation || 'The recommendation was rejected at a governance gate.');
        sessionIdRef.current = null; // a rejected session has nothing left to resume
      } else if (rec.decision) {
        setDecision(rec.decision);
        setDecisionStatus('success');
        sessionIdRef.current = null; // completed -- a fresh click should start a fresh assessment
      } else {
        setDecision(null);
        setDecisionStatus('error');
        setDecisionMessage('The pipeline completed but returned no decision.');
      }
    } catch (err) {
      setDecision(null);
      setDecisionStatus('error');
      setDecisionMessage(err.message);
    }
  }, []);

  return (
    <RiskContext.Provider
      value={{
        currentRisk: riskData.currentRisk,
        trends: riskData.trends,
        trendsByCorridor: riskData.trendsByCorridor,
        fleetSummary: riskData.fleetSummary,
        loading,
        error,
        decision,
        decisionStatus,
        decisionMessage,
        requestDecision,
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
