import React, { useState } from 'react';
import MainLayout from './layouts/MainLayout';
import Landing from './pages/Landing';
import Dashboard from './pages/Dashboard';
import VesselTracking from './pages/VesselTracking';
import EventMonitor from './pages/EventMonitor';
import RiskAnalysis from './pages/RiskAnalysis';
import RouteRecommendations from './pages/RouteRecommendations';
import Settings from './pages/Settings';
import GovernanceDashboard from './pages/GovernanceDashboard';
import CongestionPredictor from './pages/CongestionPredictor';
import DelayPredictor from './pages/DelayPredictor';
import FuelEfficiencyPredictor from './pages/FuelEfficiencyPredictor';
import './index.css';

export default function App() {
  const [view, setView] = useState('landing');
  const [activeTab, setActiveTab] = useState('dashboard');

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
        return <RiskAnalysis />;
      case 'routes':
        return <RouteRecommendations />;
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

  if (view === 'landing') {
    return <Landing onEnter={() => setView('app')} />;
  }

  return (
    <MainLayout
      activeTab={activeTab}
      setActiveTab={setActiveTab}
      onExitToLanding={() => setView('landing')}
    >
      {renderContent()}
    </MainLayout>
  );
}
