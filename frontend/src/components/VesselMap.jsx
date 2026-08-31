import React, { useMemo, useRef, useState } from 'react';
import { MapContainer, TileLayer, CircleMarker, Marker, Popup, Tooltip, useMap } from 'react-leaflet';
import L from 'leaflet';
import { Layers, Maximize2, Minimize2, Crosshair, Anchor, Ship } from 'lucide-react';
import 'leaflet/dist/leaflet.css';

/**
 * Interactive operations map.
 *
 * All tile layers are key-free:
 *   - OpenStreetMap standard tiles (dark look applied via CSS filter)
 *   - OpenSeaMap seamark overlay (buoys, lights, shipping lanes)
 * Attribution is required by those licences and is rendered by Leaflet.
 */

const SEVERITY_COLORS = {
  CRITICAL: '#ff7b7b',
  HIGH: '#ff7b7b',
  WARNING: '#ffc046',
  LOW: '#57c9ee',
  INFO: '#62d84e',
};

/** Vessel classes shown as filter toggles, each with its own colour. */
const VESSEL_CLASSES = [
  { id: 'Cargo', label: 'Cargo', color: '#62d84e' },
  { id: 'Tanker', label: 'Tanker', color: '#ffc046' },
  { id: 'Passenger', label: 'Passenger', color: '#57c9ee' },
  { id: 'Fishing', label: 'Fishing', color: '#c58cf5' },
  { id: 'Tug / Towing', label: 'Tug / Towing', color: '#ff9f6b' },
  { id: 'Other', label: 'Other / Unknown', color: '#8fabbb' },
];

const KNOWN_CLASS_IDS = new Set(VESSEL_CLASSES.map((c) => c.id));

/** Anything not in its own toggle bucket falls under "Other / Unknown". */
const classOf = (vessel) => {
  const t = vessel.ship_type;
  return t && KNOWN_CLASS_IDS.has(t) ? t : 'Other';
};

const vesselIcon = (cog, color, moving) =>
  L.divIcon({
    className: 'vessel-marker',
    iconSize: [12, 12],
    iconAnchor: [6, 6],
    html: moving
      ? `<div style="
          width:0;height:0;
          border-left:4px solid transparent;
          border-right:4px solid transparent;
          border-bottom:11px solid ${color};
          transform: rotate(${cog ?? 0}deg);
          transform-origin: 50% 65%;
          filter: drop-shadow(0 0 2px rgba(0,0,0,0.9));
        "></div>`
      : `<div style="
          width:7px;height:7px;border-radius:50%;
          background:${color};opacity:0.75;
          border:1px solid rgba(0,0,0,0.5);
        "></div>`,
  });

/** Exposes the Leaflet instance so toolbar buttons can drive the map. */
function MapControls({ onReady }) {
  const map = useMap();
  React.useEffect(() => onReady(map), [map, onReady]);
  return null;
}

export default function VesselMap({
  corridors = [],
  vessels = [],
  height = 460,
  focusedCorridor = null,
  onCorridorSelect,
}) {
  const wrapperRef = useRef(null);
  const mapRef = useRef(null);
  const corridorMarkerRefs = useRef({});
  const [showPanel, setShowPanel] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const [layers, setLayers] = useState({
    corridors: true,
    vessels: true,
    seamarks: false,
    movingOnly: false,
  });
  const [enabledClasses, setEnabledClasses] = useState(
    () => new Set(VESSEL_CLASSES.map((c) => c.id))
  );

  const toggleLayer = (key) =>
    setLayers((prev) => ({ ...prev, [key]: !prev[key] }));

  const toggleClass = (id) =>
    setEnabledClasses((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const positioned = useMemo(
    () => vessels.filter((v) => v.latitude != null && v.longitude != null),
    [vessels]
  );

  const classCounts = useMemo(() => {
    const counts = {};
    positioned.forEach((v) => {
      const c = classOf(v);
      counts[c] = (counts[c] || 0) + 1;
    });
    return counts;
  }, [positioned]);

  const visibleVessels = useMemo(() => {
    if (!layers.vessels) return [];
    return positioned.filter((v) => {
      if (!enabledClasses.has(classOf(v))) return false;
      if (layers.movingOnly && (v.sog_knots ?? 0) <= 0.5) return false;
      return true;
    });
  }, [positioned, enabledClasses, layers.vessels, layers.movingOnly]);

  const disrupted = corridors.filter((c) =>
    ['CRITICAL', 'HIGH', 'WARNING'].includes(String(c.severity || '').toUpperCase())
  ).length;

  const toggleFullscreen = () => {
    const el = wrapperRef.current;
    if (!document.fullscreenElement) {
      el?.requestFullscreen?.().then(() => {
        setIsFullscreen(true);
        setTimeout(() => mapRef.current?.invalidateSize(), 200);
      });
    } else {
      document.exitFullscreen?.().then(() => {
        setIsFullscreen(false);
        setTimeout(() => mapRef.current?.invalidateSize(), 200);
      });
    }
  };

  /** Fly to a corridor and open its popup when one is picked from the
   *  list beside the map. Runs whenever the selection changes, including
   *  re-selecting the same corridor after the user has panned away. */
  React.useEffect(() => {
    if (!focusedCorridor || !mapRef.current) return;
    const corridor = corridors.find((c) => c.location === focusedCorridor.location);
    if (!corridor) return;

    // Corridors are hidden if their layer is off — turn it back on so the
    // selection is actually visible rather than silently doing nothing.
    if (!layers.corridors) setLayers((prev) => ({ ...prev, corridors: true }));

    // Pad the fly-to so the marker (and its popup) land in clear space
    // rather than underneath the layers panel / status strip.
    const point = L.latLng(corridor.latitude, corridor.longitude);
    mapRef.current.flyToBounds(L.latLngBounds(point, point), {
      maxZoom: 6,
      paddingTopLeft: [showPanel ? 240 : 60, 80],
      paddingBottomRight: [40, 70],
      duration: 0.8,
    });

    const timer = setTimeout(() => {
      corridorMarkerRefs.current[corridor.location]?.openPopup();
    }, 900);
    return () => clearTimeout(timer);
    // focusedCorridor is a fresh object per click, so re-selecting re-runs this.
  }, [focusedCorridor, corridors, layers.corridors, showPanel]);

  const fitAll = () => {
    const pts = [
      ...corridors.map((c) => [c.latitude, c.longitude]),
      ...visibleVessels.map((v) => [v.latitude, v.longitude]),
    ].filter(([a, b]) => a != null && b != null);
    if (pts.length && mapRef.current) {
      mapRef.current.fitBounds(L.latLngBounds(pts).pad(0.15));
    }
  };

  return (
    <div ref={wrapperRef} className="ops-map" style={{ height: isFullscreen ? '100vh' : height }}>
      {/* Status strip */}
      <div className="ops-map-status">
        <span className="ops-live">
          <span className="ops-live-dot" /> LIVE
        </span>
        <span><Anchor size={11} /> {disrupted}/{corridors.length} corridors disrupted</span>
        <span><Ship size={11} /> {visibleVessels.length} of {positioned.length} vessels</span>
      </div>

      {/* Toolbar */}
      <div className="ops-map-toolbar">
        <button
          className={`ops-map-btn ${showPanel ? 'active' : ''}`}
          onClick={() => setShowPanel((s) => !s)}
          title="Toggle layers"
        >
          <Layers size={14} />
        </button>
        <button className="ops-map-btn" onClick={fitAll} title="Fit to contacts">
          <Crosshair size={14} />
        </button>
        <button className="ops-map-btn" onClick={toggleFullscreen} title="Fullscreen">
          {isFullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
        </button>
      </div>

      {/* Layers panel */}
      {showPanel && (
        <div className="ops-panel">
          <div className="ops-panel-title">Layers</div>

          <label className="ops-check">
            <input type="checkbox" checked={layers.corridors} onChange={() => toggleLayer('corridors')} />
            <span>Corridors</span>
            <em>{corridors.length}</em>
          </label>
          <label className="ops-check">
            <input type="checkbox" checked={layers.vessels} onChange={() => toggleLayer('vessels')} />
            <span>AIS vessels</span>
            <em>{positioned.length}</em>
          </label>
          <label className="ops-check">
            <input type="checkbox" checked={layers.seamarks} onChange={() => toggleLayer('seamarks')} />
            <span>Nautical chart</span>
          </label>
          <label className="ops-check">
            <input type="checkbox" checked={layers.movingOnly} onChange={() => toggleLayer('movingOnly')} />
            <span>Under way only</span>
          </label>

          <div className="ops-panel-title" style={{ marginTop: '12px' }}>Vessel class</div>
          {VESSEL_CLASSES.map((c) => (
            <label className="ops-check" key={c.id}>
              <input
                type="checkbox"
                checked={enabledClasses.has(c.id)}
                onChange={() => toggleClass(c.id)}
                disabled={!layers.vessels}
              />
              <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <i className="ops-swatch" style={{ background: c.color }} />
                {c.label}
              </span>
              <em>{classCounts[c.id] || 0}</em>
            </label>
          ))}
        </div>
      )}

      {/* Legend */}
      <div className="ops-legend">
        {Object.entries({ Critical: SEVERITY_COLORS.CRITICAL, Warning: SEVERITY_COLORS.WARNING, Low: SEVERITY_COLORS.LOW, Calm: SEVERITY_COLORS.INFO })
          .map(([label, color]) => (
            <span key={label}><i style={{ background: color }} />{label}</span>
          ))}
        <span style={{ opacity: 0.55 }}>▲ under way · ● stopped</span>
      </div>

      <MapContainer
        center={corridors.length ? [corridors[0].latitude, corridors[0].longitude] : [20, 40]}
        zoom={3}
        minZoom={2}
        scrollWheelZoom
        worldCopyJump
        zoomControl={false}
        style={{ height: '100%', width: '100%', background: 'var(--surface-sunken)' }}
      >
        <MapControls onReady={(m) => { mapRef.current = m; }} />

        <TileLayer
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          maxZoom={19}
          className="basemap-dark"
        />

        {layers.seamarks && (
          <TileLayer
            url="https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://www.openseamap.org/">OpenSeaMap</a>'
            maxZoom={18}
            opacity={0.9}
          />
        )}

        {layers.corridors && corridors.map((c) => {
          const key = String(c.severity || '').toUpperCase();
          const color = SEVERITY_COLORS[key] || SEVERITY_COLORS.INFO;
          const m = c.conditions || {};
          const isFocused = focusedCorridor?.location === c.location;
          return (
            <CircleMarker
              key={c.location}
              center={[c.latitude, c.longitude]}
              radius={isFocused ? 13 : 9}
              ref={(el) => { if (el) corridorMarkerRefs.current[c.location] = el; }}
              eventHandlers={{ click: () => onCorridorSelect?.(c) }}
              pathOptions={{
                color,
                fillColor: color,
                fillOpacity: isFocused ? 0.45 : 0.25,
                weight: isFocused ? 3 : 2,
              }}
            >
              <Tooltip direction="top" offset={[0, -8]}>{c.location}</Tooltip>
              {/* autoPan shifts the map so the whole popup clears the
                  layers panel — padding the fly-to alone only positions
                  the marker, not the popup that extends around it. */}
              <Popup
                autoPan
                autoPanPaddingTopLeft={[showPanel ? 250 : 70, 95]}
                autoPanPaddingBottomRight={[50, 80]}
              >
                <strong>{c.location}</strong>
                <br />
                {c.event_type} · <span style={{ color }}>{key}</span>
                <br />
                Wave {m.wave_height_m ?? '—'} m · Swell {m.swell_height_m ?? '—'} m
                <br />
                Wind {m.wind_speed_kmh ?? '—'} km/h, gusting {m.wind_gusts_kmh ?? '—'} km/h
              </Popup>
            </CircleMarker>
          );
        })}

        {visibleVessels.map((v) => {
          const cls = classOf(v);
          const color = (VESSEL_CLASSES.find((c) => c.id === cls) || {}).color || '#8fabbb';
          const moving = (v.sog_knots ?? 0) > 0.5;
          return (
            <Marker
              key={v.mmsi}
              position={[v.latitude, v.longitude]}
              icon={vesselIcon(v.cog_degrees, color, moving)}
            >
              <Popup>
                <strong>{v.name || `MMSI ${v.mmsi}`}</strong>
                <br />
                {v.ship_type || 'Unknown type'}{v.imo ? ` · IMO ${v.imo}` : ''}
                <br />
                {v.sog_knots != null ? `${v.sog_knots} kts` : 'Speed n/a'}
                {v.cog_degrees != null ? ` · COG ${v.cog_degrees}°` : ''}
                <br />
                {v.nav_status || 'Status n/a'}
                {v.destination ? <><br />Destination: {v.destination}</> : null}
                {v.length_m ? <><br />{v.length_m} m × {v.width_m ?? '—'} m</> : null}
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>
    </div>
  );
}
