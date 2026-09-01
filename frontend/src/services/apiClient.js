import { getToken, clearToken } from './authService';

/** Broadcast when the API rejects our token, so the app can drop back to
 *  the sign-in screen instead of silently rendering empty panels. */
export const AUTH_EXPIRED_EVENT = 'mc:auth-expired';

/**
 * fetch() with the bearer token attached and 401 handled once, centrally.
 * Every authenticated call goes through here so a new endpoint cannot
 * forget the header.
 */
export const apiFetch = async (url, options = {}) => {
  const token = getToken();
  const headers = { ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(url, { ...options, headers });

  if (res.status === 401) {
    clearToken();
    window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT));
    throw new Error('Your session has expired. Please sign in again.');
  }

  if (res.status === 429) {
    throw new Error('Too many requests — please wait a moment and try again.');
  }

  return res;
};
