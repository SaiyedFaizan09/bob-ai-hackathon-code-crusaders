/**
 * components/MapView.jsx
 * -----------------------
 * Full-screen React-Leaflet ATC tactical display map.
 * Stadia Dark tiles · Omni-Zone circle · runway polygons ·
 * aircraft markers with trajectory lines · search flyTo controller.
 *
 * Alert popup badges REMOVED — alerts are shown exclusively in the
 * right-panel AlertsList. Aircraft icons retain P-E-R red highlighting.
 */

import { useEffect, useRef } from 'react';
import {
  MapContainer,
  TileLayer,
  Circle,
  Polygon,
  Polyline,
  Marker,
  Popup,
  useMap,
} from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// ---------------------------------------------------------------------------
// Map re-centering on airport switch
// ---------------------------------------------------------------------------
function MapRecenter({ center, zoom }) {
  const map = useMap();
  useEffect(() => {
    if (center) map.setView(center, zoom, { animate: true });
  }, [center[0], center[1]]);
  return null;
}

// ---------------------------------------------------------------------------
// Search flyTo controller — smoothly pans the camera to a found aircraft
// ---------------------------------------------------------------------------
function SearchFlyTo({ aircraft, searchQuery }) {
  const map = useMap();

  useEffect(() => {
    if (!searchQuery || !aircraft?.length) return;
    const q = searchQuery.trim().toUpperCase();
    const found = aircraft.find(
      ac => ac.callsign?.toUpperCase().includes(q) || ac.icao24?.toUpperCase() === q
    );
    if (found?.lat && found?.lon) {
      map.flyTo([found.lat, found.lon], 13, { animate: true, duration: 1.2 });
    }
  }, [searchQuery]);   // re-run only when searchQuery changes

  return null;
}

// ---------------------------------------------------------------------------
// Aircraft SVG icon factory
// ---------------------------------------------------------------------------
function createAircraftIcon(track, status, onGround, isSearchMatch) {
  const isAlert = status === 'COLLISION' || status === 'INCURSION';
  const color = isAlert
    ? '#ff2244'
    : isSearchMatch
      ? '#ffe566'      // vivid amber-yellow for searched aircraft
      : onGround
        ? '#ffbb00'
        : '#00d4ff';

  const glow = isAlert
    ? 'drop-shadow(0 0 6px #ff2244) drop-shadow(0 0 12px #ff2244)'
    : isSearchMatch
      ? 'drop-shadow(0 0 8px #ffe566) drop-shadow(0 0 16px #ffe566)'
      : onGround
        ? 'drop-shadow(0 0 4px #ffbb00)'
        : 'drop-shadow(0 0 4px #00d4ff)';

  // Search-match gets an extra outer ring
  const searchRing = isSearchMatch && !isAlert
    ? `<circle r="13" fill="none" stroke="#ffe566" stroke-width="1.5" opacity="0.8" stroke-dasharray="4,2"/>`
    : '';

  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="-16 -16 32 32">
      <g transform="rotate(${track}, 0, 0)" style="filter:${glow}">
        ${onGround
          ? `<circle r="5" fill="${color}" opacity="0.9"/>
             <line x1="0" y1="-8" x2="0" y2="8" stroke="${color}" stroke-width="2"/>
             <line x1="-6" y1="0" x2="6" y2="0" stroke="${color}" stroke-width="2"/>`
          : `<polygon points="0,-9 4,6 0,3 -4,6" fill="${color}" opacity="0.95"/>
             <line x1="-7" y1="2" x2="7" y2="2" stroke="${color}" stroke-width="1.5" opacity="0.8"/>
             <line x1="-4" y1="7" x2="4" y2="7" stroke="${color}" stroke-width="1" opacity="0.6"/>`
        }
        ${isAlert ? `<circle r="11" fill="none" stroke="${color}" stroke-width="1" opacity="0.4" stroke-dasharray="3,3"/>` : ''}
        ${searchRing}
      </g>
    </svg>
  `;

  return L.divIcon({
    html: svg,
    className: isAlert ? 'per-aircraft-icon' : '',
    iconSize: [32, 32],
    iconAnchor: [16, 16],
  });
}

// ---------------------------------------------------------------------------
// Main MapView
// ---------------------------------------------------------------------------
export default function MapView({
  telemetry,
  onAircraftSelect,
  selectedAircraftId,
  searchQuery,
}) {
  const airport  = telemetry?.airport;
  const aircraft = telemetry?.aircraft || [];
  const alerts   = telemetry?.alerts   || [];

  if (!airport) {
    return (
      <div style={{
        flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'var(--color-bg-primary)',
      }}>
        <div style={{ textAlign: 'center', color: 'var(--color-text-dim)' }}>
          <div style={{ fontSize: '32px', marginBottom: '12px' }}>✈</div>
          <div style={{ fontSize: '14px', letterSpacing: '0.2em' }}>CONNECTING TO ATC STREAM...</div>
        </div>
      </div>
    );
  }

  const center  = [airport.center.latitude, airport.center.longitude];
  const radiusM = (airport.geofence_radius_km || 50) * 1000;

  // Set of IDs currently in an active alert
  const alertedIds = new Set(
    alerts.flatMap(a => [a.aircraft_a, a.aircraft_b])
  );

  // ID of the search-matched aircraft (for highlight ring)
  const q = searchQuery?.trim().toUpperCase() || '';
  const searchMatchId = q
    ? aircraft.find(
        ac => ac.callsign?.toUpperCase().includes(q) || ac.icao24?.toUpperCase() === q
      )?.icao24
    : null;

  return (
    <MapContainer
      id="atc-map"
      center={center}
      zoom={9}
      style={{ flex: 1, width: '100%', height: '100%' }}
      zoomControl={true}
      attributionControl={false}
    >
      <MapRecenter center={center} zoom={9} />
      <SearchFlyTo aircraft={aircraft} searchQuery={searchQuery} />

      {/* Stadia Alidade Smooth Dark — free, no API key required */}
      <TileLayer
        url="https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png"
        attribution='&copy; <a href="https://stadiamaps.com/">Stadia Maps</a>, &copy; <a href="https://openmaptiles.org/">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        maxZoom={20}
      />

      {/* Omni-Zone geofence boundary */}
      <Circle
        center={center}
        radius={radiusM}
        pathOptions={{
          color: '#00d4ff', fillColor: '#00d4ff',
          fillOpacity: 0.03, weight: 1.5,
          dashArray: '6 4', opacity: 0.7,
        }}
      />

      {/* Inner warning ring at 25 km */}
      <Circle
        center={center}
        radius={radiusM / 2}
        pathOptions={{
          color: '#00d4ff', fillColor: 'none',
          fillOpacity: 0, weight: 0.5,
          dashArray: '3 6', opacity: 0.3,
        }}
      />

      {/* Runway polygons */}
      {airport.runways?.map((rwy) => (
        <Polygon
          key={rwy.id}
          positions={rwy.coordinates}
          pathOptions={{
            color: '#ffbb00', fillColor: '#ffbb00',
            fillOpacity: 0.12, weight: 1.5, opacity: 0.8,
          }}
        />
      ))}

      {/* Aircraft markers + trajectory lines + callsign labels */}
      {aircraft.map((ac) => {
        if (!ac.lat || !ac.lon) return null;

        const isAlerted     = alertedIds.has(ac.icao24);
        const isSearchMatch = ac.icao24 === searchMatchId;

        const icon = createAircraftIcon(
          ac.true_track || 0,
          isAlerted ? 'COLLISION' : ac.status,
          ac.on_ground,
          isSearchMatch,
        );

        const trajectoryPositions = ac.trajectory?.length
          ? [[ac.lat, ac.lon], ...ac.trajectory.map(pt => [pt.lat, pt.lon])]
          : [];

        const trackColor   = isAlerted ? '#ff2244' : isSearchMatch ? '#ffe566' : ac.on_ground ? '#ffbb00' : '#00d4ff';
        const trackOpacity = isAlerted ? 0.9 : isSearchMatch ? 0.85 : 0.5;

        const labelColor = isAlerted ? '#ff2244' : isSearchMatch ? '#ffe566' : ac.on_ground ? '#ffbb00' : '#00d4ff';
        const labelBorder = (isAlerted || isSearchMatch) ? `1px solid ${labelColor}44` : '1px solid transparent';

        return (
          <div key={ac.icao24}>
            {/* Trajectory line */}
            {trajectoryPositions.length > 1 && (
              <Polyline
                positions={trajectoryPositions}
                pathOptions={{
                  color: trackColor,
                  weight: isSearchMatch ? 2 : 1.5,
                  opacity: trackOpacity,
                  dashArray: isAlerted ? '4 3' : '5 5',
                }}
              />
            )}

            {/* Aircraft marker */}
            <Marker
              position={[ac.lat, ac.lon]}
              icon={icon}
              eventHandlers={{ click: () => onAircraftSelect(ac) }}
            >
              <Popup closeButton={false} className="atc-popup" offset={[0, -16]}>
                <div style={{
                  background: 'var(--color-bg-panel)',
                  border: '1px solid var(--color-border-bright)',
                  borderRadius: '4px', padding: '6px 10px',
                  fontSize: '11px', color: 'var(--color-text-primary)',
                  fontFamily: 'JetBrains Mono, monospace', minWidth: '140px',
                }}>
                  <div style={{ fontWeight: 700, color: 'var(--color-cyan)', fontSize: '13px' }}>
                    {ac.callsign}
                  </div>
                  <div style={{ color: 'var(--color-text-dim)', fontSize: '9px', marginBottom: '4px' }}>
                    {ac.icao24?.toUpperCase()} · {ac.on_ground ? 'GND' : 'AIR'}
                  </div>
                  <div>ALT: {ac.altitude_m != null ? `${Math.round(ac.altitude_m * 3.281).toLocaleString()} ft` : '—'}</div>
                  <div>SPD: {ac.velocity != null ? `${Math.round(ac.velocity * 1.944)} kt` : '—'}</div>
                  <div>HDG: {ac.true_track?.toFixed(0)}°</div>
                </div>
              </Popup>
            </Marker>

            {/* Callsign label */}
            <Marker
              position={[ac.lat, ac.lon]}
              icon={L.divIcon({
                html: `<div style="
                  pointer-events:none;
                  white-space:nowrap;
                  font-family:'JetBrains Mono',monospace;
                  font-size:9px;
                  font-weight:600;
                  color:${labelColor};
                  text-shadow:0 0 4px rgba(0,0,0,0.9);
                  background:rgba(2,8,23,0.75);
                  padding:1px 3px;
                  border-radius:2px;
                  border:${labelBorder};
                ">${ac.callsign} ${ac.altitude_m != null ? Math.round(ac.altitude_m * 3.281 / 100) + 'FL' : ''}</div>`,
                className: '',
                iconSize: [80, 16],
                iconAnchor: [-2, 20],
              })}
              interactive={false}
            />
          </div>
        );
      })}

      {/* ── Alert popup badges REMOVED ──────────────────────────────────────
           Conflicts are displayed exclusively in the right-panel AlertsList.
           Aircraft icons and trajectory lines retain full P-E-R red styling.
         ──────────────────────────────────────────────────────────────────── */}
    </MapContainer>
  );
}
