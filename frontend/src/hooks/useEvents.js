import { useEventContext } from '../context/EventContext';

/**
 * Custom hook to access telemetry event streams, filtering, and active alerts
 */
export const useEvents = () => {
  const {
    events,
    eventHistory,
    rawHistory,
    loading,
    error,
    filterSeverity,
    freshness,
    setFilterSeverity,
    activeAlert,
    dismissAlert,
    refreshEvents
  } = useEventContext();

  const highSeverityCount = rawHistory.filter(e => e.severity === 'HIGH' || e.severity === 'CRITICAL').length;

  return {
    freshness,
    events,
    eventHistory,
    rawHistory,
    highSeverityCount,
    loading,
    error,
    filterSeverity,
    setFilterSeverity,
    activeAlert,
    dismissAlert,
    refreshEvents
  };
};

export default useEvents;
