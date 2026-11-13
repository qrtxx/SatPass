"""Orbit math: SGP4 propagation, observer geometry and pass search.

Pure functions with no FastAPI or store imports, so they can be tested on their own.
Times are Unix timestamps in seconds, angles are degrees.
"""

import math
from collections.abc import Callable
from datetime import datetime, timezone

from sgp4.api import WGS72, Satrec

_EPOCH0 = datetime(1949, 12, 31, tzinfo=timezone.utc)  # SGP4 counts epoch days from here
_XPDOTP = 1440 / (2 * math.pi)  # rev/day -> rad/min
WGS84_A = 6378.137  # km
WGS84_E2 = (1 / 298.257223563) * (2 - 1 / 298.257223563)
COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
STEP_S = 60
PEAK_STEP_S = 10

LookFn = Callable[[float], tuple[float, float] | None]


def build_satrec(sat) -> Satrec:
    """`sat` is anything with the OMM attributes of schemas.Satellite."""
    rec = Satrec()
    rec.sgp4init(
        WGS72,
        "i",
        0,  # satnum is only a label; real catalog numbers no longer fit its 5-digit field
        (sat.EPOCH - _EPOCH0).total_seconds() / 86400,
        sat.BSTAR,
        sat.MEAN_MOTION_DOT / (_XPDOTP * 1440),
        sat.MEAN_MOTION_DDOT / (_XPDOTP * 1440 * 1440),
        sat.ECCENTRICITY,
        math.radians(sat.ARG_OF_PERICENTER),
        math.radians(sat.INCLINATION),
        math.radians(sat.MEAN_ANOMALY),
        sat.MEAN_MOTION / _XPDOTP,
        math.radians(sat.RA_OF_ASC_NODE),
    )
    return rec


def gmst(jd: float) -> float:
    """Greenwich mean sidereal time in radians (IAU 1982, same as satellite.js gstime)."""
    t = (jd - 2451545.0) / 36525.0
    sec = -6.2e-6 * t**3 + 0.093104 * t**2 + (876600 * 3600 + 8640184.812866) * t + 67310.54841
    return math.radians(sec / 240.0) % (2 * math.pi)


def ecef_position(rec: Satrec, ts: float) -> tuple[float, float, float] | None:
    """Earth-fixed position in km, or None when SGP4 fails (e.g. the satellite has decayed)."""
    days, rem = divmod(ts, 86400.0)
    jd, fr = 2440587.5 + days, rem / 86400.0
    err, r, _ = rec.sgp4(jd, fr)
    if err:
        return None
    theta = gmst(jd + fr)
    c, s = math.cos(theta), math.sin(theta)
    return (c * r[0] + s * r[1], -s * r[0] + c * r[1], r[2])


def subpoint(rec: Satrec, ts: float) -> tuple[float, float, float] | None:
    """(latitude, longitude, altitude_km) of the point directly below the satellite."""
    p = ecef_position(rec, ts)
    if p is None:
        return None
    x, y, z = p
    r = math.hypot(x, y)
    lat = math.atan2(z, r)
    for _ in range(20):
        c = 1 / math.sqrt(1 - WGS84_E2 * math.sin(lat) ** 2)
        new_lat = math.atan2(z + WGS84_A * c * WGS84_E2 * math.sin(lat), r)
        if abs(new_lat - lat) < 1e-12:
            break
        lat = new_lat
    altitude = r / math.cos(lat) - WGS84_A * c
    return math.degrees(lat), math.degrees(math.atan2(y, x)), altitude


def observer_view(rec: Satrec, lat: float, lon: float, height_km: float) -> LookFn:
    """Returns look(ts) -> (azimuth, elevation) of the satellite seen from the observer, or None."""
    la, lo = math.radians(lat), math.radians(lon)
    sin_la, cos_la, sin_lo, cos_lo = math.sin(la), math.cos(la), math.sin(lo), math.cos(lo)
    n = WGS84_A / math.sqrt(1 - WGS84_E2 * sin_la**2)
    ox, oy, oz = (n + height_km) * cos_la * cos_lo, (n + height_km) * cos_la * sin_lo, (n * (1 - WGS84_E2) + height_km) * sin_la

    def look(ts: float) -> tuple[float, float] | None:
        p = ecef_position(rec, ts)
        if p is None:
            return None
        rx, ry, rz = p[0] - ox, p[1] - oy, p[2] - oz
        south = sin_la * cos_lo * rx + sin_la * sin_lo * ry - cos_la * rz
        east = -sin_lo * rx + cos_lo * ry
        up = cos_la * cos_lo * rx + cos_la * sin_lo * ry + sin_la * rz
        elevation = math.degrees(math.asin(up / math.sqrt(rx * rx + ry * ry + rz * rz)))
        azimuth = math.degrees(math.atan2(-east, south) + math.pi) % 360
        return azimuth, elevation

    return look


def azimuth_to_compass(deg: float) -> str:
    # int(x + 0.5) rounds halves up; Python's round() would round them to even.
    return COMPASS[int(deg % 360 / 22.5 + 0.5) % 16]


def refine_crossing(elevation_at: Callable[[float], float], a: float, b: float) -> float:
    """Bisects [a, b], where one end is above the horizon and the other is not, down to 1 s."""
    up_at_a = elevation_at(a) > 0
    while b - a > 1:
        mid = (a + b) / 2
        if (elevation_at(mid) > 0) == up_at_a:
            a = mid
        else:
            b = mid
    return (a + b) / 2


def _find_peak(elevation_at: Callable[[float], float], rise: float, set_: float) -> tuple[float, float]:
    best_t, best_el = rise, -90.0
    t = rise
    while t <= set_:
        el = elevation_at(t)
        if el > best_el:
            best_t, best_el = t, el
        t += PEAK_STEP_S
    return best_t, best_el


def find_passes(elevation_at: Callable[[float], float], start: float, end: float, min_elevation: float = 10) -> list[dict]:
    """Scans [start, end] in 60 s steps. Each pass is {rise, set, peak, peak_elevation}.

    shortcut: a pass still in progress at `end` is dropped, and one shorter than 60 s can be missed.
    """
    passes = []
    rise = start if elevation_at(start) > 0 else None
    t = start + STEP_S
    while t <= end:
        up = elevation_at(t) > 0
        if up and rise is None:
            rise = refine_crossing(elevation_at, t - STEP_S, t)
        elif not up and rise is not None:
            set_ = refine_crossing(elevation_at, t - STEP_S, t)
            peak, peak_el = _find_peak(elevation_at, rise, set_)
            if peak_el >= min_elevation:
                passes.append({"rise": rise, "set": set_, "peak": peak, "peak_elevation": peak_el})
            rise = None
        t += STEP_S
    return passes
