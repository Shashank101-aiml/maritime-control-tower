import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { getEvents, getEventHistory } from '../services/eventService';

const EventContext = createContext(null);

export const EventProvider = ({ children }) => {
  const [events, setEvents] = useState([]);
  const [eventHistory, setEventHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filterSeverity, setFilterSeverity] = useState('ALL');
  const [activeAlert, setActiveAlert] = useState(null);

  const fetchAllEvents = useCallback(async () => {
    setLoading(true);
    setError(null);
    // allSettled, not all: these are independent endpoints, and with
    // Promise.all a failure in one discarded the other's successful
    // result — a single flaky call blanked the whole page.
    const [latestResult, historyResult] = await Promise.allSettled([
      getEvents(),
      getEventHistory(),
    ]);

    if (latestResult.status === 'fulfilled') {
      setEvents(latestResult.value);
    }

    if (historyResult.status === 'fulfilled') {
      setEventHistory(historyResult.value);
      const severe = historyResult.value.find(
        (e) => e.severity === 'HIGH' || e.severity === 'CRITICAL'
      );
      if (severe) setActiveAlert(severe);
    }

    const failures = [latestResult, historyResult]
      .filter((r) => r.status === 'rejected')
      .map((r) => r.reason?.message)
      .filter(Boolean);

    setError(failures.length ? failures[0] : null);
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchAllEvents();
    const interval = setInterval(fetchAllEvents, 15000); // 15-second telemetry loop
    return () => clearInterval(interval);
  }, [fetchAllEvents]);

  const dismissAlert = () => setActiveAlert(null);

  const filteredHistory = eventHistory.filter(evt => {
    if (filterSeverity === 'ALL') return true;
    return evt.severity === filterSeverity;
  });

  return (
    <EventContext.Provider
      value={{
        events,
        eventHistory: filteredHistory,
        rawHistory: eventHistory,
        loading,
        error,
        filterSeverity,
        setFilterSeverity,
        activeAlert,
        dismissAlert,
        refreshEvents: fetchAllEvents
      }}
    >
      {children}
    </EventContext.Provider>
  );
};

export const useEventContext = () => {
  const context = useContext(EventContext);
  if (!context) {
    throw new Error('useEventContext must be used within an EventProvider');
  }
  return context;
};
