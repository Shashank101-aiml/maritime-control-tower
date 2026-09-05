import React from 'react';
import {
  Activity, Ship, Radio, ShieldAlert, Navigation, Anchor, Clock, Fuel,
  Cpu, ScrollText, Settings as SettingsIcon, Circle, FlaskConical
} from 'lucide-react';

const NAV_GROUPS = [
  {
    label: 'Operations',
    items: [
      { id: 'dashboard', label: 'Fleet Overview', icon: Activity },
      { id: 'tracking', label: 'Vessel Tracking', icon: Ship },
      { id: 'monitor', label: 'Event Monitor', icon: Radio },
    ],
  },
  {
    label: 'Analysis',
    items: [
      { id: 'risk', label: 'Risk Analysis', icon: ShieldAlert },
      { id: 'routes', label: 'Route Planning', icon: Navigation },
      { id: 'simulator', label: 'Scenario Simulator', icon: FlaskConical },
    ],
  },
  {
    label: 'Predictions',
    items: [
      { id: 'congestion', label: 'Congestion', icon: Anchor },
      { id: 'delay', label: 'Shipment Delay', icon: Clock },
      { id: 'fuel', label: 'Fuel & Cost', icon: Fuel },
    ],
  },
  {
    label: 'System',
    items: [
      { id: 'workflow', label: 'Agent Pipeline', icon: Cpu },
      { id: 'governance', label: 'Governance', icon: ScrollText },
      { id: 'settings', label: 'Settings', icon: SettingsIcon },
    ],
  },
];

export default function Sidebar({ activeTab, setActiveTab, backendOnline }) {
  return (
    <aside className="sidebar">
      <nav className="sidebar-nav">
        {NAV_GROUPS.map((group) => (
          <div className="nav-group" key={group.label}>
            <div className="nav-group-label">{group.label}</div>
            {group.items.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  className={`sidebar-btn ${isActive ? 'active' : ''}`}
                  onClick={() => setActiveTab(item.id)}
                  title={item.label}
                >
                  <span className="icon-wrap">
                    <Icon size={17} strokeWidth={2} />
                  </span>
                  <span className="btn-label">{item.label}</span>
                </button>
              );
            })}
          </div>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="conn-status">
          <Circle
            size={8}
            fill={backendOnline ? 'var(--success)' : 'var(--text-subtle)'}
            color={backendOnline ? 'var(--success)' : 'var(--text-subtle)'}
          />
          <span>{backendOnline ? 'Backend connected' : 'Backend offline'}</span>
        </div>
      </div>
    </aside>
  );
}
