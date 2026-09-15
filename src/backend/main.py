"""
main.py — FastAPI Application Entry Point
==========================================
Starts the ATC safety backend with:
  - /health         REST endpoint (system status + rate-limit counters)
  - /ws/telemetry   WebSocket endpoint (streams JSON every 2 seconds)
  - /airports       REST endpoint (list of configured airports)

Architecture:
  Lifespan context manager starts/stops:
    • OpenSkyPoller (polls every 120 s, serves cache between polls)
    • WeatherService (fetches with 300 s TTL cache)
  
  WebSocket broadcaster:
    • Runs every 2 s per client — NO extra API calls (re-serves cached state)
    • Calls CollisionEngine.run() on the cached aircraft snapshot
    • Broadcasts unified JSON to all connected clients
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from config.settings import get_settings
from engine.collision_engine import CollisionEngine
from services.opensky_service import OpenSkyPoller
from services.weather_service import WeatherService

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("atc.main")


# ---------------------------------------------------------------------------
# Shared service singletons (populated during lifespan)
# ---------------------------------------------------------------------------
_poller: Optional[OpenSkyPoller] = None
_weather: Optional[WeatherService] = None


# ---------------------------------------------------------------------------
# Lifespan: start/stop background services
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _poller, _weather

    logger.info("=== ATC Safety Backend starting ===")
    logger.info(
        "Active airport: %s | OpenSky credentials: %s | OWM key: %s",
        settings.active_airport_code,
        "YES" if settings.has_opensky_credentials else "NO (using mock)",
        "YES" if settings.has_openweather_key else "NO (using defaults)",
    )

    _poller = OpenSkyPoller()
    _weather = WeatherService()

    await _weather.start()
    await _poller.start(settings.active_airport_code)

    logger.info(
        "Services started. Poll interval: %ds | Weather TTL: %ds",
        settings.opensky_poll_interval_seconds,
        settings.openweather_cache_ttl_seconds,
    )

    yield   # Application runs here

    logger.info("=== ATC Safety Backend shutting down ===")
    await _poller.stop()
    await _weather.stop()


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Unified ATC Terminal Safety System",
    description=(
        "Real-time ADS-B ingestion, kinematic collision detection, "
        "and WebSocket streaming for terminal airspace safety."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------
class ConnectionManager:
    """Manages the pool of active WebSocket client connections."""

    def __init__(self) -> None:
        self._active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._active.append(ws)
        logger.info("WS client connected (total: %d)", len(self._active))

    def disconnect(self, ws: WebSocket) -> None:
        self._active.remove(ws)
        logger.info("WS client disconnected (total: %d)", len(self._active))

    async def send(self, ws: WebSocket, data: str) -> bool:
        """Send a message to a single client. Returns False if client disconnected."""
        try:
            await ws.send_text(data)
            return True
        except Exception:
            return False


manager = ConnectionManager()
engine = CollisionEngine(settings)


# ---------------------------------------------------------------------------
# REST Endpoints
# ---------------------------------------------------------------------------
@app.get("/health", tags=["System"])
async def health():
    """System health check with rate-limit counters."""
    rate_info = _poller.rate_info if _poller else {}
    return {
        "status": "ok",
        "airport": settings.active_airport_code,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "has_opensky_credentials": settings.has_opensky_credentials,
        "has_openweather_key": settings.has_openweather_key,
        "rate_limit": {
            "opensky_poll_interval_seconds": settings.opensky_poll_interval_seconds,
            "openweather_cache_ttl_seconds": settings.openweather_cache_ttl_seconds,
            "opensky_polls_today": rate_info.get("opensky_polls_today", 0),
            "last_poll_at": rate_info.get("last_poll_at"),
            "next_poll_at": rate_info.get("next_poll_at"),
            "data_source": rate_info.get("data_source", "unknown"),
            "using_mock": rate_info.get("using_mock", True),
        },
    }


@app.get("/airport", tags=["System"])
async def get_active_airport():
    """Return DEL (VIDP) airport configuration — the only monitored zone."""
    data = settings.get_airport_config("DEL")
    bbox = settings.compute_bounding_box("DEL")
    return {
        "icao": data.get("icao"),
        "iata": "DEL",
        "name": data.get("name"),
        "city": data.get("city"),
        "center": data["center"],
        "geofence_radius_km": data.get("geofence_radius_km", 50.0),
        "bounding_box": bbox,
        "runway_count": len(data.get("runways", [])),
    }


# ---------------------------------------------------------------------------
# WebSocket Endpoint
# ---------------------------------------------------------------------------
@app.websocket("/ws/telemetry")
async def telemetry_stream(websocket: WebSocket):
    """
    Real-time telemetry WebSocket endpoint — DEL (VIDP) terminal zone only.

    Streams a unified JSON payload every 2 seconds:
    {
      "airport": {...},
      "weather": {...},
      "aircraft": [...],
      "alerts": [...],
      "timestamp": "...",
      "data_source": "opensky_live" | "mock"
    }

    The backend re-serves cached state between 120 s poll cycles —
    zero additional API calls from the WebSocket broadcast loop.
    """
    await manager.connect(websocket)

    # Fixed to DEL — no dynamic airport switching
    airport_code = "DEL"
    airport_config = settings.get_airport_config(airport_code)

    try:
        while True:
            broadcast_start = asyncio.get_event_loop().time()

            # Drain any unexpected client frames without acting on them
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=0.05)
            except (asyncio.TimeoutError, Exception):
                pass

            # Gather data (always fast — served from in-memory cache)
            aircraft_list, data_source = await _poller.get_aircraft(airport_code)
            weather = await _weather.get_weather(airport_code)

            # Run collision engine on current snapshot
            alerts = engine.run(aircraft_list, weather, airport_config)

            # Serialize and broadcast
            payload = {
                "airport": {
                    "code": airport_code,
                    "icao": airport_config.get("icao"),
                    "name": airport_config.get("name"),
                    "city": airport_config.get("city"),
                    "center": airport_config["center"],
                    "geofence_radius_km": airport_config.get("geofence_radius_km", 50.0),
                    "runways": airport_config.get("runways", []),
                },
                "weather": weather.to_dict(),
                "aircraft": [ac.to_dict() for ac in aircraft_list],
                "alerts": [a.to_dict() for a in alerts],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data_source": data_source,
                "active_alerts_count": len(alerts),
            }

            ok = await manager.send(websocket, json.dumps(payload))
            if not ok:
                break

            # Maintain 2-second broadcast cadence
            elapsed = asyncio.get_event_loop().time() - broadcast_start
            await asyncio.sleep(max(0.0, 2.0 - elapsed))

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as exc:
        logger.error("WebSocket error: %s", exc)
        manager.disconnect(websocket)


# ---------------------------------------------------------------------------
# Dev entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        log_level=settings.log_level,
        reload=True,
    )
