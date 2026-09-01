import { apiFetch } from './apiClient';
const BASE_URL = 'http://localhost:8000/api';

export const fetchDashboard = async () => {
  const res = await apiFetch(`${BASE_URL}/dashboard`);
  if (!res.ok) throw new Error('Failed to fetch dashboard');
  return res.json();
};

export const fetchEvents = async () => {
  const res = await apiFetch(`${BASE_URL}/events`);
  if (!res.ok) throw new Error('Failed to fetch events');
  return res.json();
};

export const fetchRisks = async () => {
  const res = await apiFetch(`${BASE_URL}/risks`);
  if (!res.ok) throw new Error('Failed to fetch risks');
  return res.json();
};

export const runWorkflow = async (sessionId = null) => {
  const url = sessionId ? `${BASE_URL}/run-workflow?session_id=${sessionId}` : `${BASE_URL}/run-workflow`;
  const res = await apiFetch(url);
  if (!res.ok) throw new Error('Failed to run workflow');
  return res.json();
};

export const fetchAgents = async () => {
  const res = await apiFetch(`${BASE_URL}/agents`);
  if (!res.ok) throw new Error('Failed to fetch agents');
  return res.json();
};

export const fetchRecommendations = async () => {
  const res = await apiFetch(`${BASE_URL}/recommendations`);
  if (!res.ok) throw new Error('Failed to fetch recommendations');
  return res.json();
};

export const fetchGovernanceAgents = async () => {
  const res = await apiFetch(`${BASE_URL}/governance/agents`);
  if (!res.ok) throw new Error('Failed to fetch governance agents');
  return res.json();
};

export const fetchGovernanceExecutions = async () => {
  const res = await apiFetch(`${BASE_URL}/governance/executions`);
  if (!res.ok) throw new Error('Failed to fetch governance executions');
  return res.json();
};

export const fetchGovernanceAudit = async () => {
  const res = await apiFetch(`${BASE_URL}/governance/audit`);
  if (!res.ok) throw new Error('Failed to fetch governance audit');
  return res.json();
};

export const fetchGovernanceApprovals = async () => {
  const res = await apiFetch(`${BASE_URL}/governance/approvals`);
  if (!res.ok) throw new Error('Failed to fetch governance approvals');
  return res.json();
};

export const approveGovernanceRequest = async (id) => {
  const res = await apiFetch(`${BASE_URL}/governance/approvals/${id}/approve`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to approve request');
  return res.json();
};

export const rejectGovernanceRequest = async (id) => {
  const res = await apiFetch(`${BASE_URL}/governance/approvals/${id}/reject`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to reject request');
  return res.json();
};

export const updateAgentStatus = async (agentId, status) => {
  const res = await apiFetch(`${BASE_URL}/governance/agents/${agentId}/status?status=${status}`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to update agent status');
  return res.json();
};
