/**
 * components/TopNav.jsx
 * ----------------------
 * Top navigation bar: system status, airport selector, UTC clock, alert counter.
 */

import { useEffect, useState } from 'react';
import { AlertTriangle, Radio, Search, Wifi, WifiOff, X } from 'lucide-react';


export default function TopNav({ connectionState, alertCount, dataSource, onSearch }) {
  const [utcTime, setUtcTime] = useState('');
  const [inputVal, setInputVal] = useState('');  // local controlled input
  const [active, setActive] = useState(false); // input focus state

  useEffect(() => {
    const tick = () => {
      const now = new Date();
      setUtcTime(
        new Intl.DateTimeFormat('en-IN', {
          hour: '2-digit', minute: '2-digit', second: '2-digit',
          hour12: false, timeZone: 'Asia/Kolkata',
        }).format(now) + ' IST'
      );
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  const statusConfig = {
    connected: { label: 'ONLINE', cls: 'online', Icon: Wifi },
    connecting: { label: 'CONNECTING', cls: 'warning', Icon: Radio },
    reconnecting: { label: 'RECONNECTING', cls: 'warning', Icon: Radio },
    failed: { label: 'OFFLINE', cls: 'offline', Icon: WifiOff },
  };

  const { label, cls, Icon } = statusConfig[connectionState] || statusConfig.failed;

  return (
    <nav
      id="top-nav"
      style={{
        background: 'rgba(2,8,23,0.96)',
        borderBottom: '1px solid var(--color-border)',
        height: '52px',
        display: 'flex',
        alignItems: 'center',
        padding: '0 16px',
        gap: '16px',
        flexShrink: 0,
        backdropFilter: 'blur(12px)',
        zIndex: 1000,
      }}
    >
      {/* Brand */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginRight: '8px' }}>
        <div style={{
          width: '32px', height: '32px', borderRadius: '6px',
          background: 'linear-gradient(135deg, #00d4ff22, #00d4ff44)',
          border: '1px solid var(--color-cyan)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: 'var(--glow-cyan)',
        }}>
          <span style={{ fontSize: '14px' }}>✈</span>
        </div>
        <div>
          <div style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '0.15em', color: 'var(--color-cyan)' }}>
            ATC OMNI-ZONE
          </div>
          <div style={{ fontSize: '9px', color: 'var(--color-text-dim)', letterSpacing: '0.1em' }}>
            TERMINAL SAFETY SYSTEM
          </div>
        </div>
      </div>

      <div style={{ width: '1px', height: '28px', background: 'var(--color-border)', flexShrink: 0 }} />

      {/* Status indicator */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span className={`status-dot ${cls}`} />
        <Icon size={12} style={{ color: cls === 'online' ? 'var(--color-emerald)' : 'var(--color-amber)' }} />
        <span style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '0.1em', color: 'var(--color-text-secondary)' }}>
          {label}
        </span>
        {dataSource === 'mock' && (
          <span style={{
            fontSize: '9px', padding: '1px 5px', borderRadius: '3px',
            background: '#ffbb0022', border: '1px solid #ffbb0066',
            color: 'var(--color-amber)', letterSpacing: '0.05em'
          }}>MOCK</span>
        )}
      </div>

      <div style={{ width: '1px', height: '28px', background: 'var(--color-border)', flexShrink: 0 }} />

      {/* Active zone — static DEL badge */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{ fontSize: '10px', color: 'var(--color-text-dim)', letterSpacing: '0.1em' }}>ACTIVE ZONE</span>
        <div style={{
          display: 'flex', alignItems: 'center', gap: '6px',
          padding: '4px 10px', borderRadius: '4px',
          background: 'linear-gradient(135deg, #00d4ff14, #00d4ff08)',
          border: '1px solid var(--color-cyan)',
          boxShadow: '0 0 8px rgba(0,212,255,0.15)',
        }}>
          <span style={{
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: '13px', fontWeight: 700,
            color: 'var(--color-cyan)', letterSpacing: '0.08em',
          }}>DEL</span>
          <span style={{ width: '1px', height: '12px', background: 'var(--color-border-bright)' }} />
          <span style={{
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: '10px', color: 'var(--color-text-secondary)', letterSpacing: '0.06em',
          }}>VIDP</span>
          <span style={{ fontSize: '9px', color: 'var(--color-text-dim)' }}>INDIRA GANDHI INTL</span>
        </div>
      </div>

      <div style={{ flex: 1 }} />

      {/* ── Callsign Search ────────────────────────────────────────── */}
      <div
        id="callsign-search"
        style={{
          display: 'flex', alignItems: 'center', gap: '0',
          border: `1px solid ${active ? 'var(--color-cyan)' : 'var(--color-border-bright)'}`,
          borderRadius: '5px',
          background: 'rgba(0,212,255,0.04)',
          boxShadow: active ? '0 0 8px rgba(0,212,255,0.2)' : 'none',
          transition: 'border-color 0.2s, box-shadow 0.2s',
          overflow: 'hidden',
        }}
      >
        <div style={{ padding: '0 8px', color: active ? 'var(--color-cyan)' : 'var(--color-text-dim)' }}>
          <Search size={11} />
        </div>
        <input
          id="search-input"
          type="text"
          placeholder="Callsign / ICAO…"
          value={inputVal}
          onFocus={() => setActive(true)}
          onBlur={() => setActive(false)}
          onChange={e => setInputVal(e.target.value.toUpperCase())}
          onKeyDown={e => {
            if (e.key === 'Enter') { onSearch(inputVal); }
            if (e.key === 'Escape') { setInputVal(''); onSearch(''); }
          }}
          style={{
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: 'var(--color-text-primary)',
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: '11px',
            width: '130px',
            padding: '5px 0',
            letterSpacing: '0.06em',
          }}
        />
        {inputVal && (
          <button
            onClick={() => { setInputVal(''); onSearch(''); }}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              padding: '0 6px', color: 'var(--color-text-dim)',
              display: 'flex', alignItems: 'center',
            }}
          >
            <X size={10} />
          </button>
        )}
        <button
          onClick={() => onSearch(inputVal)}
          style={{
            background: inputVal ? 'rgba(0,212,255,0.15)' : 'transparent',
            border: 'none', borderLeft: '1px solid var(--color-border)',
            cursor: 'pointer', padding: '5px 8px',
            color: inputVal ? 'var(--color-cyan)' : 'var(--color-text-dim)',
            fontSize: '9px', fontWeight: 700, letterSpacing: '0.1em',
            transition: 'background 0.15s',
          }}
        >
          GO
        </button>
      </div>

      {/* Alert counter */}
      {alertCount > 0 && (
        <div
          id="alert-counter"
          className="per-active"
          style={{
            display: 'flex', alignItems: 'center', gap: '6px',
            padding: '4px 10px', borderRadius: '4px',
            background: '#ff224420',
            border: '1px solid var(--color-red-alert)',
          }}
        >
          <AlertTriangle size={12} style={{ color: 'var(--color-red-alert)' }} />
          <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--color-red-alert)', letterSpacing: '0.1em' }}>
            {alertCount} ACTIVE ALERT{alertCount !== 1 ? 'S' : ''}
          </span>
        </div>
      )}

      {/* UTC Clock */}
      <div style={{
        fontFamily: 'JetBrains Mono, monospace',
        fontSize: '12px',
        color: 'var(--color-text-secondary)',
        letterSpacing: '0.05em',
      }}>
        {utcTime}
      </div>
    </nav>
  );
}
