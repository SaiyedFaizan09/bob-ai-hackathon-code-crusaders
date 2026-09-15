/**
 * components/TelemetryInspector.jsx
 * -----------------------------------
 * Shows detailed telemetry for a selected aircraft.
 */

import { X, ArrowUp, ArrowDown, Minus } from 'lucide-react';

function Row({ label, value, unit, highlight }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0' }}>
      <span style={{ fontSize: '10px', color: 'var(--color-text-dim)' }}>{label}</span>
      <span style={{
        fontFamily: 'JetBrains Mono, monospace',
        fontSize: '12px',
        fontWeight: 600,
        color: highlight || 'var(--color-text-primary)',
      }}>
        {value}{unit && <span style={{ fontSize: '9px', fontWeight: 400, marginLeft: '2px', color: 'var(--color-text-dim)' }}>{unit}</span>}
      </span>
    </div>
  );
}

const STATUS_CONFIG = {
  NORMAL: { label: 'NORMAL', color: 'var(--color-emerald)', bg: '#00ff8812' },
  WARNING: { label: 'WARNING', color: 'var(--color-amber)', bg: '#ffbb0012' },
  COLLISION: { label: 'COLLISION', color: 'var(--color-red-alert)', bg: '#ff224412' },
  INCURSION: { label: 'INCURSION', color: 'var(--color-red-alert)', bg: '#ff224412' },
};

export default function TelemetryInspector({ aircraft, onClose }) {
  if (!aircraft) return null;

  const s = STATUS_CONFIG[aircraft.status] || STATUS_CONFIG.NORMAL;
  const altFt = aircraft.altitude_m != null ? Math.round(aircraft.altitude_m * 3.28084) : null;
  const spdKt = aircraft.velocity != null ? Math.round(aircraft.velocity * 1.944) : null;
  const vrFpm = aircraft.vertical_rate != null ? Math.round(aircraft.vertical_rate * 196.85) : null;

  const VrIcon = vrFpm > 100 ? ArrowUp : vrFpm < -100 ? ArrowDown : Minus;
  const vrColor = vrFpm > 100 ? 'var(--color-emerald)' : vrFpm < -100 ? 'var(--color-amber)' : 'var(--color-text-dim)';

  return (
    <div
      id="telemetry-inspector"
      className="glass-panel"
      style={{ padding: '12px 14px', animation: 'fade-in-up 0.2s ease' }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
        <div>
          <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--color-cyan)', fontFamily: 'JetBrains Mono, monospace', letterSpacing: '0.05em' }}>
            {aircraft.callsign || aircraft.icao24}
          </div>
          <div style={{ fontSize: '9px', color: 'var(--color-text-dim)', letterSpacing: '0.1em' }}>
            {aircraft.icao24?.toUpperCase()} · {aircraft.on_ground ? 'GROUND' : 'AIRBORNE'}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{
            fontSize: '9px', padding: '2px 7px', borderRadius: '3px',
            background: s.bg, border: `1px solid ${s.color}`,
            color: s.color, fontWeight: 700, letterSpacing: '0.1em',
          }}>
            {s.label}
          </span>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '2px', color: 'var(--color-text-dim)' }}
          >
            <X size={14} />
          </button>
        </div>
      </div>

      <div className="divider" style={{ marginBottom: '10px' }} />

      <Row label="ALTITUDE" value={altFt != null ? altFt.toLocaleString() : '—'} unit="ft" highlight="var(--color-text-primary)" />
      <Row label="GND SPEED" value={spdKt != null ? spdKt : '—'} unit="kt" />
      <Row label="HEADING" value={aircraft.true_track != null ? `${aircraft.true_track.toFixed(0)}°` : '—'} />
      <Row label="V/SPEED" value={vrFpm != null ? `${vrFpm > 0 ? '+' : ''}${vrFpm}` : '—'} unit="fpm" highlight={vrColor} />
      <Row label="LATITUDE" value={aircraft.lat?.toFixed(5)} />
      <Row label="LONGITUDE" value={aircraft.lon?.toFixed(5)} />

      {aircraft.trajectory?.length > 0 && (
        <>
          <div className="divider" style={{ margin: '8px 0' }} />
          <div style={{ fontSize: '9px', color: 'var(--color-text-dim)', letterSpacing: '0.1em', marginBottom: '6px' }}>
            TRAJECTORY FORECAST
          </div>
          {aircraft.trajectory.map((pt) => (
            <div key={pt.t} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0', fontSize: '10px' }}>
              <span style={{ color: 'var(--color-text-dim)' }}>T+{pt.t}s</span>
              <span style={{ fontFamily: 'JetBrains Mono, monospace', color: 'var(--color-text-secondary)', fontSize: '10px' }}>
                {pt.lat?.toFixed(4)}, {pt.lon?.toFixed(4)} · {Math.round((pt.alt || 0) * 3.281).toLocaleString()}ft
              </span>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
