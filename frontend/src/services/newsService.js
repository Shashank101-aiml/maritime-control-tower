import { apiFetch } from './apiClient';
import { API_BASE_URL as BASE_URL } from '../config';

/**
 * Recent maritime news, newest first, each article tagged with the
 * monitored corridors it mentions and a category by the Event
 * Understanding Agent. Served from the backend's cached batch, so polling
 * this is cheap. Pass a corridor name to narrow to that corridor.
 */
export const getNews = async (corridor) => {
  const query = corridor ? `?corridor=${encodeURIComponent(corridor)}` : '';
  const res = await apiFetch(`${BASE_URL}/news${query}`);
  if (!res.ok) throw new Error(`News request failed (${res.status})`);
  return res.json();
};
