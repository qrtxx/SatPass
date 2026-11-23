"""Satellite catalog: create, read, update, delete and live position, with the catalog's business rules."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.errors import Conflict, NotFound, RuleViolation
from app.models import SatelliteModel
from app.schemas import Position, Satellite, SatelliteCreate, SatelliteUpdate, as_utc
from app.services import orbit

# Elements get less accurate with age: warn after 3 days, refuse to predict after 30.
STALE_AFTER_DAYS = 3
MAX_ORBIT_AGE_DAYS = 30
EPOCH_FUTURE_TOLERANCE = timedelta(days=1)


def orbit_age_days(sat: SatelliteModel, at: datetime) -> float:
    return abs((at - sat.EPOCH).total_seconds()) / 86400


def list_satellites(db: Session, search: str | None, limit: int, offset: int) -> list[SatelliteModel]:
    query = select(SatelliteModel).order_by(SatelliteModel.OBJECT_NAME).limit(limit).offset(offset)
    if search:
        match = SatelliteModel.OBJECT_NAME.icontains(search, autoescape=True)
        if search.isdigit() and len(search) <= 9:
            match = or_(match, SatelliteModel.NORAD_CAT_ID == int(search))
        query = query.where(match)
    return list(db.scalars(query))


def get_satellite(db: Session, norad_id: int) -> SatelliteModel:
    sat = db.get(SatelliteModel, norad_id)
    if sat is None:
        raise NotFound("satellite_not_found", f"No satellite with NORAD ID {norad_id}")
    return sat


def check_elements(sat: SatelliteCreate) -> None:
    if sat.EPOCH > datetime.now(timezone.utc) + EPOCH_FUTURE_TOLERANCE:
        raise RuleViolation("epoch_in_future", "EPOCH cannot be more than 1 day in the future")
    rec = orbit.build_satrec(sat)
    # Propagating to the epoch catches orbits SGP4 rejects, e.g. a perigee below Earth's surface.
    if rec.error or rec.sgp4(rec.jdsatepoch, rec.jdsatepochF)[0]:
        raise RuleViolation("invalid_orbit", "These orbital elements do not describe a valid Earth orbit")


def create_satellite(db: Session, data: SatelliteCreate) -> SatelliteModel:
    if db.get(SatelliteModel, data.NORAD_CAT_ID):
        raise Conflict("satellite_exists", f"Satellite {data.NORAD_CAT_ID} is already in the catalog")
    check_elements(data)
    sat = SatelliteModel(**data.model_dump())
    db.add(sat)
    db.commit()
    return sat


def update_satellite(db: Session, norad_id: int, patch: SatelliteUpdate) -> SatelliteModel:
    current = get_satellite(db, norad_id)
    changes = patch.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        raise RuleViolation("empty_update", "Send at least one field to change")
    # Orbital elements only make sense as a set taken at one moment, so new elements need a new epoch.
    if changes.keys() - {"OBJECT_NAME", "EPOCH"} and "EPOCH" not in changes:
        raise RuleViolation("epoch_required", "Changing orbital elements requires a new EPOCH")
    if "EPOCH" in changes and changes["EPOCH"] <= current.EPOCH:
        raise Conflict("outdated_elements", f"New EPOCH must be later than the current one ({current.EPOCH.isoformat()})")
    # Check the merged element set before touching the row, so a rejected update leaves it unchanged.
    check_elements(Satellite.model_validate(current).model_copy(update=changes))
    for field, value in changes.items():
        setattr(current, field, value)
    db.commit()
    return current


def delete_satellite(db: Session, norad_id: int) -> None:
    # Watchlist entries for it are removed by ON DELETE CASCADE, so no observer watches a missing satellite.
    db.delete(get_satellite(db, norad_id))
    db.commit()


def get_position(db: Session, norad_id: int, at: datetime | None) -> Position:
    sat = get_satellite(db, norad_id)
    at = as_utc(at) if at else datetime.now(timezone.utc)
    age = orbit_age_days(sat, at)
    if age > MAX_ORBIT_AGE_DAYS:
        raise RuleViolation("orbit_data_too_old", f"Orbit data is {age:.0f} days from the requested time (limit {MAX_ORBIT_AGE_DAYS})")
    point = orbit.subpoint(orbit.build_satrec(sat), at.timestamp())
    if point is None:
        raise RuleViolation("propagation_failed", f"{sat.OBJECT_NAME} cannot be located at {at.isoformat()} (it may have decayed)")
    lat, lon, alt = point
    return Position(norad_id=norad_id, time=at, latitude=round(lat, 4), longitude=round(lon, 4), altitude_km=round(alt, 1), orbit_age_days=round(age, 2))
