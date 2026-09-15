/**
 * hooks/useWebSocket.js
 * ---------------------
 * Custom hook that manages the WebSocket connection to the backend telemetry
 * endpoint. Handles auto-reconnect with exponential backoff and connection
 * state tracking.
 *
 * Airport is fixed to DEL — no switching logic.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/telemetry';

const INITIAL_RECONNECT_DELAY = 1000;  // 1 second
const MAX_RECONNECT_DELAY = 30000;     // 30 seconds
const MAX_RECONNECT_ATTEMPTS = 20;

export function useWebSocket() {
  const [telemetry, setTelemetry] = useState(null);
  const [connectionState, setConnectionState] = useState('connecting'); // connecting | connected | reconnecting | failed

  const wsRef = useRef(null);
  const reconnectDelay = useRef(INITIAL_RECONNECT_DELAY);
  const reconnectAttempts = useRef(0);
  const reconnectTimer = useRef(null);
  const unmounted = useRef(false);

  const connect = useCallback(() => {
    if (unmounted.current) return;

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;
      setConnectionState('connecting');

      ws.onopen = () => {
        reconnectDelay.current = INITIAL_RECONNECT_DELAY;
        reconnectAttempts.current = 0;
        setConnectionState('connected');
        console.log('[WS] Connected to ATC telemetry stream — DEL zone');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setTelemetry(data);
        } catch (e) {
          console.error('[WS] Parse error:', e);
        }
      };

      ws.onerror = () => {
        setConnectionState('reconnecting');
      };

      ws.onclose = () => {
        if (unmounted.current) return;
        setConnectionState('reconnecting');

        if (reconnectAttempts.current >= MAX_RECONNECT_ATTEMPTS) {
          setConnectionState('failed');
          return;
        }

        const delay = Math.min(reconnectDelay.current, MAX_RECONNECT_DELAY);
        console.log(`[WS] Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current + 1})`);

        reconnectTimer.current = setTimeout(() => {
          reconnectDelay.current = Math.min(reconnectDelay.current * 1.5, MAX_RECONNECT_DELAY);
          reconnectAttempts.current += 1;
          connect();
        }, delay);
      };
    } catch (e) {
      console.error('[WS] Connection error:', e);
      setConnectionState('failed');
    }
  }, []);

  useEffect(() => {
    unmounted.current = false;
    connect();

    return () => {
      unmounted.current = true;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.onclose = null; // Prevent reconnect on intentional close
        wsRef.current.close();
      }
    };
  }, [connect]);

  return { telemetry, connectionState };
}
