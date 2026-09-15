"""
services/opensky_service.py
============================
OpenSky Network ADS-B ingestion with OAuth2 token management,
rate-conserving polling, and a deterministic mock fallback.

Rate budget (1,000 req/day):
  - Token refresh:    ~48 req/day   (one per 30-min token lifetime)
  - State polls:      ~720 req/day  (every 120 s)
  - Backoff retries:  ~50 req/day   (buffer)
  ─────────────────────────────────────────────
  Total:              ~818 req/day  (~182 headroom)

The WebSocket layer broadcasts every 2 seconds by re-serving the last
*cached* state, so no extra API calls occur between poll intervals.
"""

from __future__ import annotations

import asyncio
import logging
import math
import random
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

from config.settings import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Aircraft state vector model
# ---------------------------------------------------------------------------
@dataclass
class AircraftState:
    """Parsed OpenSky state vector for a single aircraft."""

    icao24: str
    callsign: str
    longitude: Optional[float]
    latitude: Optional[float]
    baro_altitude: Optional[float]    # metres
    geo_altitude: Optional[float]     # metres
    on_ground: bool
    velocity: Optional[float]         # m/s
    true_track: Optional[float]       # degrees (0 = North, clockwise)
    vertical_rate: Optional[float]    # m/s (positive = climb)

    # Enriched by the collision engine — not from OpenSky
    status: str = "NORMAL"            # NORMAL | WARNING | COLLISION | INCURSION
    trajectory: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "icao24": self.icao24,
            "callsign": self.callsign,
            "lat": self.latitude,
            "lon": self.longitude,
            "altitude_m": self.baro_altitude,
            "geo_altitude_m": self.geo_altitude,
            "on_ground": self.on_ground,
            "velocity": self.velocity,
            "true_track": self.true_track,
            "vertical_rate": self.vertical_rate,
            "status": self.status,
            "trajectory": self.trajectory,
        }


# ---------------------------------------------------------------------------
# OAuth2 Token Manager
# ---------------------------------------------------------------------------
class TokenManager:
    """
    OAuth2 Client Credentials token manager for OpenSky Network.

    - Fetches a new token on first use.
    - Caches the token and auto-refreshes it 30 seconds before expiry.
    - Thread-safe via asyncio.Lock.
    - Token lifetime is assumed to be 1,800 s (30 min); the actual
      `expires_in` field from the response overrides this.
    """

    _ASSUMED_EXPIRY_S = 1_800   # 30 minutes
    _REFRESH_BUFFER_S = 30      # refresh this many seconds before expiry

    def __init__(self, settings) -> None:
        self._settings = settings
        self._token: Optional[str] = None
        self._expires_at: float = 0.0
        self._lock = asyncio.Lock()
        self._client: Optional[httpx.AsyncClient] = None

    async def start(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def get_valid_token(self) -> Optional[str]:
        """
        Return a valid Bearer token, refreshing proactively if needed.
        Returns None if credentials are not configured.
        """
        if not self._settings.has_opensky_credentials:
            return None

        async with self._lock:
            # Refresh if expired or within the refresh buffer window
            if time.monotonic() >= (self._expires_at - self._REFRESH_BUFFER_S):
                await self._refresh()
            return self._token

    async def _refresh(self) -> None:
        """Fetch a new access token from the OpenSky token endpoint."""
        logger.info("TokenManager: refreshing OpenSky access token")
        try:
            resp = await self._client.post(
                self._settings.opensky_token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._settings.opensky_client_id,
                    "client_secret": self._settings.opensky_client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=15.0,
            )
            resp.raise_for_status()
            payload = resp.json()
            self._token = payload["access_token"]
            expires_in = int(payload.get("expires_in", self._ASSUMED_EXPIRY_S))
            self._expires_at = time.monotonic() + expires_in
            logger.info(
                "TokenManager: token obtained, expires in %d s", expires_in
            )
        except httpx.HTTPStatusError as exc:
            logger.error(
                "TokenManager: HTTP %d from token endpoint: %s",
                exc.response.status_code,
                exc.response.text[:200],
            )
            self._token = None
        except Exception as exc:  # noqa: BLE001
            logger.error("TokenManager: unexpected error: %s", exc)
            self._token = None


# ---------------------------------------------------------------------------
# Mock aircraft generator (deterministic fallback)
# ---------------------------------------------------------------------------
class MockAircraftGenerator:
    """
    Deterministic mock ADS-B generator.

    Produces 8 aircraft in realistic flight patterns around the active airport.
    Two pairs are always on converging trajectories to guarantee P-E-R alert
    triggering for demo purposes.

    The simulation advances by `elapsed_seconds` on each call so aircraft
    move continuously without persistent state.
    """

    MOCK_CALLSIGNS = [
        "AI101", "6E502", "SG304", "UK706", "IX811",
        "AI202", "6E303", "QP100",
    ]

    def __init__(self) -> None:
        self._start_time = time.monotonic()

    def generate(self, airport_code: str, settings) -> list[AircraftState]:
        """Generate a snapshot of aircraft for the given airport."""
        airport = settings.get_airport_config(airport_code)
        center = airport["center"]
        clat = center["latitude"]
        clon = center["longitude"]

        elapsed = time.monotonic() - self._start_time
        aircraft: list[AircraftState] = []

        # ---- Pair 1: converging mid-air collision scenario ----
        # Aircraft A: flying East at 280° → 100° track, descending
        a1_lat = clat + 0.15 - (elapsed * 0.0002)
        a1_lon = clon - 0.20 + (elapsed * 0.0003)
        aircraft.append(AircraftState(
            icao24="mock001",
            callsign=self.MOCK_CALLSIGNS[0],
            latitude=a1_lat, longitude=a1_lon,
            baro_altitude=3500.0 - elapsed * 2.0,
            geo_altitude=3520.0 - elapsed * 2.0,
            on_ground=False, velocity=85.0, true_track=110.0,
            vertical_rate=-3.5,
        ))

        # Aircraft B: flying West on opposing converging track
        a2_lat = clat + 0.12 + (elapsed * 0.0001)
        a2_lon = clon + 0.25 - (elapsed * 0.0003)
        aircraft.append(AircraftState(
            icao24="mock002",
            callsign=self.MOCK_CALLSIGNS[1],
            latitude=a2_lat, longitude=a2_lon,
            baro_altitude=3400.0 - elapsed * 1.5,
            geo_altitude=3420.0 - elapsed * 1.5,
            on_ground=False, velocity=92.0, true_track=290.0,
            vertical_rate=-2.0,
        ))

        # ---- Pair 2: runway incursion scenario ----
        runway = airport["runways"][0]["coordinates"]
        rw_center_lat = sum(c[0] for c in runway) / 4
        rw_center_lon = sum(c[1] for c in runway) / 4

        # Landing aircraft
        a3_lat = rw_center_lat + 0.05 - (elapsed * 0.0003)
        a3_lon = rw_center_lon - 0.01
        aircraft.append(AircraftState(
            icao24="mock003",
            callsign=self.MOCK_CALLSIGNS[2],
            latitude=a3_lat, longitude=a3_lon,
            baro_altitude=max(0.0, 800.0 - elapsed * 5.0),
            geo_altitude=max(0.0, 810.0 - elapsed * 5.0),
            on_ground=a3_lat <= rw_center_lat + 0.01,
            velocity=max(10.0, 65.0 - elapsed * 0.3),
            true_track=180.0, vertical_rate=-5.0,
        ))

        # Taxiing intruder approaching runway
        a4_lat = rw_center_lat - 0.008 + (elapsed * 0.00015)
        a4_lon = rw_center_lon + (elapsed * 0.00005)
        aircraft.append(AircraftState(
            icao24="mock004",
            callsign=self.MOCK_CALLSIGNS[3],
            latitude=a4_lat, longitude=a4_lon,
            baro_altitude=0.0, geo_altitude=0.0,
            on_ground=True, velocity=8.0, true_track=0.0,
            vertical_rate=0.0,
        ))

        # ---- Normal background traffic (no conflicts) ----
        orbits = [
            (0.30, 45.0, 2_500.0, 75.0, 0.0),
            (-0.20, 200.0, 4_000.0, 120.0, -1.0),
            (0.10, 315.0, 6_000.0, 220.0, 2.0),
            (-0.35, 130.0, 8_000.0, 250.0, 0.0),
        ]
        for i, (r, track, alt, spd, vr) in enumerate(orbits):
            angle = math.radians(elapsed * 0.05 + i * 90)
            lat = clat + r * math.cos(angle)
            lon = clon + r * math.sin(angle)
            aircraft.append(AircraftState(
                icao24=f"mock{5+i:03d}",
                callsign=self.MOCK_CALLSIGNS[4 + i],
                latitude=lat, longitude=lon,
                baro_altitude=alt, geo_altitude=alt + 20,
                on_ground=False, velocity=spd,
                true_track=(track + elapsed * 0.1) % 360,
                vertical_rate=vr,
            ))

        return aircraft


# ---------------------------------------------------------------------------
# OpenSky Poller
# ---------------------------------------------------------------------------
class OpenSkyPoller:
    """
    Asynchronous OpenSky ADS-B state-vector poller.

    Behaviour:
    - Polls every `poll_interval_seconds` (default 120 s).
    - On HTTP 429, triggers exponential backoff (60 s → 120 s → 300 s).
    - Automatically falls back to `MockAircraftGenerator` when:
        a) Credentials are absent
        b) Three consecutive real-API failures occur
    - The last received state is cached and returned to the WebSocket
      broadcaster between poll intervals (zero extra API calls).
    """

    _MAX_CONSECUTIVE_FAILURES = 3
    _BACKOFF_SEQUENCE = [60, 120, 300]  # seconds

    def __init__(self) -> None:
        self._settings = get_settings()
        self._token_manager = TokenManager(self._settings)
        self._mock_gen = MockAircraftGenerator()
        self._client: Optional[httpx.AsyncClient] = None

        self._cached_aircraft: list[AircraftState] = []
        self._data_source: str = "initializing"
        self._consecutive_failures: int = 0
        self._using_mock: bool = False

        # Rate-limit tracking (informational — for /health endpoint)
        self._polls_today: int = 0
        self._last_poll_at: Optional[float] = None
        self._next_poll_at: Optional[float] = None

        self._lock = asyncio.Lock()
        self._poll_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def start(self, airport_code: Optional[str] = None) -> None:
        """Start the background polling loop."""
        self._client = httpx.AsyncClient(timeout=20.0)
        await self._token_manager.start(self._client)

        if not self._settings.has_opensky_credentials:
            logger.warning(
                "OpenSky credentials not configured — using mock aircraft generator"
            )
            self._using_mock = True
            self._data_source = "mock"

        self._poll_task = asyncio.create_task(
            self._poll_loop(airport_code or self._settings.active_airport_code),
            name="opensky_poll_loop",
        )
        logger.info(
            "OpenSkyPoller started (interval=%ds, mock=%s)",
            self._settings.opensky_poll_interval_seconds,
            self._using_mock,
        )

    async def stop(self) -> None:
        """Cancel the polling loop and close the HTTP client."""
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        if self._client:
            await self._client.aclose()
        logger.info("OpenSkyPoller stopped")

    # ------------------------------------------------------------------
    # Public API (called by WebSocket broadcaster every 2 s)
    # ------------------------------------------------------------------
    async def get_aircraft(self, airport_code: str) -> tuple[list[AircraftState], str]:
        """
        Return the last cached aircraft list and data source label.
        Never blocks on network I/O — always returns immediately.
        """
        async with self._lock:
            if self._using_mock or not self._cached_aircraft:
                return (
                    self._mock_gen.generate(airport_code, self._settings),
                    "mock",
                )
            return list(self._cached_aircraft), self._data_source

    @property
    def rate_info(self) -> dict:
        """Rate-limit counters for the /health endpoint."""
        return {
            "opensky_polls_today": self._polls_today,
            "last_poll_at": self._last_poll_at,
            "next_poll_at": self._next_poll_at,
            "data_source": self._data_source,
            "using_mock": self._using_mock,
        }

    # ------------------------------------------------------------------
    # Polling loop
    # ------------------------------------------------------------------
    async def _poll_loop(self, airport_code: str) -> None:
        interval = self._settings.opensky_poll_interval_seconds
        backoff_index = 0

        while True:
            wait = interval
            try:
                if not self._using_mock:
                    aircraft = await self._fetch(airport_code)
                    async with self._lock:
                        self._cached_aircraft = aircraft
                        self._consecutive_failures = 0
                        self._data_source = "opensky_live"
                        self._last_poll_at = time.time()
                        self._next_poll_at = time.time() + interval
                        self._polls_today += 1
                        backoff_index = 0
                    logger.info(
                        "OpenSky poll OK — %d aircraft in %s zone (polls today: %d)",
                        len(aircraft),
                        airport_code,
                        self._polls_today,
                    )
            except _RateLimitError:
                # Exponential backoff on 429
                wait = self._BACKOFF_SEQUENCE[min(backoff_index, len(self._BACKOFF_SEQUENCE) - 1)]
                backoff_index += 1
                self._consecutive_failures += 1
                logger.warning(
                    "OpenSky rate limited (429). Backing off %d s "
                    "(failure streak: %d)",
                    wait,
                    self._consecutive_failures,
                )
                if self._consecutive_failures >= self._MAX_CONSECUTIVE_FAILURES:
                    logger.warning(
                        "Too many consecutive failures — switching to mock generator"
                    )
                    self._using_mock = True
                    self._data_source = "mock"
            except Exception as exc:  # noqa: BLE001
                self._consecutive_failures += 1
                logger.error("OpenSky poll error: %s", exc)
                if self._consecutive_failures >= self._MAX_CONSECUTIVE_FAILURES:
                    logger.warning(
                        "Switching to mock generator after %d consecutive failures",
                        self._consecutive_failures,
                    )
                    self._using_mock = True
                    self._data_source = "mock"

            await asyncio.sleep(wait)

    # ------------------------------------------------------------------
    # HTTP fetch
    # ------------------------------------------------------------------
    async def _fetch(self, airport_code: str) -> list[AircraftState]:
        """Fetch state vectors from OpenSky for the airport bounding box."""
        bbox = self._settings.compute_bounding_box(airport_code)
        token = await self._token_manager.get_valid_token()

        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        params = {
            "lamin": bbox["lamin"],
            "lomin": bbox["lomin"],
            "lamax": bbox["lamax"],
            "lomax": bbox["lomax"],
        }

        resp = await self._client.get(
            self._settings.opensky_api_url,
            params=params,
            headers=headers,
        )

        if resp.status_code == 429:
            raise _RateLimitError("HTTP 429 — rate limited by OpenSky")

        resp.raise_for_status()
        payload = resp.json()
        return self._parse_states(payload)

    @staticmethod
    def _parse_states(payload: dict) -> list[AircraftState]:
        """
        Parse the OpenSky /states/all response.

        State vector array indices:
          0: icao24, 1: callsign, 5: longitude, 6: latitude,
          7: baro_altitude, 8: on_ground, 9: velocity,
          10: true_track, 11: vertical_rate, 13: geo_altitude
        """
        states = payload.get("states") or []
        result = []
        for sv in states:
            if not isinstance(sv, list) or len(sv) < 14:
                continue
            # Skip aircraft with no position
            if sv[5] is None or sv[6] is None:
                continue
            result.append(AircraftState(
                icao24=str(sv[0] or ""),
                callsign=str(sv[1] or "").strip() or str(sv[0] or ""),
                longitude=sv[5],
                latitude=sv[6],
                baro_altitude=sv[7],
                geo_altitude=sv[13],
                on_ground=bool(sv[8]),
                velocity=sv[9],
                true_track=sv[10],
                vertical_rate=sv[11],
            ))
        return result


# ---------------------------------------------------------------------------
# Internal sentinel exception
# ---------------------------------------------------------------------------
class _RateLimitError(Exception):
    """Raised when OpenSky returns HTTP 429."""
