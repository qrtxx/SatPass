"""Observers (locations), their watchlists, and pass prediction.

Every observer belongs to a user. Users reach only their own; admins reach all (see get_observer)."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import Conflict, Forbidden, NotFound, RuleViolation
from app.models import ObserverModel, SatelliteModel, UserModel, WatchlistEntry
from app.schemas import ObserverCreate, ObserverUpdate, PassPoint, PassReport, PeakPoint, SatellitePass, as_utc
from app.services import orbit
from app.services.satellites import MAX_ORBIT_AGE_DAYS, STALE_AFTER_DAYS, get_satellite, orbit_age_days

# Each watched satellite costs ~1,500 SGP4 runs per day of predictions.
MAX_WATCHLIST = 10


def _check_name_free(db: Session, owner_id: int, name: str, own_id: int | None = None) -> None:
    # Names are unique per owner. The unique index on (owner_id, lower(name)) is the final guard; this gives a readable error.
    query = select(ObserverModel).where(ObserverModel.owner_id == owner_id, func.lower(ObserverModel.name) == name.lower())
    if own_id is not None:
        query = query.where(ObserverModel.id != own_id)
    clash = db.scalar(query)
    if clash:
        raise Conflict("observer_exists", f"An observer named '{clash.name}' already exists")


def is_admin(user: UserModel) -> bool:
    return user.role == "admin"


def list_observers(db: Session, user: UserModel) -> list[ObserverModel]:
    """The user's own locations, admins included; admins see other users' locations on the admin user page."""
    return list(db.scalars(select(ObserverModel).where(ObserverModel.owner_id == user.id).order_by(ObserverModel.id)))


def get_observer(db: Session, user: UserModel, observer_id: int) -> ObserverModel:
    """The one ownership check: every other function reaches an observer through here."""
    obs = db.get(ObserverModel, observer_id)
    if obs is None:
        raise NotFound("observer_not_found", f"No observer with id {observer_id}")
    if obs.owner_id != user.id and not is_admin(user):
        raise Forbidden("not_owner", "This location belongs to another user")
    return obs


def create_observer(db: Session, user: UserModel, data: ObserverCreate) -> ObserverModel:
    _check_name_free(db, user.id, data.name)
    obs = ObserverModel(**data.model_dump(), owner_id=user.id)
    db.add(obs)
    db.commit()
    return obs


def update_observer(db: Session, user: UserModel, observer_id: int, patch: ObserverUpdate) -> ObserverModel:
    obs = get_observer(db, user, observer_id)
    changes = patch.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        raise RuleViolation("empty_update", "Send at least one field to change")
    if "name" in changes:
        _check_name_free(db, obs.owner_id, changes["name"], own_id=observer_id)  # the owner's names, even when an admin edits
    for field, value in changes.items():
        setattr(obs, field, value)
    db.commit()
    return obs


def delete_observer(db: Session, user: UserModel, observer_id: int) -> None:
    db.delete(get_observer(db, user, observer_id))  # its watchlist entries go with it
    db.commit()


# --- Watchlist ----------------------------------------------------------------


def get_watchlist(db: Session, user: UserModel, observer_id: int) -> list[SatelliteModel]:
    return [entry.satellite for entry in get_observer(db, user, observer_id).entries]


def add_to_watchlist(db: Session, user: UserModel, observer_id: int, norad_id: int) -> SatelliteModel:
    obs = get_observer(db, user, observer_id)
    sat = get_satellite(db, norad_id)
    if norad_id in obs.watchlist:
        raise Conflict("already_watched", f"{sat.OBJECT_NAME} is already on this watchlist")
    if len(obs.entries) >= MAX_WATCHLIST:
        raise Conflict("watchlist_full", f"A watchlist holds at most {MAX_WATCHLIST} satellites")
    db.add(WatchlistEntry(observer=obs, satellite=sat))
    db.commit()
    return sat


def remove_from_watchlist(db: Session, user: UserModel, observer_id: int, norad_id: int) -> None:
    get_observer(db, user, observer_id)
    entry = db.get(WatchlistEntry, (observer_id, norad_id))
    if entry is None:
        raise NotFound("not_watched", f"Satellite {norad_id} is not on this watchlist")
    db.delete(entry)
    db.commit()


# --- Passes -------------------------------------------------------------------


def _point(look: orbit.LookFn, ts: float) -> PassPoint:
    azimuth, _ = look(ts)
    time = datetime.fromtimestamp(round(ts), timezone.utc)
    return PassPoint(time=time, azimuth_deg=round(azimuth, 1), compass=orbit.azimuth_to_compass(azimuth))


def predict_passes(
    db: Session,
    user: UserModel,
    observer_id: int,
    start: datetime | None,
    hours: int,
    min_elevation: float | None,
    norad_ids: list[int] | None = None,
) -> PassReport:
    """Passes of the given satellites (any, watched or not), or of the observer's watchlist when none are given.
    The observer must be the user's own (or the user an admin); the satellites can be any."""
    obs = get_observer(db, user, observer_id)
    if norad_ids:
        satellites = [get_satellite(db, norad_id) for norad_id in dict.fromkeys(norad_ids)]
    elif obs.entries:
        satellites = [entry.satellite for entry in obs.entries]
    else:
        raise Conflict("empty_watchlist", "Add satellites to the watchlist before asking for passes")
    start = as_utc(start) if start else datetime.now(timezone.utc)
    end = start + timedelta(hours=hours)
    min_el = obs.min_elevation_deg if min_elevation is None else min_elevation

    passes, warnings = [], []
    for sat in satellites:
        age = orbit_age_days(sat, start)
        if age > MAX_ORBIT_AGE_DAYS:
            warnings.append(f"{sat.OBJECT_NAME}: orbit data is {age:.0f} days old, skipped")
            continue
        if age > STALE_AFTER_DAYS:
            warnings.append(f"{sat.OBJECT_NAME}: orbit data is {age:.0f} days old, times may be off by a minute or more")

        look = orbit.observer_view(orbit.build_satrec(sat), obs.latitude, obs.longitude, obs.elevation_m / 1000)
        if look(start.timestamp()) is None:
            warnings.append(f"{sat.OBJECT_NAME}: cannot be propagated (it may have decayed), skipped")
            continue

        def elevation_at(ts: float) -> float:
            angles = look(ts)
            return angles[1] if angles else -90.0

        for p in orbit.find_passes(elevation_at, start.timestamp(), end.timestamp(), min_el):
            peak = _point(look, p["peak"])
            passes.append(
                SatellitePass(
                    norad_id=sat.NORAD_CAT_ID,
                    name=sat.OBJECT_NAME,
                    rise=_point(look, p["rise"]),
                    peak=PeakPoint(**peak.model_dump(), elevation_deg=round(p["peak_elevation"], 1)),
                    set=_point(look, p["set"]),
                    duration_seconds=round(p["set"] - p["rise"]),
                )
            )

    passes.sort(key=lambda p: p.rise.time)
    return PassReport(observer_id=obs.id, start=start, end=end, min_elevation_deg=min_el, passes=passes, warnings=warnings)
