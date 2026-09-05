import React, { useEffect, useMemo, useRef } from 'react';
import { MapContainer, TileLayer, Polyline, CircleMarker, Marker, Popup, Tooltip, useMap } from 'react-leaflet';
import L from 'leaflet';
import { Map as MapIcon } from 'lucide-react';
import 'leaflet/dist/leaflet.css';
import { getSeverityTone } from '../types/Event';

const portIcon = (color, isEndpoint) =>
  L.divIcon({
    className: 'route-port-marker',
    iconSize: isEndpoint ? [14, 14] : [9, 9],
    iconAnchor: isEndpoint ? [7, 7] : [4.5, 4.5],
    html: `<div style="
      width:100%;height:100%;border-radius:${isEndpoint ? '4px' : '50%'};
      background:${color};border:2px solid rgba(10,20,30,0.9);
      box-shadow:0 0 6px rgba(0,0,0,0.5);
    "></div>`,
  });

/** Fits the map to whichever path is currently selected, so picking a
 *  different candidate re-frames the view instead of leaving the reader
 *  to pan and zoom to see it. */
function FitToPath({ points }) {
  const map = useMap();
  useEffect(() => {
    if (!points || points.length < 2) return;
    const bounds = L.latLngBounds(points.map((p) => [p.lat, p.lon]));
    map.flyToBounds(bounds.pad(0.3), { maxZoom: 5, duration: 0.7 });
  }, [points, map]);
  return null;
}

/**
 * Real geography for the current route optimization, not just a bar
 * list of numbers. Every point plotted is a real port (digital twin
 * node coordinates, backend/app/twin/coordinates.py) or a real
 * monitored corridor the lane actually crosses (backend/app/twin/
 * digital_twin.py's WAYPOINT_COORDINATES) -- nothing here is an
 * invented waypoint. Alternatives are drawn dimmed and are clickable,
 * so comparing candidates is a map interaction, not just reading rows
 * in a table below.
 */
export default function RouteMap({ candidates = [], selectedId, onSelect, height = 380 }) {
  const wrapperRef = useRef(null);

  const withPaths = candidates.filter((c) => c.points && c.points.length >= 2);
  const selected = withPaths.find((c) => c.id === selectedId) || withPaths[0];

  const allWaypointMarkers = useMemo(() => {
    if (!selected) return [];
    const seen = new Map();
    selected.points.forEach((p) => {
      if (!seen.has(p.name)) seen.set(p.name, p);
    });
    return [...seen.values()];
  }, [selected]);

  if (withPaths.length === 0) {
    return (
      <div className="panel" style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <p style={{ color: 'var(--text-subtle)', fontSize: '0.85rem' }}>No route geometry to plot yet.</p>
      </div>
    );
  }

  const center = selected.points[Math.floor(selected.points.length / 2)];

  return (
    <div className="panel" style={{ padding: 0, overflow: 'hidden' }}>
      <div className="section-header" style={{ padding: '16px 20px 0' }}>
        <h3 className="section-title" style={{ fontSize: '1.05rem' }}>
          <MapIcon size={17} color="var(--accent-teal)" />
          Route geometry
        </h3>
        <span style={{ fontSize: '0.72rem', color: 'var(--text-subtle)' }}>
          Click a lane on the map or a candidate below — they stay in sync
        </span>
      </div>

      <div ref={wrapperRef} style={{ height, marginTop: '10px' }}>
        <MapContainer
          center={[center.lat, center.lon]}
          zoom={3}
          minZoom={2}
          scrollWheelZoom
          worldCopyJump
          zoomControl={false}
          style={{ height: '100%', width: '100%', background: 'var(--surface-sunken)' }}
        >
          <TileLayer
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            maxZoom={19}
            className="basemap-dark"
          />

          <FitToPath points={selected.points} />

          {/* Every candidate's real path, dimmed unless selected -- a
              visual version of the ranked list below, clickable the
              same way. */}
          {withPaths.map((c) => {
            const isSelected = c.id === selected.id;
            const color = c.risk >= 60 ? '#fb7185' : c.risk >= 35 ? '#fbbf24' : '#34d399';
            return (
              <Polyline
                key={c.id}
                positions={c.points.map((p) => [p.lat, p.lon])}
                pathOptions={{
                  color: isSelected ? color : '#5b6b7a',
                  weight: isSelected ? 4 : 2,
                  opacity: isSelected ? 0.95 : 0.45,
                  dashArray: isSelected ? undefined : '4 6',
                }}
                eventHandlers={{ click: () => onSelect?.(c.id) }}
              >
                <Tooltip sticky>
                  {c.label} — {Math.round(c.distance_nm).toLocaleString()} nm, risk {c.risk}/100
                  {!isSelected && ' (click to select)'}
                </Tooltip>
              </Polyline>
            );
          })}

          {allWaypointMarkers.map((p) => {
            const isEndpoint = p.type === 'port' && (p.name === selected.origin || p.name === selected.destination);
            const color = p.type === 'port'
              ? (isEndpoint ? '#22d3ee' : '#94a3b8')
              : getSeverityTone(p.severity).fg;
            return (
              <Marker key={p.name} position={[p.lat, p.lon]} icon={portIcon(color, isEndpoint)}>
                <Tooltip direction="top" offset={[0, -6]}>{p.name}</Tooltip>
                <Popup>
                  <strong>{p.name}</strong>
                  <br />
                  {p.type === 'port'
                    ? (isEndpoint ? (p.name === selected.origin ? 'Origin' : 'Destination') : 'Intermediate port')
                    : `Monitored corridor${p.severity ? ` — ${p.severity}` : ''}`}
                </Popup>
              </Marker>
            );
          })}
        </MapContainer>
      </div>

      <p className="form-note" style={{ padding: '0 20px 16px', marginTop: '10px' }}>
        Solid line is the selected candidate; dashed lines are the other ranked alternatives — click
        either the map or a candidate card to compare. Square markers are the origin/destination,
        small circles are intermediate ports and monitored corridors the lane actually crosses.
      </p>
    </div>
  );
}
