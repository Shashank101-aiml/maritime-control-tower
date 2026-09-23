import { apiFetch } from './apiClient';
import { API_BASE_URL as BASE_URL } from '../config';

// FastAPI reports validation failures as a list of {loc, msg}; everything
// else as a string. Turn either into one readable sentence.
const failureMessage = async (res, fallback) => {
  const body = await res.json().catch(() => null);
  const detail = body?.detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => `${(d.loc || []).slice(1).join('.') || 'input'}: ${d.msg}`).join('; ');
  }
  return detail || fallback;
};

const json = (method, payload) => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload),
});

export const listUsers = async () => {
  const res = await apiFetch(`${BASE_URL}/users`);
  if (!res.ok) throw new Error(await failureMessage(res, 'Could not load users'));
  return res.json();
};

export const createUser = async (payload) => {
  const res = await apiFetch(`${BASE_URL}/users`, json('POST', payload));
  if (!res.ok) throw new Error(await failureMessage(res, 'Could not create the user'));
  return res.json();
};

export const updateUser = async (id, changes) => {
  const res = await apiFetch(`${BASE_URL}/users/${id}`, json('PATCH', changes));
  if (!res.ok) throw new Error(await failureMessage(res, 'Could not update the user'));
  return res.json();
};

export const resetUserPassword = async (id, password) => {
  const res = await apiFetch(`${BASE_URL}/users/${id}/reset-password`, json('POST', { password }));
  if (!res.ok) throw new Error(await failureMessage(res, 'Could not reset the password'));
};
