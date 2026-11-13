"""Satellite catalog: create, read, update, delete and live position, with the catalog's business rules."""

from datetime import datetime, timedelta, timezone

from app import store
from app.errors import Conflict, NotFound, RuleViolation
from app.schemas import Position, as_utc, Satellite, SatelliteCreate, SatelliteUpdate
from app.services import orbit

# Elements get less accurate with age: warn after 3 days, refuse to predict after 30.
STALE_AFTER_DAYS = 3
MAX_ORBIT_AGE_DAYS = 30
EPOCH_FUTURE_TOLERANCE = timedelta(days=1)


def orbit_age_days(sat: Satellite, at: datetime) -> float:
    return abs((at - sat.EPOCH).total_seconds()) / 86400


def list_satellites(search: str | None, limit: int, offset: int) -> list[Satellite]:
    sats = sorted(store.satellites.values(), key=lambda s: s.OBJECT_NAME)
    if search:
        needle = search.casefold()
        sats = [s for s in sats if needle in s.OBJECT_NAME.casefold() or needle == str(s.NORAD_CAT_ID)]
    return sats[offset : offset + limit]


def get_satellite(norad_id: int) -> Satellite:
    sat = store.satellites.get(norad_id)
    if sat is None:
        raise NotFound("satellite_not_found", f"No satellite with NORAD ID {norad_id}")
    return sat


def _check_elements(sat: Satellite) -> None:
    if sat.EPOCH > datetime.now(timezone.utc) + EPOCH_FUTURE_TOLERANCE:
        raise RuleViolation("epoch_in_future", "EPOCH cannot be more than 1 day in the future")
    rec = orbit.build_satrec(sat)
    # Propagating to the epoch catches orbits SGP4 rejects, e.g. a perigee below Earth's surface.
    if rec.error or rec.sgp4(rec.jdsatepoch, rec.jdsatepochF)[0]:
        raise RuleViolation("invalid_orbit", "These orbital elements do not describe a valid Earth orbit")


def create_satellite(data: SatelliteCreate) -> Satellite:
    if data.NORAD_CAT_ID in store.satellites:
        raise Conflict("satellite_exists", f"Satellite {data.NORAD_CAT_ID} is already in the catalog")
    sat = Satellite.model_validate(data.model_dump())
    _check_elements(sat)
    store.satellites[sat.NORAD_CAT_ID] = sat
    return sat


def update_satellite(norad_id: int, patch: SatelliteUpdate) -> Satellite:
    current = get_satellite(norad_id)
    changes = patch.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        raise RuleViolation("empty_update", "Send at least one field to change")
    # Orbital elements only make sense as a set taken at one moment, so new elements need a new epoch.
    if changes.keys() - {"OBJECT_NAME", "EPOCH"} and "EPOCH" not in changes:
        raise RuleViolation("epoch_required", "Changing orbital elements requires a new EPOCH")
    if "EPOCH" in changes and changes["EPOCH"] <= current.EPOCH:
        raise Conflict("outdated_elements", f"New EPOCH must be later than the current one ({current.EPOCH.isoformat()})")
    updated = current.model_copy(update=changes)
    _check_elements(updated)
    store.satellites[norad_id] = updated
    return updated


def delete_satellite(norad_id: int) -> None:
    get_satellite(norad_id)
    del store.satellites[norad_id]
    # Keep watchlists consistent: nobody can watch a satellite that no longer exists.
    for observer in store.observers.values():
        if norad_id in observer.watchlist:
            observer.watchlist.remove(norad_id)


def get_position(norad_id: int, at: datetime | None) -> Position:
    sat = get_satellite(norad_id)
    at = as_utc(at) if at else datetime.now(timezone.utc)
    age = orbit_age_days(sat, at)
    if age > MAX_ORBIT_AGE_DAYS:
        raise RuleViolation("orbit_data_too_old", f"Orbit data is {age:.0f} days from the requested time (limit {MAX_ORBIT_AGE_DAYS})")
    point = orbit.subpoint(orbit.build_satrec(sat), at.timestamp())
    if point is None:
        raise RuleViolation("propagation_failed", f"{sat.OBJECT_NAME} cannot be located at {at.isoformat()} (it may have decayed)")
    lat, lon, alt = point
    return Position(norad_id=norad_id, time=at, latitude=round(lat, 4), longitude=round(lon, 4), altitude_km=round(alt, 1), orbit_age_days=round(age, 2))
