"""
services/weather_service.py
============================
OpenWeatherMap integration with a TTL cache.

Rate budget:
  - Default cache TTL = 300 seconds (5 minutes)
  - Maximum calls per day ≈ 86,400 / 300 = 288 req/day
  - This preserves the bulk of the 1,000 req/day quota for OpenSky polling.

If the API key is missing or the request fails, returns a safe default
weather payload so the collision engine can still operate.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from math import cos, radians, sin
from typing import Optional

import httpx

from config.settings import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class WeatherData:
    """Parsed weather snapshot for an airport."""

    airport_code: str
    wind_speed: float = 0.0          # m/s
    wind_deg: float = 0.0            # meteorological degrees (FROM direction)
    visibility: float = 10_000.0     # metres
    condition: str = "Clear"         # e.g. "Rain", "Snow", "Thunderstorm", "Clear"
    temperature_c: float = 20.0
    fetched_at: float = field(default_factory=time.monotonic)

    @property
    def wind_vector(self) -> tuple[float, float]:
        """
        Decompose wind into (wx, wy) ground-plane drift components (m/s).

        Meteorological wind direction is the direction the wind blows FROM.
        We negate to get the direction the wind pushes aircraft TOWARD.

        Returns:
            (wx, wy) where wx is East-component, wy is North-component.
        """
        bearing_rad = radians(self.wind_deg)
        wx = -self.wind_speed * sin(bearing_rad)
        wy = -self.wind_speed * cos(bearing_rad)
        return wx, wy

    @property
    def is_precipitation(self) -> bool:
        """True if current condition involves any form of precipitation."""
        precip_conditions = {"Rain", "Drizzle", "Snow", "Sleet", "Thunderstorm"}
        return any(c.lower() in self.condition.lower() for c in precip_conditions)

    def to_dict(self) -> dict:
        wx, wy = self.wind_vector
        return {
            "airport_code": self.airport_code,
            "wind_speed": round(self.wind_speed, 2),
            "wind_deg": round(self.wind_deg, 1),
            "wind_vector_east": round(wx, 3),
            "wind_vector_north": round(wy, 3),
            "visibility_m": round(self.visibility, 0),
            "condition": self.condition,
            "temperature_c": round(self.temperature_c, 1),
            "is_precipitation": self.is_precipitation,
        }


def _safe_default_weather(airport_code: str) -> WeatherData:
    """Return a neutral weather snapshot used when the API is unavailable."""
    return WeatherData(airport_code=airport_code)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
class WeatherService:
    """
    Fetches and caches weather data from OpenWeatherMap.

    Thread-safe via asyncio.Lock. Cache TTL is configurable via settings
    (default 300 s). If credentials are absent the service returns safe
    defaults without making any network calls.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._cache: dict[str, WeatherData] = {}
        self._lock = asyncio.Lock()
        self._client: Optional[httpx.AsyncClient] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def start(self) -> None:
        """Create the shared HTTP client."""
        self._client = httpx.AsyncClient(timeout=10.0)
        logger.info("WeatherService started (TTL=%ds)", self._settings.openweather_cache_ttl_seconds)

    async def stop(self) -> None:
        """Close the shared HTTP client."""
        if self._client:
            await self._client.aclose()
            logger.info("WeatherService stopped")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def get_weather(self, airport_code: str) -> WeatherData:
        """
        Return weather for an airport, using the cache when still valid.

        If the API key is absent, returns safe defaults immediately without
        consuming any quota.
        """
        if not self._settings.has_openweather_key:
            logger.debug("No OpenWeatherMap key configured — returning default weather")
            return _safe_default_weather(airport_code)

        async with self._lock:
            cached = self._cache.get(airport_code)
            ttl = self._settings.openweather_cache_ttl_seconds

            if cached and (time.monotonic() - cached.fetched_at) < ttl:
                logger.debug(
                    "Weather cache hit for %s (age=%.0fs)",
                    airport_code,
                    time.monotonic() - cached.fetched_at,
                )
                return cached

            # Cache miss — fetch from API
            data = await self._fetch(airport_code)
            self._cache[airport_code] = data
            return data

    # ------------------------------------------------------------------
    # Internal fetch
    # ------------------------------------------------------------------
    async def _fetch(self, airport_code: str) -> WeatherData:
        """Make a live request to OpenWeatherMap. Returns safe defaults on error."""
        try:
            airport = self._settings.get_airport_config(airport_code)
            center = airport["center"]
            lat = center["latitude"]
            lon = center["longitude"]

            params = {
                "lat": lat,
                "lon": lon,
                "appid": self._settings.openweather_api_key,
                "units": "metric",
            }

            resp = await self._client.get(
                self._settings.openweather_base_url,
                params=params,
            )

            if resp.status_code == 200:
                return self._parse(airport_code, resp.json())

            logger.warning(
                "OpenWeatherMap returned HTTP %d for %s — using default weather",
                resp.status_code,
                airport_code,
            )

        except httpx.RequestError as exc:
            logger.warning("WeatherService request error for %s: %s", airport_code, exc)
        except Exception as exc:  # noqa: BLE001
            logger.error("WeatherService unexpected error: %s", exc)

        return _safe_default_weather(airport_code)

    @staticmethod
    def _parse(airport_code: str, payload: dict) -> WeatherData:
        """Extract relevant fields from the OpenWeatherMap API response."""
        wind = payload.get("wind", {})
        weather_list = payload.get("weather", [{}])
        condition = weather_list[0].get("main", "Clear") if weather_list else "Clear"

        return WeatherData(
            airport_code=airport_code,
            wind_speed=float(wind.get("speed", 0.0)),
            wind_deg=float(wind.get("deg", 0.0)),
            visibility=float(payload.get("visibility", 10_000.0)),
            condition=condition,
            temperature_c=float(payload.get("main", {}).get("temp", 20.0)),
            fetched_at=time.monotonic(),
        )
