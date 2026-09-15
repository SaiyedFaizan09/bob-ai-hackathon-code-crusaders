"""
engine/collision_engine.py
===========================
Kinematic collision and runway incursion detection engine.

This module is **pure mathematics** — no I/O, no network calls.
It consumes a list of AircraftState objects plus a WeatherData snapshot
and returns enriched aircraft (with status flags and trajectory projections)
plus a list of active Alert objects.

═══════════════════════════════════════════════════════════════════════════════
PHYSICS NOTES (critical — read before modifying)
═══════════════════════════════════════════════════════════════════════════════

1. GROUND-SPEED VECTORS
   OpenSky state vector[9]  = velocity  → Ground Speed (m/s), already
   wind-corrected by the aircraft's own navigation system.
   OpenSky state vector[10] = true_track → Track Over Ground (degrees).
   Wind drift is therefore ALREADY embedded in these values.
   Adding meteorological (wx, wy) again would double-count the drift.
   → _velocity_components() uses ground-speed decomposition only.

2. CYLINDRICAL AIRSPACE SEPARATION (ICAO Doc 4444)
   Aviation separation is NOT 3-D spherical. It is cylindrical:
     Horizontal  ≥ 3.0 NM  (5 556 m)  — evaluated on the 2-D ground plane
     Vertical    ≥ 1 000 ft (304.8 m)  — evaluated independently
   Coupling horizontal and vertical in a single 3-D dot product distorts
   t_CPA because vertical rates (10–20 m/s) dominate over lateral closure
   rates of similar magnitude, producing wrong timestamps.
   → _check_airborne() decouples horizontal t_CPA from vertical separation.

3. STOPPING DISTANCE PHYSICS
   Classical kinematics: d = v² / (2·a)
   Baseline deceleration (dry): a_base = 1.8 m/s²
   Wet/icy runway: a_eff  = a_base / µ_wet  (µ_wet = 1.6 → a_eff ≈ 1.125)
   The old "300 × (v/10)²" formula yielded ~14.7 km at 70 m/s — engulfing
   an entire airport in a false bubble.

4. FORWARD-PROJECTING GROUND ENVELOPES
   Aircraft cannot stop *behind* themselves. The safety perimeter must be
   centred ahead of the aircraft along its track, not omnidirectionally.
   Omnidirectional circles trigger false alerts on queued trailing traffic.

5. POINT-TO-LINE-SEGMENT RUNWAY GEOMETRY
   Runways are 3–4 km long × ~45 m wide. A single centroid misses
   threshold incursions (2 km away) and false-triggers on parked aircraft
   near the centre. The runway is modelled as the segment between its
   first and last polygon vertices, with a half-width buffer of 30 m.
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from services.opensky_service import AircraftState
from services.weather_service import WeatherData


# ─────────────────────────────────────────────────────────────────────────────
# Physical constants
# ─────────────────────────────────────────────────────────────────────────────
_NM_TO_M: float = 1_852.0          # 1 nautical mile → metres
_FT_TO_M: float = 0.3048           # 1 foot → metres
_DEG_LAT_TO_M: float = 111_000.0   # metres per degree of latitude (approx)

# Ground stopping physics
_A_BASE_DRY: float = 1.8           # m/s²  — dry runway deceleration
_MU_WET: float = 1.6               # friction reduction factor when raining
_D_STOP_MIN: float = 25.0          # m     — minimum safety perimeter radius
_R_BUBBLE_MIN: float = 20.0        # m     — minimum forward-bubble radius

# Runway geometry
_HALF_RUNWAY_WIDTH: float = 30.0   # m     — half-width of runway strip


# ─────────────────────────────────────────────────────────────────────────────
# Data models
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Alert:
    """A detected conflict event."""

    alert_type: str                 # "MID_AIR_COLLISION" | "RUNWAY_INCURSION"
    aircraft_a_id: str              # icao24 of first aircraft
    aircraft_b_id: str              # icao24 of second aircraft
    aircraft_a_callsign: str
    aircraft_b_callsign: str
    t_cpa_seconds: float            # Time to horizontal closest approach (s)
    horizontal_sep_m: float         # Projected horizontal separation at t_CPA
    vertical_sep_m: float           # Projected vertical separation at t_CPA
    resolution_advisory_a: str      # RA text for aircraft A
    resolution_advisory_b: str      # RA text for aircraft B
    conflict_lat: Optional[float] = None   # Approximate conflict location
    conflict_lon: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "type": self.alert_type,
            "aircraft_a": self.aircraft_a_id,
            "aircraft_b": self.aircraft_b_id,
            "callsign_a": self.aircraft_a_callsign,
            "callsign_b": self.aircraft_b_callsign,
            "t_cpa_seconds": round(self.t_cpa_seconds, 1),
            "horizontal_sep_m": round(self.horizontal_sep_m, 1),
            "vertical_sep_m": round(self.vertical_sep_m, 1),
            "resolution_advisory_a": self.resolution_advisory_a,
            "resolution_advisory_b": self.resolution_advisory_b,
            "conflict_lat": self.conflict_lat,
            "conflict_lon": self.conflict_lon,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Coordinate helpers
# ─────────────────────────────────────────────────────────────────────────────
def _geo_to_xy(
    lat: float,
    lon: float,
    ref_lat: float,
    ref_lon: float,
) -> tuple[float, float]:
    """
    Convert (lat, lon) → (x, y) in metres relative to a reference point.
    Uses the equirectangular (flat-Earth) approximation, valid for < 100 km.

    x → East component
    y → North component
    """
    deg_lon_to_m = _DEG_LAT_TO_M * math.cos(math.radians(ref_lat))
    x = (lon - ref_lon) * deg_lon_to_m
    y = (lat - ref_lat) * _DEG_LAT_TO_M
    return x, y


def _xy_to_geo(
    x: float,
    y: float,
    ref_lat: float,
    ref_lon: float,
) -> tuple[float, float]:
    """Inverse of _geo_to_xy. Returns (lat, lon)."""
    deg_lon_to_m = _DEG_LAT_TO_M * math.cos(math.radians(ref_lat))
    lat = ref_lat + y / _DEG_LAT_TO_M
    lon = ref_lon + (x / deg_lon_to_m if deg_lon_to_m > 1e-9 else 0.0)
    return lat, lon


# ─────────────────────────────────────────────────────────────────────────────
# Geometry helpers
# ─────────────────────────────────────────────────────────────────────────────
def _point_to_segment_distance(
    px: float, py: float,
    x1: float, y1: float,
    x2: float, y2: float,
) -> float:
    """
    Minimum distance from point P=(px, py) to the finite line segment AB.

    Algorithm:
        AB = B − A
        AP = P − A
        t  = clamp(AP·AB / |AB|², 0, 1)
        C  = A + t·AB          ← closest point on segment
        distance = |P − C|
    """
    ab_x = x2 - x1
    ab_y = y2 - y1
    ab_sq = ab_x * ab_x + ab_y * ab_y

    if ab_sq < 1e-9:
        # Degenerate segment — treat as point A
        return math.hypot(px - x1, py - y1)

    ap_x = px - x1
    ap_y = py - y1

    t = (ap_x * ab_x + ap_y * ab_y) / ab_sq
    t = max(0.0, min(1.0, t))               # clamp to [0, 1]

    cx = x1 + t * ab_x
    cy = y1 + t * ab_y
    return math.hypot(px - cx, py - cy)


# ─────────────────────────────────────────────────────────────────────────────
# Velocity decomposition
# ─────────────────────────────────────────────────────────────────────────────
def _velocity_components(ac: AircraftState) -> tuple[float, float, float]:
    """
    Decompose aircraft motion into Cartesian ground-plane components (m/s).

    OpenSky `velocity`   = Ground Speed (m/s)  — already wind-corrected.
    OpenSky `true_track` = Track Over Ground   — already wind-corrected.
    Wind drift must NOT be re-added here; it is already embedded.

    Returns:
        (vx, vy, vz)
        vx → East  component  (m/s)
        vy → North component  (m/s)
        vz → Up    component  (m/s, positive = climb)
    """
    speed: float = ac.velocity or 0.0
    track_rad: float = math.radians(ac.true_track or 0.0)

    vx: float = speed * math.sin(track_rad)   # East
    vy: float = speed * math.cos(track_rad)   # North
    vz: float = ac.vertical_rate or 0.0       # Up (m/s)
    return vx, vy, vz


# ─────────────────────────────────────────────────────────────────────────────
# Stopping distance
# ─────────────────────────────────────────────────────────────────────────────
def _stopping_distance(speed_ms: float, is_precipitation: bool) -> float:
    """
    Compute kinematic stopping distance using constant-deceleration model.

        d_stop = v² / (2 · a_eff)

    Dry runway:  a_eff = a_base = 1.8 m/s²
    Wet runway:  a_eff = a_base / µ_wet  (µ_wet=1.6 → a_eff ≈ 1.125 m/s²)

    Result is clamped to a minimum of 25 m (safety perimeter).

    Examples:
        70 m/s dry  → 1 361 m  (vs the old formula's 14.7 km — ✓ realistic)
        25 m/s wet  → 277 m
         5 m/s dry  →  6.9 m  → clamped to 25 m
    """
    a_eff: float = _A_BASE_DRY / _MU_WET if is_precipitation else _A_BASE_DRY
    raw: float = (speed_ms ** 2) / (2.0 * a_eff)
    return max(raw, _D_STOP_MIN)


# ─────────────────────────────────────────────────────────────────────────────
# Forward-projecting ground envelope
# ─────────────────────────────────────────────────────────────────────────────
def _forward_bubble(
    x: float,
    y: float,
    track_deg: float,
    d_stop: float,
) -> tuple[float, float, float]:
    """
    Compute the centre and radius of the forward-projecting stopping envelope.

    The bubble centre is offset ahead of the aircraft by d_stop/2 along its
    track vector.  Radius = max(d_stop/2, _R_BUBBLE_MIN).

    Returns:
        (cx, cy, radius)  all in metres
    """
    theta: float = math.radians(track_deg)
    offset: float = d_stop / 2.0
    cx: float = x + offset * math.sin(theta)
    cy: float = y + offset * math.cos(theta)
    radius: float = max(offset, _R_BUBBLE_MIN)
    return cx, cy, radius


# ─────────────────────────────────────────────────────────────────────────────
# Main engine
# ─────────────────────────────────────────────────────────────────────────────
class CollisionEngine:
    """
    Stateless kinematic collision and runway-incursion detection engine.

    Call `run()` each data cycle. The method mutates `aircraft_list` in-place
    (setting `status` and `trajectory`) then returns active Alert objects.
    """

    def __init__(self, settings) -> None:
        self._settings = settings

    # ─────────────────────────────────────────────────────────────────────
    # Public entry point
    # ─────────────────────────────────────────────────────────────────────
    def run(
        self,
        aircraft_list: list[AircraftState],
        weather: WeatherData,
        airport_config: dict,
    ) -> list[Alert]:
        """
        Execute one detection cycle.

        Args:
            aircraft_list:  AircraftState objects — mutated in-place.
            weather:        Current weather snapshot (used for friction only).
            airport_config: Dict from airports.json (for runway geometry).

        Returns:
            List of Alert objects for all active conflicts found.
        """
        # Reset status to NORMAL and clear stale trajectories
        for ac in aircraft_list:
            ac.status = "NORMAL"
            ac.trajectory = []

        if not aircraft_list:
            return []

        # Use the first aircraft with a valid position as the Cartesian origin
        origin = next(
            (ac for ac in aircraft_list if ac.latitude and ac.longitude),
            None,
        )
        if origin is None:
            return []

        ref_lat: float = origin.latitude   # type: ignore[assignment]
        ref_lon: float = origin.longitude  # type: ignore[assignment]

        # Build trajectory projections (T+15s, T+30s, T+60s) for all airborne
        self._build_trajectories(aircraft_list, ref_lat, ref_lon)

        alerts: list[Alert] = []

        # ── Airborne pair-wise check ──────────────────────────────────────
        airborne = [
            ac for ac in aircraft_list
            if not ac.on_ground
            and ac.latitude is not None
            and ac.longitude is not None
        ]
        alerts.extend(self._check_airborne(airborne, weather, ref_lat, ref_lon))

        # ── Ground / runway check ─────────────────────────────────────────
        ground = [
            ac for ac in aircraft_list
            if ac.on_ground
            and ac.latitude is not None
            and ac.longitude is not None
        ]
        alerts.extend(
            self._check_ground(ground, aircraft_list, weather, airport_config, ref_lat, ref_lon)
        )

        return alerts

    # ─────────────────────────────────────────────────────────────────────
    # Trajectory builder
    # ─────────────────────────────────────────────────────────────────────
    def _build_trajectories(
        self,
        aircraft_list: list[AircraftState],
        ref_lat: float,
        ref_lon: float,
    ) -> None:
        """
        Pre-compute projected positions at T+15s, T+30s, T+60s for each
        airborne aircraft.  Ground-speed decomposition only; no wind offset.
        """
        for ac in aircraft_list:
            if ac.on_ground or ac.latitude is None or ac.longitude is None:
                continue
            if ac.velocity is None and ac.vertical_rate is None:
                continue

            vx, vy, vz = _velocity_components(ac)
            x0, y0 = _geo_to_xy(ac.latitude, ac.longitude, ref_lat, ref_lon)
            z0: float = ac.baro_altitude or 0.0
            points: list[dict] = []

            for t in (15, 30, 60):
                plat, plon = _xy_to_geo(x0 + vx * t, y0 + vy * t, ref_lat, ref_lon)
                points.append({
                    "t": t,
                    "lat": round(plat, 6),
                    "lon": round(plon, 6),
                    "alt": round(max(0.0, z0 + vz * t), 1),
                })

            ac.trajectory = points

    # ─────────────────────────────────────────────────────────────────────
    # Airborne conflict detection — cylindrical separation
    # ─────────────────────────────────────────────────────────────────────
    def _check_airborne(
        self,
        airborne: list[AircraftState],
        weather: WeatherData,
        ref_lat: float,
        ref_lon: float,
    ) -> list[Alert]:
        """
        Pairwise horizontal t_CPA computation with independent vertical check.

        Algorithm (Bug #2 fix — cylindrical separation):
          1. Compute 2-D relative position (Δpx, Δpy) and velocity (Δvx, Δvy)
             in the horizontal ground plane.
          2. Minimise horizontal distance only:
               t_CPA_horiz = -(Δpx·Δvx + Δpy·Δvy) / (Δvx²+Δvy²)
          3. At that t_CPA_horiz, independently evaluate:
               d_horiz = sqrt((Δpx+Δvx·t)²+(Δpy+Δvy·t)²)
               d_vert  = |Δpz + Δvz·t|
          4. Alert iff d_horiz < 5 556 m AND d_vert < 304.8 m.

        Wind (wx, wy) is NOT added to velocities — ground-speed vectors are
        already wind-corrected by the aircraft's own navigation system.
        """
        alerts: list[Alert] = []
        horizon: float = float(self._settings.prediction_horizon_seconds)
        h_thresh: float = self._settings.airborne_min_horizontal_separation_m
        v_thresh: float = self._settings.airborne_min_vertical_separation_m

        if len(airborne) < 2:
            return alerts

        # Build Cartesian state vectors for all airborne aircraft
        vectors: list[tuple[float, float, float, float, float, float, AircraftState]] = []
        for ac in airborne:
            vx, vy, vz = _velocity_components(ac)
            x, y = _geo_to_xy(ac.latitude, ac.longitude, ref_lat, ref_lon)  # type: ignore[arg-type]
            z: float = ac.baro_altitude or 0.0
            vectors.append((x, y, z, vx, vy, vz, ac))

        for i in range(len(vectors)):
            for j in range(i + 1, len(vectors)):
                xi, yi, zi, vxi, vyi, vzi, ac_i = vectors[i]
                xj, yj, zj, vxj, vyj, vzj, ac_j = vectors[j]

                # ── Step 1: 2-D horizontal relative vectors ───────────────
                dpx: float = xj - xi
                dpy: float = yj - yi
                dpz: float = zj - zi

                dvx: float = vxj - vxi
                dvy: float = vyj - vyi
                dvz: float = vzj - vzi

                # ── Step 2: horizontal t_CPA ──────────────────────────────
                dv_horiz_sq: float = dvx * dvx + dvy * dvy

                if dv_horiz_sq < 1e-6:
                    # Aircraft moving at identical horizontal velocity —
                    # check current separation directly (t_CPA = 0)
                    t_cpa: float = 0.0
                else:
                    t_cpa = -(dpx * dvx + dpy * dvy) / dv_horiz_sq

                # Reject if CPA is in the past or beyond the prediction horizon
                if t_cpa < 0.0 or t_cpa > horizon:
                    continue

                # ── Step 3: evaluate separation at t_CPA ─────────────────
                sep_px: float = dpx + dvx * t_cpa
                sep_py: float = dpy + dvy * t_cpa
                d_horiz: float = math.sqrt(sep_px * sep_px + sep_py * sep_py)

                d_vert: float = abs(dpz + dvz * t_cpa)

                # ── Step 4: trigger if BOTH thresholds are breached ───────
                if d_horiz < h_thresh and d_vert < v_thresh:
                    # Approximate conflict midpoint (for map badge placement)
                    mid_x: float = (xi + vxi * t_cpa + xj + vxj * t_cpa) / 2.0
                    mid_y: float = (yi + vyi * t_cpa + yj + vyj * t_cpa) / 2.0
                    clat, clon = _xy_to_geo(mid_x, mid_y, ref_lat, ref_lon)

                    alert = _make_airborne_alert(
                        ac_i, ac_j, t_cpa, d_horiz, d_vert, clat, clon
                    )
                    alerts.append(alert)
                    ac_i.status = "COLLISION"
                    ac_j.status = "COLLISION"

        return alerts

    # ─────────────────────────────────────────────────────────────────────
    # Ground conflict detection — forward envelopes + runway line segments
    # ─────────────────────────────────────────────────────────────────────
    def _check_ground(
        self,
        ground: list[AircraftState],
        all_aircraft: list[AircraftState],
        weather: WeatherData,
        airport_config: dict,
        ref_lat: float,
        ref_lon: float,
    ) -> list[Alert]:
        """
        Two-part ground safety check:

        A. Ground–Ground envelope overlap:
           Each aircraft gets a forward-projecting bubble centred ahead of it.
           If two bubbles overlap → RUNWAY_INCURSION.

        B. Ground–Lander runway intrusion:
           For each runway (modelled as a line segment between its first and
           last polygon vertices), check whether any ground aircraft's bubble
           breaches the runway half-width while an inbound aircraft is below
           500 m AGL and within 3 km of the runway threshold.
        """
        alerts: list[Alert] = []
        if not ground:
            return alerts

        is_precip: bool = weather.is_precipitation
        runways: list[dict] = airport_config.get("runways", [])

        # ── Build forward-bubble geometry for all ground aircraft ─────────
        bubbles: list[tuple[float, float, float, float, AircraftState]] = []
        # Each entry: (x_orig, y_orig, bubble_cx, bubble_cy, radius, ac)
        envelope_data: list[tuple[float, float, float, float, float, AircraftState]] = []

        for ac in ground:
            speed: float = ac.velocity or 0.0
            track: float = ac.true_track or 0.0
            d_stop: float = _stopping_distance(speed, is_precip)
            x, y = _geo_to_xy(ac.latitude, ac.longitude, ref_lat, ref_lon)   # type: ignore[arg-type]
            cx, cy, r = _forward_bubble(x, y, track, d_stop)
            envelope_data.append((x, y, cx, cy, r, ac))

        # ── A. Ground–Ground bubble overlap ──────────────────────────────
        for i in range(len(envelope_data)):
            for j in range(i + 1, len(envelope_data)):
                xi, yi, cxi, cyi, ri, ac_i = envelope_data[i]
                xj, yj, cxj, cyj, rj, ac_j = envelope_data[j]

                bubble_dist: float = math.hypot(cxj - cxi, cyj - cyi)
                if bubble_dist < (ri + rj):
                    # Report true aircraft-to-aircraft distance, not bubble-centre distance
                    true_dist: float = math.hypot(xj - xi, yj - yi)
                    alerts.append(_make_incursion_alert(ac_i, ac_j, true_dist))
                    ac_i.status = "INCURSION"
                    ac_j.status = "INCURSION"

        # ── B. Runway intrusion while lander is on approach ───────────────
        # Identify inbound aircraft: airborne, below 500 m AGL, speed > 40 m/s
        landers: list[AircraftState] = [
            ac for ac in all_aircraft
            if not ac.on_ground
            and ac.baro_altitude is not None
            and ac.baro_altitude < 500.0
            and (ac.velocity or 0.0) > 40.0
            and ac.latitude is not None
            and ac.longitude is not None
        ]

        for rwy in runways:
            coords: list[list[float]] = rwy.get("coordinates", [])
            if len(coords) < 2:
                continue

            # Runway is modelled as the segment: threshold_A → threshold_B
            # Use the first and last coordinate pairs as the two thresholds
            th_a = coords[0]    # [lat, lon]
            th_b = coords[-1]   # [lat, lon]

            ax, ay = _geo_to_xy(th_a[0], th_a[1], ref_lat, ref_lon)
            bx, by = _geo_to_xy(th_b[0], th_b[1], ref_lat, ref_lon)

            # Runway length = distance between thresholds
            rwy_len: float = math.hypot(bx - ax, by - ay)
            # Threshold proximity limit: 3 km from the near threshold
            _LANDER_PROXIMITY_M = 3_000.0

            for lander in landers:
                lx, ly = _geo_to_xy(lander.latitude, lander.longitude, ref_lat, ref_lon)  # type: ignore[arg-type]
                # Distance from lander to the nearest runway threshold
                dist_to_th_a: float = math.hypot(lx - ax, ly - ay)
                dist_to_th_b: float = math.hypot(lx - bx, ly - by)
                if min(dist_to_th_a, dist_to_th_b) > _LANDER_PROXIMITY_M:
                    continue   # Lander is too far from this runway

                # Check each ground aircraft envelope against runway centreline
                for gx, gy, cxi, cyi, ri, gac in envelope_data:
                    if gac.status == "INCURSION":
                        continue   # Already flagged — skip to avoid duplicates

                    # Minimum distance from ground bubble centre to runway segment
                    dist_to_rwy: float = _point_to_segment_distance(
                        cxi, cyi, ax, ay, bx, by
                    )

                    if dist_to_rwy < (ri + _HALF_RUNWAY_WIDTH):
                        # Bug 1 fix: report true Euclidean plane-to-plane distance,
                        # NOT the bubble-to-runway-centreline geometry distance.
                        true_dist_m: float = math.hypot(lx - gx, ly - gy)

                        alert = _make_incursion_alert(
                            lander, gac, true_dist_m,
                            lander_is_airborne=True,
                        )
                        alerts.append(alert)
                        # Bug 2 fix: only mark gac here; lander status is set
                        # AFTER the inner loop so a single lander can trigger
                        # alerts against multiple ground aircraft on the runway.
                        gac.status = "INCURSION"

                # Mark lander as INCURSION only if it triggered at least one alert
                # (avoids locking status before the inner loop runs)
                if any(a.aircraft_a_id == lander.icao24 for a in alerts):
                    lander.status = "INCURSION"

        return alerts


# ─────────────────────────────────────────────────────────────────────────────
# Alert factory helpers (module-level, stateless)
# ─────────────────────────────────────────────────────────────────────────────
def _make_airborne_alert(
    ac_i: AircraftState,
    ac_j: AircraftState,
    t_cpa: float,
    h_sep: float,
    v_sep: float,
    conflict_lat: Optional[float] = None,
    conflict_lon: Optional[float] = None,
) -> Alert:
    """
    Build a MID_AIR_COLLISION alert with Resolution Advisories.

    RA assignment rule:
        Higher aircraft  → CLIMB 2 000 ft  (increase vertical separation)
        Lower  aircraft  → TURN RIGHT 30°  (increase horizontal separation)
    """
    alt_i: float = ac_i.baro_altitude or 0.0
    alt_j: float = ac_j.baro_altitude or 0.0

    if alt_i >= alt_j:
        ra_i = f"{ac_i.callsign}: CLIMB 2000 FT IMMEDIATELY"
        ra_j = f"{ac_j.callsign}: TURN RIGHT 30 DEGREES"
    else:
        ra_i = f"{ac_i.callsign}: TURN RIGHT 30 DEGREES"
        ra_j = f"{ac_j.callsign}: CLIMB 2000 FT IMMEDIATELY"

    return Alert(
        alert_type="MID_AIR_COLLISION",
        aircraft_a_id=ac_i.icao24,
        aircraft_b_id=ac_j.icao24,
        aircraft_a_callsign=ac_i.callsign,
        aircraft_b_callsign=ac_j.callsign,
        t_cpa_seconds=t_cpa,
        horizontal_sep_m=h_sep,
        vertical_sep_m=v_sep,
        resolution_advisory_a=ra_i,
        resolution_advisory_b=ra_j,
        conflict_lat=conflict_lat,
        conflict_lon=conflict_lon,
    )


def _make_incursion_alert(
    ac_a: AircraftState,
    ac_b: AircraftState,
    dist: float,
    lander_is_airborne: bool = False,
) -> Alert:
    """
    Build a RUNWAY_INCURSION alert with context-aware Resolution Advisories.

    If lander_is_airborne is True:
        ac_a = inbound aircraft on approach  → GO AROUND
        ac_b = ground aircraft on runway     → HOLD SHORT / EXIT RUNWAY
    Otherwise (ground–ground conflict):
        Both aircraft → HOLD SHORT IMMEDIATELY
    """
    if lander_is_airborne:
        ra_a = f"{ac_a.callsign}: GO AROUND IMMEDIATELY — RUNWAY NOT CLEAR"
        ra_b = f"{ac_b.callsign}: EXIT RUNWAY / HOLD SHORT IMMEDIATELY"
    else:
        ra_a = f"{ac_a.callsign}: HOLD SHORT IMMEDIATELY"
        ra_b = f"{ac_b.callsign}: HOLD SHORT IMMEDIATELY"

    return Alert(
        alert_type="RUNWAY_INCURSION",
        aircraft_a_id=ac_a.icao24,
        aircraft_b_id=ac_b.icao24,
        aircraft_a_callsign=ac_a.callsign,
        aircraft_b_callsign=ac_b.callsign,
        t_cpa_seconds=0.0,
        horizontal_sep_m=dist,
        vertical_sep_m=0.0,
        resolution_advisory_a=ra_a,
        resolution_advisory_b=ra_b,
    )
