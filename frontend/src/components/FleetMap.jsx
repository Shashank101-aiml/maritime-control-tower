import React, { useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, Polyline, Marker, Tooltip, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

export const RISK_COLORS = { low: '#34d399', medium: '#fbbf24', high: '#fb7185', unknown: '#8fabbb' };

const riskColor = (vessel) => RISK_COLORS[vessel.risk?.level] || RISK_COLORS.unknown;

const laneColor = (risk) => (risk >= 60 ? '#fb7185' : risk >= 35 ? '#fbbf24' : '#3f8f78');

const vesselIcon = (vessel, selected) => {
  const color = riskColor(vessel);
  const moving = (vessel.position?.sog_knots ?? 0) > 0.5;
  const size = selected ? 18 : 13;
  const ring = selected ? `box-shadow:0 0 0 3px rgba(255,255,255,0.85), 0 0 10px ${color};` : 'filter:drop-shadow(0 0 2px rgba(0,0,0,0.9));';
  const stale = vessel.position && !vessel.position.live ? 'opacity:0.55;' : '';
  return L.divIcon({
    className: 'fleet-vessel-marker',
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    html: moving
      ? `<div style="width:0;height:0;border-left:${size / 2.4}px solid transparent;border-right:${size / 2.4}px solid transparent;border-bottom:${size}px solid ${color};transform:rotate(${vessel.position.cog_degrees ?? 0}deg);transform-origin:50% 65%;${selected ? `filter:drop-shadow(0 0 4px ${color});` : 'filter:drop-shadow(0 0 2px rgba(0,0,0,0.9));'}${stale}"></div>`
      : `<div style="width:${size * 0.7}px;height:${size * 0.7}px;margin:${size * 0.15}px;border-radius:50%;background:${color};border:2px solid rgba(10,20,30,0.9);${ring}${stale}"></div>`,
  });
};

/** Frames the whole fleet at first, then flies to a vessel when one is picked. */
function Framing({ vessels, selected }) {
  const map = useMap();
  const positioned = useMemo(
    () => vessels.filter((v) => v.position).map((v) => [v.position.latitude, v.position.longitude]),
    [vessels],
  );
  const selectedKey = selected?.position ? `${selected.id}` : null;

  useEffect(() => {
    if (selected?.position) {
      map.flyTo([selected.position.latitude, selected.position.longitude], Math.max(map.getZoom(), 5), { duration: 0.7 });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedKey]);

  const positionedCount = positioned.length;
  useEffect(() => {
    if (positioned.length === 0) return;
    if (positioned.length === 1) map.setView(positioned[0], 5);
    else map.fitBounds(L.latLngBounds(positioned).pad(0.3), { maxZoom: 6 });
    // Re-frame when a vessel gets its first position or is removed -- not
    // on every refresh, which would fight the user panning the map.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [positionedCount]);

  return null;
}

/**
 * The fleet on the digital twin: the real shipping lanes (coloured by their
 * live risk) with each registered vessel where AIS last placed it. Vessels
 * with no position yet simply aren't drawn -- nothing is guessed.
 */
export default function FleetMap({ lanes = [], vessels = [], selectedId, onSelect, trail = [], height = 460 }) {
  const selected = vessels.find((v) => v.id === selectedId) || null;

  return (
    <div className="panel" style={{ padding: 0, overflow: 'hidden' }}>
      <div style={{ height }}>
        <MapContainer
          center={[25, 40]}
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
          <Framing vessels={vessels} selected={selected} />

          {lanes.map((lane) => (
            <Polyline
              key={lane.id}
              positions={lane.points}
              pathOptions={{
                color: laneColor(lane.risk),
                weight: selected?.twin?.lane_id === lane.id ? 4 : 1.6,
                opacity: selected?.twin?.lane_id === lane.id ? 0.95 : 0.4,
              }}
            >
              <Tooltip sticky>{lane.id} · risk {lane.risk ?? '—'}/100</Tooltip>
            </Polyline>
          ))}

          {trail.length > 1 && (
            <Polyline positions={trail.map((p) => [p[0], p[1]])} pathOptions={{ color: '#ffffff', weight: 2, opacity: 0.8, dashArray: '4 5' }} />
          )}

          {vessels.filter((v) => v.position).map((v) => (
            <Marker
              key={v.id}
              position={[v.position.latitude, v.position.longitude]}
              icon={vesselIcon(v, v.id === selectedId)}
              eventHandlers={{ click: () => onSelect(v.id) }}
              zIndexOffset={v.id === selectedId ? 1000 : 0}
            >
              <Tooltip direction="top" offset={[0, -8]}>
                <strong>{v.name}</strong>
                <br />
                {v.position.sog_knots != null ? `${v.position.sog_knots.toFixed(1)} kn` : 'speed n/a'}
                {v.position.live ? '' : ' · last known'}
              </Tooltip>
            </Marker>
          ))}
        </MapContainer>
      </div>
      <p className="form-note" style={{ padding: '10px 16px 14px', margin: 0 }}>
        Lines are the digital twin's shipping lanes, coloured by live risk. Markers are your vessels where AIS last
        placed them, coloured by sea-state risk at their position; faded means the last report is old.
      </p>
    </div>
  );
}
