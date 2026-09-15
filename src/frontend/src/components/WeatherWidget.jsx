/**
 * components/WeatherWidget.jsx
 * -----------------------------
 * Displays live weather conditions for the active airport.
 */

import { Wind, Eye, Droplets, Thermometer } from 'lucide-react';

function WindArrow({ deg, speed }) {
  return (
    <div style={{ position: 'relative', width: '60px', height: '60px' }}>
      <div style={{
        width: '60px', height: '60px', borderRadius: '50%',
        border: '1px solid var(--color-border-bright)',
        background: 'var(--color-bg-primary)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        position: 'relative',
      }}>
        {/* Compass labels */}
        {[['N', 0], ['E', 90], ['S', 180], ['W', 270]].map(([lbl, d]) => {
          const r = 22;
          const angle = (d - 90) * Math.PI / 180;
          const x = 30 + r * Math.cos(angle);
          const y = 30 + r * Math.sin(angle);
          return (
            <span key={lbl} style={{
              position: 'absolute', left: `${x}px`, top: `${y}px`,
              transform: 'translate(-50%,-50%)',
              fontSize: '7px', color: 'var(--color-text-dim)',
              fontWeight: 600,
            }}>{lbl}</span>
          );
        })}
        {/* Arrow */}
        <div style={{
          position: 'absolute', width: '2px', height: '20px',
          background: 'var(--color-cyan)',
          borderRadius: '1px',
          transformOrigin: 'bottom center',
          bottom: '50%',
          left: '50%',
          transform: `translateX(-50%) rotate(${deg}deg)`,
          boxShadow: 'var(--glow-cyan)',
        }} />
        <div style={{
          position: 'absolute', width: '6px', height: '6px',
          borderRadius: '50%',
          background: 'var(--color-cyan)',
          boxShadow: 'var(--glow-cyan)',
        }} />
      </div>
      <div style={{
        position: 'absolute', bottom: '-16px', left: '50%',
        transform: 'translateX(-50%)',
        fontSize: '9px', color: 'var(--color-text-dim)',
        whiteSpace: 'nowrap',
      }}>
        {deg}°
      </div>
    </div>
  );
}

export default function WeatherWidget({ weather }) {
  if (!weather) return null;

  const isPrecip = weather.is_precipitation;
  const visKm = (weather.visibility_m / 1000).toFixed(1);

  const conditionColor = isPrecip
    ? 'var(--color-amber)'
    : 'var(--color-emerald)';

  return (
    <div id="weather-widget" className="glass-panel" style={{ padding: '12px 14px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '10px' }}>
        <span style={{ fontSize: '9px', fontWeight: 700, letterSpacing: '0.15em', color: 'var(--color-text-dim)' }}>
          SURFACE WEATHER
        </span>
        <span style={{
          fontSize: '9px', padding: '1px 6px', borderRadius: '3px',
          background: isPrecip ? '#ffbb0022' : '#00ff8822',
          border: `1px solid ${conditionColor}`,
          color: conditionColor,
          fontWeight: 600,
        }}>
          {weather.condition?.toUpperCase()}
        </span>
      </div>

      <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
        {/* Wind arrow */}
        <WindArrow deg={weather.wind_deg} speed={weather.wind_speed} />

        {/* Metrics */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '10px', color: 'var(--color-text-dim)' }}>
              <Wind size={10} /> WIND
            </span>
            <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--color-cyan)', fontFamily: 'JetBrains Mono, monospace' }}>
              {weather.wind_speed?.toFixed(1)} <span style={{ fontSize: '9px', fontWeight: 400 }}>m/s</span>
            </span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '10px', color: 'var(--color-text-dim)' }}>
              <Eye size={10} /> VIS
            </span>
            <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--color-text-primary)', fontFamily: 'JetBrains Mono, monospace' }}>
              {visKm} <span style={{ fontSize: '9px', fontWeight: 400 }}>km</span>
            </span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '10px', color: 'var(--color-text-dim)' }}>
              <Thermometer size={10} /> TEMP
            </span>
            <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--color-text-primary)', fontFamily: 'JetBrains Mono, monospace' }}>
              {weather.temperature_c?.toFixed(0)}° <span style={{ fontSize: '9px', fontWeight: 400 }}>C</span>
            </span>
          </div>
          {isPrecip && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginTop: '2px' }}>
              <Droplets size={10} style={{ color: 'var(--color-amber)' }} />
              <span style={{ fontSize: '9px', color: 'var(--color-amber)', fontWeight: 600 }}>
                FRICTION PENALTY ×1.6 ACTIVE
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
