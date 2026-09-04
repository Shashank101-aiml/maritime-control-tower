import React, { createContext, useContext, useState } from 'react';

/**
 * Which monitored corridor the user is currently focused on, shared
 * across pages. Previously this lived as page-local state inside
 * VesselTracking.jsx (`focusedCorridor`) -- selecting a corridor there
 * moved the map, but Event Monitor, Risk Analysis, and Route Planning
 * had no way to know a selection had even happened. Lifted here, above
 * the tab switch in MainLayout.jsx, so it survives navigating between
 * tabs instead of resetting.
 */
const CorridorContext = createContext(null);

export const CorridorProvider = ({ children }) => {
  const [selectedCorridor, setSelectedCorridor] = useState(null); // { location, at }

  /** Wrapped in a fresh object each time so re-selecting the same
   *  corridor still re-triggers anything watching `at` (e.g. the map
   *  re-centring after the user has panned away). */
  const selectCorridor = (location) => {
    if (!location) return;
    setSelectedCorridor({ location, at: Date.now() });
  };

  const clearCorridor = () => setSelectedCorridor(null);

  return (
    <CorridorContext.Provider value={{ selectedCorridor, selectCorridor, clearCorridor }}>
      {children}
    </CorridorContext.Provider>
  );
};

export const useCorridorContext = () => {
  const context = useContext(CorridorContext);
  if (!context) {
    throw new Error('useCorridorContext must be used within a CorridorProvider');
  }
  return context;
};
