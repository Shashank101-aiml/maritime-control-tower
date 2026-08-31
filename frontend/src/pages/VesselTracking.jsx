import React, { useEffect, useState } from 'react';
import { Ship, Search, AlertTriangle, RefreshCw, Radio, Waves, Navigation } from 'lucide-react';
import { getVessels } from '../services/vesselService';
import VesselMap from '../components/VesselMap';

const BASE_URL = 'http://localhost:8000/api';

const TONES = {
  CRITICAL: 'var(--danger)',
  HIGH: 'var(--danger)',
  WARNING: 'var(--warning)',
  LOW: 'var(--info)',
  INFO: 'var(--success)',
};

export default function VesselTracking() {
  const [searchTerm, setSearchTerm] = useState('');
  const [conditions, setConditions] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [ais, setAis] = useState(null);
  const [focusedCorridor, setFocusedCorridor] = useState(null);

  /** Wrapped in a fresh object each time so re-clicking the same corridor
   *  still re-centres the map after the user has panned away. */
  const focusCorridor = (corridor) =>
    setFocusedCorridor({ location: corridor.location, at: Date.now() });

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${BASE_URL}/conditions`);
      if (!res.ok) throw new Error(`Request failed (${res.status})`);
      const data = await res.json();
      if (data.source !== 'live') throw new Error(data.error || 'Live feed unavailable.');
      setConditions(data.conditions || []);
    } catch (err) {
      setError(err.message);
      setConditions([]);
    } finally {
      setLoading(false);
    }
  };

  const loadVessels = async () => {
    try {
      setAis(await getVessels());
    } catch {
      setAis(null);
    }
  };

  useEffect(() => {
    load();
    loadVessels();
    const conditionsTimer = setInterval(load, 60000);
    // Vessel positions move far faster than sea state, so poll harder.
    const vesselTimer = setInterval(loadVessels, 15000);
    return () => {
      clearInterval(conditionsTimer);
      clearInterval(vesselTimer);
    };
  }, []);

  const filtered = conditions.filter((c) =>
    `${c.location} ${c.event_type}`.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="page-wrapper">
      <div className="section-header" style={{ marginBottom: '24px' }}>
        <div>
          <h1 className="page-title">
            <Ship size={24} color="var(--primary)" />
            Corridor Tracking
          </h1>
          <p className="page-subtitle">
            Live sea state at the maritime chokepoints and corridors under monitoring.
          </p>
        </div>

        <div style={{ position: 'relative', width: '300px' }}>
          <Search size={16} color="var(--text-subtle)" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
          <input
            className="form-input"
            type="text"
            placeholder="Search corridors…"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{ paddingLeft: '36px' }}
          />
        </div>
      </div>

      {error ? (
        <div className="panel" style={{ textAlign: 'center', padding: '40px', borderColor: 'var(--warning-border)' }}>
          <AlertTriangle size={28} color="var(--warning)" style={{ margin: '0 auto 12px' }} />
          <h3 style={{ fontSize: '1rem', marginBottom: '6px' }}>Live feed unavailable</h3>
          <p style={{ color: 'var(--text-subtle)', marginBottom: '18px' }}>{error}</p>
          <button className="btn-action" onClick={load} style={{ margin: '0 auto' }}>
            <RefreshCw size={15} /> Retry
          </button>
        </div>
      ) : (
        <div className="content-grid" style={{ gridTemplateColumns: '1.4fr 1fr' }}>
          <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: '480px' }}>
            <div className="section-header">
              <h3 className="section-title">
                <Waves size={17} color="var(--info)" />
                Monitored corridor positions
              </h3>
              {loading && <RefreshCw size={15} className="spin" color="var(--text-subtle)" />}
            </div>
            <VesselMap
              corridors={filtered}
              vessels={ais?.vessels || []}
              height={560}
              focusedCorridor={focusedCorridor}
              onCorridorSelect={focusCorridor}
            />

            <p className="form-note">
              Circles are monitored corridors, coloured by sea state; arrows are live AIS vessels
              pointing along their course. Click any marker for detail, or enable the nautical
              chart overlay via the layers control. Basemap &copy; OpenStreetMap contributors;
              nautical overlay &copy; OpenSeaMap.
            </p>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div className="panel">
              <div className="section-header">
                <h3 className="section-title">
                  <Waves size={17} color="var(--info)" />
                  Corridor status ({filtered.length})
                </h3>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {filtered.length === 0 && !loading ? (
                  <p style={{ color: 'var(--text-subtle)' }}>No corridors match that search.</p>
                ) : filtered.map((c) => {
                  const color = TONES[String(c.severity || '').toUpperCase()] || 'var(--success)';
                  const m = c.conditions || {};
                  const isFocused = focusedCorridor?.location === c.location;
                  return (
                    <button
                      key={c.location}
                      type="button"
                      className={`agent-item corridor-row ${isFocused ? 'focused' : ''}`}
                      onClick={() => focusCorridor(c)}
                      title={`Show ${c.location} on the map`}
                    >
                      <div className="agent-info">
                        <div className="agent-avatar" style={{ background: 'var(--surface-sunken)', color }}>
                          <Waves size={15} />
                        </div>
                        <div style={{ textAlign: 'left' }}>
                          <div className="agent-name">{c.location}</div>
                          <div className="agent-role">
                            {m.wave_height_m ?? '—'} m wave · gust {m.wind_gusts_kmh ?? '—'} km/h
                          </div>
                        </div>
                      </div>
                      <span className="status-badge" style={{
                        background: 'transparent', borderColor: color, color, fontSize: '0.68rem',
                      }}>
                        {String(c.severity || '').toUpperCase()}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Real feed state — never invented vessels. */}
            <div className="panel">
              <div className="section-header">
                <h3 className="section-title">
                  <Radio
                    size={17}
                    color={ais?.connected ? 'var(--success)' : 'var(--text-subtle)'}
                  />
                  Live AIS vessels{ais?.count ? ` (${ais.count})` : ''}
                </h3>
                {ais?.configured && (
                  <span
                    className="status-badge"
                    style={
                      ais.connected
                        ? undefined
                        : {
                            background: 'var(--warning-soft)',
                            borderColor: 'var(--warning-border)',
                            color: 'var(--warning)',
                          }
                    }
                  >
                    <span className="pulse-dot" />
                    {ais.connected ? 'Connected' : 'Connecting'}
                  </span>
                )}
              </div>

              {!ais?.configured ? (
                <p style={{ fontSize: '0.85rem', color: 'var(--text-subtle)', lineHeight: 1.6 }}>
                  No AIS API key configured, so individual vessel positions are not shown.
                  Add a free key from <strong>aisstream.io</strong> as{' '}
                  <code>AISSTREAM_API_KEY</code> in <code>backend/.env</code> and restart the
                  backend — live vessel tracks, speeds, and headings will appear here automatically.
                </p>
              ) : ais.vessels.length === 0 ? (
                <p style={{ fontSize: '0.85rem', color: 'var(--text-subtle)', lineHeight: 1.6 }}>
                  {ais.connected
                    ? 'Connected — waiting for vessels to report inside the monitored corridors.'
                    : `Connecting to AISStream…${ais.error ? ` (${ais.error})` : ''}`}
                </p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '320px', overflowY: 'auto' }}>
                  {ais.vessels.slice(0, 25).map((v) => (
                    <div key={v.mmsi} className="agent-item">
                      <div className="agent-info">
                        <div className="agent-avatar">
                          <Navigation
                            size={15}
                            style={{
                              transform: v.cog_degrees != null
                                ? `rotate(${v.cog_degrees}deg)`
                                : undefined,
                            }}
                          />
                        </div>
                        <div>
                          <div className="agent-name">{v.name || `MMSI ${v.mmsi}`}</div>
                          <div className="agent-role">
                            {v.ship_type || 'Unknown type'}
                            {v.sog_knots != null ? ` · ${v.sog_knots} kts` : ''}
                            {v.destination ? ` · → ${v.destination}` : ''}
                          </div>
                        </div>
                      </div>
                      {v.nav_status && (
                        <span style={{ fontSize: '0.7rem', color: 'var(--text-subtle)', textAlign: 'right', maxWidth: '110px' }}>
                          {v.nav_status}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}

              <p className="form-note">
                Source: AISStream.io · positions expire after 30 min without a new report.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
