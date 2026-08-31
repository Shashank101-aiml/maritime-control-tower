import React from 'react';
import { Navigation, ShieldCheck, RefreshCw, AlertCircle, CheckCircle2, MapPin } from 'lucide-react';
import { useRecommendations } from '../hooks/useRecommendations';
import RouteCard from '../components/RouteCard';
import RouteComparisonChart from '../components/Charts/RouteComparisonChart';
import DelayChart from '../components/Charts/DelayChart';
import LoadingSpinner from '../components/LoadingSpinner';

export default function RouteRecommendations() {
  const { 
    primary, 
    corridors, 
    adoptedCorridor, 
    adoptRoute, 
    loading, 
    error, 
    refreshRecommendations 
  } = useRecommendations();

  return (
    <div className="page-wrapper">
      <div className="section-header" style={{ marginBottom: '24px' }}>
        <div>
          <h1 className="section-title" style={{ fontSize: '1.8rem', color: 'var(--text-strong)' }}>
            <Navigation size={28} color="var(--accent-teal)" />
            AI Route Optimization & Waypoints
          </h1>
          <p style={{ color: 'var(--text-muted)', marginTop: '4px' }}>
            Dynamic waypoint calculation by the Route Optimization Agent to circumvent severe storms and security zones.
          </p>
        </div>

        <button className="btn-action" onClick={refreshRecommendations}>
          <RefreshCw size={16} className={loading ? 'spin' : ''} />
          Re-Optimize Corridors
        </button>
      </div>

      {loading && corridors.length === 0 ? (
        <LoadingSpinner message="Simulating oceanic hydrodynamic models and corridor waypoints..." />
      ) : error ? (
        <div className="glass-panel" style={{ textAlign: 'center', padding: '40px', borderColor: 'var(--accent-rose)' }}>
          <AlertCircle size={36} color="var(--accent-rose)" style={{ margin: '0 auto 12px' }} />
          <p style={{ color: 'var(--text-main)' }}>{error}</p>
        </div>
      ) : (
        <>
          {/* Primary AI Recommendation Banner */}
          {primary && (
            <div className="workflow-box" style={{ marginBottom: '28px', background: 'var(--info-soft)', border: '1px solid var(--accent-cyan)' }}>
              <div className="workflow-header" style={{ fontSize: '1.15rem' }}>
                <CheckCircle2 size={22} color="var(--accent-emerald)" />
                Primary AI Routing Synthesis (Explanation Agent)
              </div>
              <p style={{ fontSize: '1.05rem', color: 'var(--text-strong)', margin: '10px 0', lineHeight: 1.5 }}>
                {primary.primary_recommendation}
              </p>
              <div style={{ display: 'flex', gap: '20px', marginTop: '14px', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                <span>Analysis Timestamp: <strong style={{ color: 'var(--text-strong)' }}>{primary.timestamp}</strong></span>
                <span>Assessed Corridor Risk: <strong style={{ color: primary.assessed_risk > 50 ? 'var(--accent-rose)' : 'var(--accent-emerald)' }}>{primary.assessed_risk}/100</strong></span>
              </div>
            </div>
          )}

          {/* Charts Row: Route Comparison + Delays */}
          <div className="content-grid" style={{ gridTemplateColumns: '1fr 1fr', marginBottom: '28px' }}>
            <RouteComparisonChart />
            <DelayChart />
          </div>

          {/* Corridor Selection List */}
          <div className="glass-panel" style={{ padding: '24px' }}>
            <div className="section-header" style={{ marginBottom: '20px' }}>
              <h3 className="section-title" style={{ fontSize: '1.2rem' }}>
                <MapPin size={22} color="var(--accent-amber)" />
                Available Maritime Shipping Corridors ({corridors.length})
              </h3>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                Click a corridor below to select or adopt as active fleet waypoint path
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {corridors.length === 0 ? (
                <div style={{
                  textAlign: 'center',
                  padding: '36px 20px',
                  border: '1px dashed var(--border-strong)',
                  borderRadius: 'var(--radius)',
                  background: 'var(--surface-subtle)'
                }}>
                  <p style={{ color: 'var(--text-subtle)', fontSize: '0.875rem' }}>
                    No scored corridor alternatives available.
                  </p>
                  <p style={{ color: 'var(--text-subtle)', fontSize: '0.8rem', marginTop: '6px' }}>
                    The Route Agent currently returns a single recommended route (shown above)
                    rather than a ranked set of alternatives.
                  </p>
                </div>
              ) : corridors.map((c) => (
                <RouteCard
                  key={c.id}
                  corridor={c}
                  isSelected={adoptedCorridor === c.id}
                  onSelect={adoptRoute}
                />
              ))}
            </div>

            {adoptedCorridor && (
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'space-between', 
                background: 'var(--success-soft)', 
                border: '1px solid var(--accent-emerald)', 
                padding: '16px 20px', 
                borderRadius: '12px',
                marginTop: '24px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', color: 'var(--accent-emerald)', fontWeight: 700 }}>
                  <ShieldCheck size={24} />
                  <div>
                    <div style={{ fontSize: '1.05rem' }}>Active Fleet Waypoint Protocol: {adoptedCorridor}</div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 400, marginTop: '2px' }}>
                      All vessels in affected sectors are automatically synchronized with this corridor vector.
                    </div>
                  </div>
                </div>

                <button 
                  className="btn-action" 
                  style={{ background: 'var(--accent-emerald)', color: '#ffffff', padding: '10px 20px' }}
                  onClick={() => alert(`Corridor ${adoptedCorridor} successfully locked as primary fleet navigational route!`)}
                >
                  <CheckCircle2 size={16} /> Lock Route Protocol
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
