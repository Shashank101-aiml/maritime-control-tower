import React, { useState, useEffect } from 'react';
import Navbar from '../components/Navbar';
import Sidebar from '../components/Sidebar';
import AlertBanner from '../components/AlertBanner';
import { EventProvider, useEventContext } from '../context/EventContext';
import { RiskProvider } from '../context/RiskContext';

const HEALTH_URL = 'http://localhost:8000/health';

/** Polls the backend so the shell reports real connectivity rather than a
 *  hardcoded "OPERATIONAL" label. */
const useBackendHealth = () => {
  const [online, setOnline] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const check = async () => {
      try {
        const res = await fetch(HEALTH_URL);
        if (!cancelled) setOnline(res.ok);
      } catch {
        if (!cancelled) setOnline(false);
      }
    };

    check();
    const interval = setInterval(check, 15000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return online;
};

const MainContentWrapper = ({ activeTab, setActiveTab, onExitToLanding, user, onSignOut, children }) => {
  const { activeAlert, dismissAlert } = useEventContext();
  const backendOnline = useBackendHealth();

  return (
    <div className="app-container">
      <Navbar
          backendOnline={backendOnline}
          onBrandClick={onExitToLanding}
          user={user}
          onSignOut={onSignOut}
        />
      <div className="layout-body">
        <Sidebar
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          backendOnline={backendOnline}
        />
        <main className="main-content">
          <AlertBanner
            alert={activeAlert}
            onDismiss={dismissAlert}
            onAction={() => setActiveTab('routes')}
          />
          {children}
        </main>
      </div>
    </div>
  );
};

export default function MainLayout({ activeTab, setActiveTab, onExitToLanding, user, onSignOut, children }) {
  return (
    <EventProvider>
      <RiskProvider>
        <MainContentWrapper
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          onExitToLanding={onExitToLanding}
          user={user}
          onSignOut={onSignOut}
        >
          {children}
        </MainContentWrapper>
      </RiskProvider>
    </EventProvider>
  );
}
