/**
 * components/AlertsList.jsx
 * --------------------------
 * Scrollable list of active collision and runway incursion alerts.
 */

import { AlertTriangle, Zap } from 'lucide-react';

function AlertCard({ alert, index }) {
  const isMidAir = alert.type === 'MID_AIR_COLLISION';
  const color = 'var(--color-red-alert)';
  const bg = '#ff224410';

  return (
    <div
      id={`alert-${index}`}
      className="per-active"
      style={{
        padding: '10px 12px',
        borderRadius: '6px',
        background: bg,
        border: `1px solid ${color}`,
        marginBottom: '8px',
        animation: 'slide-in-right 0.3s ease',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
        {isMidAir
          ? <AlertTriangle size={12} style={{ color }} />
          : <Zap size={12} style={{ color }} />
        }
        <span style={{ fontSize: '10px', fontWeight: 700, color, letterSpacing: '0.1em' }}>
          {isMidAir ? 'MID-AIR COLLISION' : 'RUNWAY INCURSION'}
        </span>
        {alert.t_cpa_seconds > 0 && (
          <span style={{
            marginLeft: 'auto',
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: '11px',
            fontWeight: 700,
            color,
            animation: 'countdown-tick 1s ease-in-out infinite',
          }}>
            ⏱ {alert.t_cpa_seconds.toFixed(0)}s
          </span>
        )}
      </div>

      {/* Aircraft pair */}
      <div style={{ display: 'flex', gap: '6px', alignItems: 'center', marginBottom: '8px' }}>
        <span style={{
          fontFamily: 'JetBrains Mono, monospace', fontSize: '13px',
          fontWeight: 700, color,
        }}>
          {alert.callsign_a}
        </span>
        <span style={{ color: 'var(--color-text-dim)', fontSize: '11px' }}>↔</span>
        <span style={{
          fontFamily: 'JetBrains Mono, monospace', fontSize: '13px',
          fontWeight: 700, color,
        }}>
          {alert.callsign_b}
        </span>
      </div>

      {/* Separation */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '8px' }}>
        <div>
          <div style={{ fontSize: '8px', color: 'var(--color-text-dim)', letterSpacing: '0.1em' }}>H-SEP</div>
          <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '11px', color: 'var(--color-text-secondary)' }}>
            {(alert.horizontal_sep_m / 1852).toFixed(2)} NM
          </div>
        </div>
        {isMidAir && (
          <div>
            <div style={{ fontSize: '8px', color: 'var(--color-text-dim)', letterSpacing: '0.1em' }}>V-SEP</div>
            <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '11px', color: 'var(--color-text-secondary)' }}>
              {Math.round((alert.vertical_sep_m || 0) * 3.281)} ft
            </div>
          </div>
        )}
      </div>

      <div className="divider" style={{ marginBottom: '8px' }} />

      {/* Resolution Advisories */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <div style={{
          fontSize: '9px', fontWeight: 600, padding: '3px 8px',
          background: '#ff224415', borderRadius: '3px',
          color: 'var(--color-red-alert)', letterSpacing: '0.05em',
          fontFamily: 'JetBrains Mono, monospace',
        }}>
          RA: {alert.resolution_advisory_a}
        </div>
        <div style={{
          fontSize: '9px', fontWeight: 600, padding: '3px 8px',
          background: '#ff224415', borderRadius: '3px',
          color: 'var(--color-red-alert)', letterSpacing: '0.05em',
          fontFamily: 'JetBrains Mono, monospace',
        }}>
          RA: {alert.resolution_advisory_b}
        </div>
      </div>
    </div>
  );
}

export default function AlertsList({ alerts }) {
  if (!alerts || alerts.length === 0) {
    return (
      <div className="glass-panel" style={{ padding: '12px 14px' }}>
        <div style={{ fontSize: '9px', fontWeight: 700, letterSpacing: '0.15em', color: 'var(--color-text-dim)', marginBottom: '8px' }}>
          ACTIVE ALERTS
        </div>
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px',
          padding: '16px 0',
        }}>
          <div style={{
            width: '8px', height: '8px', borderRadius: '50%',
            background: 'var(--color-emerald)',
            boxShadow: 'var(--glow-emerald)',
            animation: 'blink 2s infinite',
          }} />
          <span style={{ fontSize: '11px', color: 'var(--color-emerald)', fontWeight: 600 }}>
            NO ACTIVE CONFLICTS
          </span>
          <span style={{ fontSize: '9px', color: 'var(--color-text-dim)' }}>
            All traffic within safe separation
          </span>
        </div>
      </div>
    );
  }

  return (
    <div id="alerts-list" className="glass-panel" style={{ padding: '12px 14px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
        <span style={{ fontSize: '9px', fontWeight: 700, letterSpacing: '0.15em', color: 'var(--color-text-dim)' }}>
          ACTIVE ALERTS
        </span>
        <span style={{
          fontSize: '9px', fontWeight: 700,
          color: 'var(--color-red-alert)',
          fontFamily: 'JetBrains Mono, monospace',
        }}>
          {alerts.length} CONFLICT{alerts.length > 1 ? 'S' : ''}
        </span>
      </div>

      <div style={{ maxHeight: '280px', overflowY: 'auto', paddingRight: '2px' }}>
        {alerts.map((alert, i) => (
          <AlertCard key={`${alert.aircraft_a}-${alert.aircraft_b}`} alert={alert} index={i} />
        ))}
      </div>
    </div>
  );
}
