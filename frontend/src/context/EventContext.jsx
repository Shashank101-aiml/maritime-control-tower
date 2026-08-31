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
    try {
      const [latestEvents, history] = await Promise.all([
        getEvents(),
        getEventHistory()
      ]);
      setEvents(latestEvents);
      setEventHistory(history);

      // Check for high severity alert
      const highSev = history.find(e => e.severity === 'HIGH' || e.severity === 'CRITICAL');
      if (highSev) {
        setActiveAlert(highSev);
      }
    } catch (err) {
      setError('Failed to synchronize telemetry stream.');
    } finally {
      setLoading(false);
    }
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
