import { useEffect, useState } from 'react';
import { getConditionsHistory } from '../services/eventService';

const POLL_MS = 2 * 60 * 1000;

/** Recorded sea-state history per corridor, refreshed as new readings land.
 *  Returns null until the first response, then a map (empty if nothing is
 *  recorded). */
export const useSeaStateHistory = (hours = 24) => {
  const [corridors, setCorridors] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const data = await getConditionsHistory(hours);
        if (!cancelled) setCorridors(data.corridors || {});
      } catch {
        // History is an enhancement; the live reading still renders without it.
        if (!cancelled) setCorridors((prev) => prev ?? {});
      }
    };
    load();
    const timer = setInterval(load, POLL_MS);
    return () => { cancelled = true; clearInterval(timer); };
  }, [hours]);

  return corridors;
};

export default useSeaStateHistory;
