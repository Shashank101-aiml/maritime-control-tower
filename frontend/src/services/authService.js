import { API_BASE_URL as BASE_URL } from '../config';
const TOKEN_KEY = 'mc_access_token';

/** Wrapped in try/catch: localStorage throws in private-mode browsers
 *  and when site data is blocked, which would otherwise white-screen the app. */
export const getToken = () => {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
};

export const setToken = (token) => {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* session-only fallback: the in-memory token still works this page load */
  }
};

export const clearToken = () => {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* nothing to clean up */
  }
};

export const login = async (username, password) => {
  // The backend uses the OAuth2 password flow, which expects form
  // encoding rather than JSON.
  const body = new URLSearchParams({ username, password });

  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  });

  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail || 'Sign in failed');
  }

  const data = await res.json();
  setToken(data.access_token);
  return data.user;
};

export const fetchCurrentUser = async () => {
  const token = getToken();
  if (!token) return null;

  const res = await fetch(`${BASE_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    clearToken();
    return null;
  }
  return res.json();
};

export const logout = () => clearToken();
