/**
 * Single source of truth for the backend origin.
 *
 * Falls back to localhost:8000 so `npm run dev` keeps working with no
 * .env file. A real deployment (anywhere the frontend isn't served from
 * the same host as the API) must set VITE_API_BASE_URL — see .env.example.
 */
const API_ORIGIN = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const API_BASE_URL = `${API_ORIGIN}/api`;
export const HEALTH_URL = `${API_ORIGIN}/health`;
