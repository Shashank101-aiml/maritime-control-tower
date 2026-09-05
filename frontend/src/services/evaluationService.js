import { apiFetch } from './apiClient';
import { API_BASE_URL as BASE_URL } from '../config';

/** Real persisted training metrics per model (Slice 14) -- read back
 *  from what each pipeline/train_*_model.py script actually computed
 *  and saved, not re-derived or invented here. */
export const getModelMetrics = async () => {
  const res = await apiFetch(`${BASE_URL}/evaluation/model-metrics`);
  if (!res.ok) throw new Error(`Model metrics request failed (${res.status})`);
  return res.json();
};

/** Real counts of what governance actually did vs. what would have
 *  happened with no human-in-the-loop gate at all. */
export const getGovernanceImpact = async () => {
  const res = await apiFetch(`${BASE_URL}/evaluation/governance-impact`);
  if (!res.ok) throw new Error(`Governance impact request failed (${res.status})`);
  return res.json();
};
