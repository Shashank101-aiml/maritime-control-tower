import { useState, useEffect, useCallback } from 'react';
import { getCorridorOptions } from '../services/routeService';

/**
 * Custom hook for AI waypoint recommendations and corridor comparisons
 */
export const useRecommendations = () => {
  const [data, setData] = useState({ primary: null, corridors: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [adoptedCorridor, setAdoptedCorridor] = useState(null);

  const fetchCorridors = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getCorridorOptions();
      setData(res);
      if (!adoptedCorridor && res.corridors.length > 0) {
        const rec = res.corridors.find(c => c.recommended) || res.corridors[0];
        setAdoptedCorridor(rec.id);
      }
    } catch (err) {
      setError('Could not load corridor recommendations.');
    } finally {
      setLoading(false);
    }
  }, [adoptedCorridor]);

  useEffect(() => {
    fetchCorridors();
  }, [fetchCorridors]);

  const adoptRoute = (corridorId) => {
    setAdoptedCorridor(corridorId);
  };

  return {
    primary: data.primary,
    corridors: data.corridors,
    adoptedCorridor,
    adoptRoute,
    loading,
    error,
    refreshRecommendations: fetchCorridors
  };
};

export default useRecommendations;
