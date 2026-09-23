import { apiFetch } from './apiClient';
import { failureMessage, jsonRequest } from './apiErrors';
import { API_BASE_URL as BASE_URL } from '../config';

export const listUsers = async () => {
  const res = await apiFetch(`${BASE_URL}/users`);
  if (!res.ok) throw new Error(await failureMessage(res, 'Could not load users'));
  return res.json();
};

export const createUser = async (payload) => {
  const res = await apiFetch(`${BASE_URL}/users`, jsonRequest('POST', payload));
  if (!res.ok) throw new Error(await failureMessage(res, 'Could not create the user'));
  return res.json();
};

export const updateUser = async (id, changes) => {
  const res = await apiFetch(`${BASE_URL}/users/${id}`, jsonRequest('PATCH', changes));
  if (!res.ok) throw new Error(await failureMessage(res, 'Could not update the user'));
  return res.json();
};

export const resetUserPassword = async (id, password) => {
  const res = await apiFetch(`${BASE_URL}/users/${id}/reset-password`, jsonRequest('POST', { password }));
  if (!res.ok) throw new Error(await failureMessage(res, 'Could not reset the password'));
};
