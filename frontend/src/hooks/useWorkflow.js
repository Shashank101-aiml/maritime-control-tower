import { useState, useEffect, useCallback } from 'react';
import { executeWorkflow, getAgentStatus } from '../services/workflowServices';

/**
 * Custom hook for coordinating the multi-agent workflow pipeline
 */
export const useWorkflow = () => {
  const [agents, setAgents] = useState([]);
  const [workflowRes, setWorkflowRes] = useState(null);
  const [executing, setExecuting] = useState(false);
  const [loadingAgents, setLoadingAgents] = useState(true);
  const [error, setError] = useState(null);

  const loadAgents = useCallback(async () => {
    setLoadingAgents(true);
    try {
      const data = await getAgentStatus();
      setAgents(data);
    } catch (err) {
      setError('Failed to load agent fleet status.');
    } finally {
      setLoadingAgents(false);
    }
  }, []);

  useEffect(() => {
    loadAgents();
    const interval = setInterval(loadAgents, 20000);
    return () => clearInterval(interval);
  }, [loadAgents]);

  const runPipeline = async () => {
    setExecuting(true);
    setError(null);
    try {
      const res = await executeWorkflow();
      setWorkflowRes(res);
      await loadAgents();
      return res;
    } catch (err) {
      setError('Multi-agent workflow execution failed.');
      throw err;
    } finally {
      setExecuting(false);
    }
  };

  return {
    agents,
    workflowRes,
    executing,
    loadingAgents,
    error,
    runPipeline,
    refreshAgents: loadAgents
  };
};

export default useWorkflow;
