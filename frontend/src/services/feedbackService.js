import { apiFetch } from './apiClient';
import { API_BASE_URL as BASE_URL } from '../config';

/**
 * Records a real human decision against a real agent execution (Slice
 * 11) -- what a human actually did with a recommendation, not just
 * whether a governance gate was cleared. `modificationReason` is
 * required by the backend when action is 'MODIFIED'.
 */
export const submitFeedback = async (executionId, action, modificationReason = null) => {
  const res = await apiFetch(`${BASE_URL}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      execution_id: executionId,
      human_action: action,
      modification_reason: modificationReason,
    }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Feedback request failed (${res.status})`);
  }
  return res.json();
};

/** Real approval/override rate computed from recorded feedback -- null
 *  fields, not fabricated percentages, when nothing has been recorded. */
export const getFeedbackMetrics = async () => {
  const res = await apiFetch(`${BASE_URL}/feedback/metrics`);
  if (!res.ok) throw new Error(`Feedback metrics request failed (${res.status})`);
  return res.json();
};

export const listFeedback = async () => {
  const res = await apiFetch(`${BASE_URL}/feedback`);
  if (!res.ok) throw new Error(`Feedback list request failed (${res.status})`);
  return res.json();
};

export const recordOutcome = async (feedbackId, actualOutcome) => {
  const res = await apiFetch(`${BASE_URL}/feedback/${feedbackId}/outcome`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ actual_outcome: actualOutcome }),
  });
  if (!res.ok) throw new Error(`Outcome recording failed (${res.status})`);
  return res.json();
};
