/**
 * App.jsx — Root Application Component
 * --------------------------------------
 * Manages WebSocket state, layout, and component composition.
 * New in this version:
 *   - searchQuery state → drives MapView callsign search + flyTo
 *   - lastFetchTime tracking → 120s countdown timer in the data footer
 */

import { useState, useEffect, useRef } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import TopNav from './components/TopNav';
import MapView from './components/MapView';
import WeatherWidget from './components/WeatherWidget';
import TelemetryInspector from './components/TelemetryInspector';
import AlertsList from './components/AlertsList';

// Poll interval in seconds — must match backend OPENSKY_POLL_INTERVAL_SECONDS
const POLL_INTERVAL_S = 120;

export default function App() {
  const { telemetry, connectionState } = useWebSocket();

  const [selectedAircraft, setSelectedAircraft] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [lastFetchTime, setLastFetchTime] = useState(null);   // JS Date object
  const [countdown, setCountdown] = useState(POLL_INTERVAL_S);

  const alerts = telemetry?.alerts || [];
  const weather = telemetry?.weather;
  const dataSource = telemetry?.data_source || 'unknown';

  // ── Track last OpenSky poll via WebSocket timestamp ───────────────────────
  // The WS payload timestamp updates every 2s but the data_source field only
  // changes to 'opensky_live' when a real poll happens. We approximate the
  // last fetch time as the timestamp of the first payload received, then
  // reset the countdown whenever `aircraft` array length meaningfully changes
  // (which happens after a real poll). For simplicity and reliability, we just
  // parse the WS payload timestamp and reset to POLL_INTERVAL_S each cycle.
  const prevAircraftLen = useRef(null);

  useEffect(() => {
    if (!telemetry?.timestamp) return;

    const len = telemetry.aircraft?.length ?? 0;

    // Reset countdown when the aircraft snapshot visibly refreshes
    // (either first payload or count changes, indicating a new OpenSky poll)
    if (prevAircraftLen.current === null || Math.abs(len - prevAircraftLen.current) > 0) {
      setLastFetchTime(new Date(telemetry.timestamp));
      setCountdown(POLL_INTERVAL_S);
      prevAircraftLen.current = len;
    }
  }, [telemetry?.timestamp]);

  // ── 1-second countdown ticker ─────────────────────────────────────────────
  useEffect(() => {
    const id = setInterval(() => {
      setCountdown(prev => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(id);
  }, []);

  // ── Aircraft selection ────────────────────────────────────────────────────
  const handleAircraftSelect = (ac) => {
    setSelectedAircraft(prev => prev?.icao24 === ac.icao24 ? null : ac);
  };

  const freshSelected = selectedAircraft
    ? (telemetry?.aircraft?.find(a => a.icao24 === selectedAircraft.icao24) || selectedAircraft)
    : null;

  // ── Search submission ─────────────────────────────────────────────────────
  const handleSearch = (query) => {
    setSearchQuery(query);
    // If query matches an aircraft, also open its telemetry inspector
    if (query && telemetry?.aircraft) {
      const q = query.trim().toUpperCase();
      const found = telemetry.aircraft.find(
        ac => ac.callsign?.toUpperCase().includes(q) || ac.icao24?.toUpperCase() === q
      );
      if (found) setSelectedAircraft(found);
    }
  };

  // ── Format fetch time for display ────────────────────────────────────────
  const fetchTimeStr = lastFetchTime
    ? new Intl.DateTimeFormat('en-IN', {
      hour: '2-digit', minute: '2-digit', second: '2-digit',
      hour12: false, timeZone: 'Asia/Kolkata',
    }).format(lastFetchTime) + ' IST'
    : '—';

  const isImminentRefresh = countdown <= 10;

  return (
    <div id="app-root" style={{
      display: 'flex', flexDirection: 'column',
      height: '100vh', width: '100vw',
      overflow: 'hidden', background: 'var(--color-bg-primary)',
    }}>
      {/* Top navigation bar — includes callsign search input */}
      <TopNav
        connectionState={connectionState}
        alertCount={alerts.length}
        dataSource={dataSource}
        onSearch={handleSearch}
      />

      {/* Main content area */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

        {/* Map — takes remaining space */}
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
          <MapView
            telemetry={telemetry}
            onAircraftSelect={handleAircraftSelect}
            selectedAircraftId={freshSelected?.icao24}
            searchQuery={searchQuery}
          />

          {/* Aircraft count badge — bottom-left */}
          {telemetry && (
            <div style={{
              position: 'absolute', bottom: '16px', left: '16px',
              background: 'rgba(2,8,23,0.88)',
              border: '1px solid var(--color-border-bright)',
              borderRadius: '6px', padding: '6px 12px',
              backdropFilter: 'blur(8px)', zIndex: 1000,
              display: 'flex', gap: '16px',
            }}>
              <Stat label="TRACKED" value={telemetry.aircraft?.length || 0} color="var(--color-cyan)" />
              <Stat label="AIRBORNE" value={telemetry.aircraft?.filter(a => !a.on_ground).length || 0} color="var(--color-emerald)" />
              <Stat label="GROUND" value={telemetry.aircraft?.filter(a => a.on_ground).length || 0} color="var(--color-amber)" />
              <Stat label="ALERTS" value={alerts.length} color={alerts.length > 0 ? 'var(--color-red-alert)' : 'var(--color-text-dim)'} />
            </div>
          )}
        </div>

        {/* Right panel */}
        <div style={{
          width: '280px', flexShrink: 0,
          display: 'flex', flexDirection: 'column', gap: '8px',
          padding: '8px', overflowY: 'auto',
          background: 'rgba(2,8,23,0.7)',
          borderLeft: '1px solid var(--color-border)',
        }}>
          <WeatherWidget weather={weather} />

          {freshSelected && (
            <TelemetryInspector
              aircraft={freshSelected}
              onClose={() => setSelectedAircraft(null)}
            />
          )}

          <AlertsList alerts={alerts} />

          {/* ── Data source + 120s countdown footer ───────────────────── */}
          <div style={{
            marginTop: 'auto', padding: '8px 10px',
            borderRadius: '6px',
            background: 'var(--color-bg-surface)',
            border: '1px solid var(--color-border)',
          }}>
            <div style={{
              fontSize: '8px', color: 'var(--color-text-dim)',
              letterSpacing: '0.1em', marginBottom: '4px',
            }}>
              DATA SOURCE
            </div>

            {/* Source type indicator */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
              <span className={`status-dot ${dataSource === 'opensky_live' ? 'online' : 'mock'}`} />
              <span style={{
                fontSize: '10px', color: 'var(--color-text-secondary)',
                fontFamily: 'JetBrains Mono, monospace',
              }}>
                {dataSource === 'opensky_live' ? 'OpenSky Live' : 'Mock Generator'}
              </span>
            </div>

            <div style={{ height: '1px', background: 'var(--color-border)', marginBottom: '6px' }} />

            {/* Last fetch timestamp */}
            <div style={{ marginBottom: '3px' }}>
              <span style={{
                fontSize: '8px', color: 'var(--color-text-dim)',
                letterSpacing: '0.08em',
              }}>LAST FETCH  </span>
              <span style={{
                fontFamily: 'JetBrains Mono, monospace',
                fontSize: '9px', color: 'var(--color-text-secondary)',
              }}>
                {fetchTimeStr}
              </span>
            </div>

            {/* Next update countdown */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{
                fontSize: '8px', color: 'var(--color-text-dim)',
                letterSpacing: '0.08em',
              }}>NEXT IN  </span>
              <span style={{
                fontFamily: 'JetBrains Mono, monospace',
                fontSize: '11px',
                fontWeight: 700,
                color: isImminentRefresh ? 'var(--color-amber)' : 'var(--color-emerald)',
                transition: 'color 0.3s ease',
                // Brief pulse when imminent
                animation: isImminentRefresh ? 'blink 1s step-start infinite' : 'none',
              }}>
                {countdown}s
              </span>
              {isImminentRefresh && (
                <span style={{
                  fontSize: '8px', color: 'var(--color-amber)',
                  letterSpacing: '0.06em', fontWeight: 600,
                }}>
                  ⚡ REFRESHING
                </span>
              )}
            </div>

            <div style={{
              fontSize: '8px', color: 'var(--color-text-dim)',
              marginTop: '4px', letterSpacing: '0.05em',
            }}>
              WS: 2s · Poll: 120s · OWM TTL: 300s
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, color }) {
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: '16px', fontWeight: 700, color, fontFamily: 'JetBrains Mono, monospace' }}>
        {value}
      </div>
      <div style={{ fontSize: '8px', color: 'var(--color-text-dim)', letterSpacing: '0.1em' }}>
        {label}
      </div>
    </div>
  );
}
