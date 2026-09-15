"""
config/settings.py
==================
Pydantic-settings model that reads all configuration from the .env file.
Includes the dynamic bounding-box calculator for the Omni-Zone geofence.

No hard-coded secrets or coordinates. All values come from environment variables
or the airports.json file loaded at runtime.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
CONFIG_DIR = Path(__file__).parent
AIRPORTS_JSON = CONFIG_DIR / "airports.json"
ENV_FILE = Path(__file__).parent.parent.parent / ".env"   # src/.env


# ---------------------------------------------------------------------------
# Settings model
# ---------------------------------------------------------------------------
class Settings(BaseSettings):
    """
    All application settings, sourced from environment variables.
    See src/.env.example for the full list of supported variables.
    """

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Server & Runtime
    # ------------------------------------------------------------------
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    frontend_port: int = 3000
    log_level: str = "info"

    # ------------------------------------------------------------------
    # OpenSky Network
    # ------------------------------------------------------------------
    opensky_client_id: Optional[str] = None
    opensky_client_secret: Optional[str] = None
    opensky_token_url: str = (
        "https://auth.opensky-network.org/auth/realms/opensky-network"
        "/protocol/openid-connect/token"
    )
    opensky_api_url: str = "https://opensky-network.org/api/states/all"

    # Rate limit: 1,000 req/day → safe interval = 120 s → ~720 req/day
    # Leaves ~280 req headroom for token refreshes + retry backoff
    opensky_poll_interval_seconds: int = 120

    # ------------------------------------------------------------------
    # OpenWeatherMap
    # ------------------------------------------------------------------
    openweather_api_key: Optional[str] = None
    openweather_base_url: str = "https://api.openweathermap.org/data/2.5/weather"

    # Cache weather responses for 300 s (5 min) → ~288 req/day
    openweather_cache_ttl_seconds: int = 300

    # ------------------------------------------------------------------
    # Airport Selection
    # ------------------------------------------------------------------
    active_airport_code: str = "DEL"

    # ------------------------------------------------------------------
    # Collision Safety Parameters
    # ------------------------------------------------------------------
    prediction_horizon_seconds: int = 60

    # 3.0 NM converted to metres: 1 NM = 1,852 m
    airborne_min_horizontal_separation_nm: float = 3.0

    # 1,000 ft converted to metres: 1 ft = 0.3048 m
    airborne_min_vertical_separation_ft: float = 1000.0

    # Ground stopping envelope base distance (metres)
    ground_stopping_base_distance_m: float = 300.0

    # Wet-runway friction multiplier when precipitation is detected
    rain_friction_penalty_factor: float = 1.6

    # Geofence radius used for the dynamic bounding-box calculation
    geofence_radius_km: float = 50.0

    # ------------------------------------------------------------------
    # Derived / computed properties
    # ------------------------------------------------------------------
    @property
    def airborne_min_horizontal_separation_m(self) -> float:
        """3.0 NM → metres."""
        return self.airborne_min_horizontal_separation_nm * 1_852.0

    @property
    def airborne_min_vertical_separation_m(self) -> float:
        """1,000 ft → metres."""
        return self.airborne_min_vertical_separation_ft * 0.3048

    @property
    def has_opensky_credentials(self) -> bool:
        """True only when both OpenSky OAuth2 credentials are non-empty."""
        return bool(
            self.opensky_client_id
            and self.opensky_client_secret
            and self.opensky_client_id not in ("your_opensky_client_id_here", "")
            and self.opensky_client_secret not in ("your_opensky_client_secret_here", "")
        )

    @property
    def has_openweather_key(self) -> bool:
        """True only when the OpenWeatherMap API key is non-empty."""
        return bool(
            self.openweather_api_key
            and self.openweather_api_key not in ("your_openweather_api_key_here", "")
        )

    # ------------------------------------------------------------------
    # Airport helpers
    # ------------------------------------------------------------------
    def load_airports(self) -> dict:
        """Load and return the full airports.json as a dict."""
        with open(AIRPORTS_JSON, encoding="utf-8") as f:
            return json.load(f)

    def get_airport_config(self, code: Optional[str] = None) -> dict:
        """Return the config block for a given airport code (defaults to active)."""
        airports = self.load_airports()
        target = (code or self.active_airport_code).upper()
        if target not in airports:
            raise ValueError(
                f"Unknown airport code '{target}'. "
                f"Valid codes: {list(airports.keys())}"
            )
        return airports[target]

    def compute_bounding_box(self, code: Optional[str] = None) -> dict:
        """
        Dynamically compute the lat/lon bounding box for the Omni-Zone geofence.

        Given airport center (Lat, Lon) and radius R (km):
            ΔLat = R / 111.0
            ΔLon = R / (111.0 × cos(radians(Lat)))
            lamin = Lat - ΔLat
            lamax = Lat + ΔLat
            lomin = Lon - ΔLon
            lomax = Lon + ΔLon

        Returns:
            dict with keys: lamin, lamax, lomin, lomax, center_lat, center_lon
        """
        airport = self.get_airport_config(code)
        center = airport["center"]
        lat = center["latitude"]
        lon = center["longitude"]

        # Use the airport-specific radius if defined, else fall back to settings value
        radius_km = float(airport.get("geofence_radius_km", self.geofence_radius_km))

        delta_lat = radius_km / 111.0
        delta_lon = radius_km / (111.0 * math.cos(math.radians(lat)))

        return {
            "lamin": round(lat - delta_lat, 6),
            "lamax": round(lat + delta_lat, 6),
            "lomin": round(lon - delta_lon, 6),
            "lomax": round(lon + delta_lon, 6),
            "center_lat": lat,
            "center_lon": lon,
            "radius_km": radius_km,
        }


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings singleton. Reads .env once per process."""
    return Settings()
