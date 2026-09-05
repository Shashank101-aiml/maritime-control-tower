import React, { useState, useEffect } from 'react';
import MainLayout from './layouts/MainLayout';
import Landing from './pages/Landing';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import VesselTracking from './pages/VesselTracking';
import EventMonitor from './pages/EventMonitor';
import RiskAnalysis from './pages/RiskAnalysis';
import RouteRecommendations from './pages/RouteRecommendations';
import ScenarioSimulator from './pages/ScenarioSimulator';
import Settings from './pages/Settings';
import GovernanceDashboard from './pages/GovernanceDashboard';
import CongestionPredictor from './pages/CongestionPredictor';
import DelayPredictor from './pages/DelayPredictor';
import FuelEfficiencyPredictor from './pages/FuelEfficiencyPredictor';
import { fetchCurrentUser, logout } from './services/authService';
import { AUTH_EXPIRED_EVENT } from './services/apiClient';
import './index.css';

export default function App() {
  const [view, setView] = useState('landing');
  const [activeTab, setActiveTab] = useState('dashboard');
  const [user, setUser] = useState(null);
  const [checkingSession, setCheckingSession] = useState(true);

  // Revalidate any stored token on load — it may have expired since the
  // last visit, in which case the console must not render.
  useEffect(() => {
    let cancelled = false;
    fetchCurrentUser()
      .then((u) => { if (!cancelled) setUser(u); })
      .finally(() => { if (!cancelled) setCheckingSession(false); });
    return () => { cancelled = true; };
  }, []);

  // apiClient fires this when the API rejects the token mid-session.
  useEffect(() => {
    const handleExpiry = () => {
      setUser(null);
      setView('login');
    };
    window.addEventListener(AUTH_EXPIRED_EVENT, handleExpiry);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, handleExpiry);
  }, []);

  const handleSignOut = () => {
    logout();
    setUser(null);
    setView('landing');
  };

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return <Dashboard activeTab="dashboard" setActiveTab={setActiveTab} />;
      case 'workflow':
        return <Dashboard activeTab="workflow" setActiveTab={setActiveTab} />;
      case 'tracking':
        return <VesselTracking />;
      case 'monitor':
        return <EventMonitor />;
      case 'risk':
        return <RiskAnalysis setActiveTab={setActiveTab} />;
      case 'routes':
        return <RouteRecommendations setActiveTab={setActiveTab} />;
      case 'simulator':
        return <ScenarioSimulator />;
      case 'congestion':
        return <CongestionPredictor />;
      case 'delay':
        return <DelayPredictor />;
      case 'fuel':
        return <FuelEfficiencyPredictor />;
      case 'governance':
        return <GovernanceDashboard />;
      case 'settings':
        return <Settings />;
      default:
        return <Dashboard activeTab="dashboard" setActiveTab={setActiveTab} />;
    }
  };

  // Avoid flashing the landing page before we know whether the stored
  // token is still valid.
  if (checkingSession) return null;

  if (view === 'landing') {
    return <Landing onEnter={() => setView(user ? 'app' : 'login')} />;
  }

  if (!user) {
    return (
      <Login
        onSignedIn={(signedIn) => {
          setUser(signedIn);
          setView('app');
        }}
      />
    );
  }

  return (
    <MainLayout
      activeTab={activeTab}
      setActiveTab={setActiveTab}
      onExitToLanding={() => setView('landing')}
      user={user}
      onSignOut={handleSignOut}
    >
      {renderContent()}
    </MainLayout>
  );
}
