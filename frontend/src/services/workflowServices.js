const BASE_URL = 'http://localhost:8000/api';

/**
 * Triggers the governed multi-agent workflow.
 * The response may legitimately be PENDING_APPROVAL or REJECTED rather
 * than a completed run — callers must branch on `status` instead of
 * assuming success.
 */
export const executeWorkflow = async () => {
  const res = await fetch(`${BASE_URL}/run-workflow`);
  if (!res.ok) throw new Error(`Workflow request failed (${res.status})`);
  return res.json();
};

/** Live agent registry from the governance layer. */
export const getAgentStatus = async () => {
  const res = await fetch(`${BASE_URL}/agents`);
  if (!res.ok) throw new Error(`Agent status request failed (${res.status})`);
  return res.json();
};
