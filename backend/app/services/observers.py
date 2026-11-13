"""Observers (locations), their watchlists, and pass prediction for a watchlist."""

from datetime import datetime, timedelta, timezone

from app import store
from app.errors import Conflict, NotFound, RuleViolation
from app.schemas import Observer, as_utc, ObserverCreate, ObserverUpdate, PassPoint, PassReport, PeakPoint, Satellite, SatellitePass
from app.services import orbit
from app.services.satellites import MAX_ORBIT_AGE_DAYS, STALE_AFTER_DAYS, get_satellite, orbit_age_days

# Each watched satellite costs ~1,500 SGP4 runs per day of predictions.
MAX_WATCHLIST = 10


def _check_name_free(name: str, own_id: int | None = None) -> None:
    for obs in store.observers.values():
        if obs.id != own_id and obs.name.casefold() == name.casefold():
            raise Conflict("observer_exists", f"An observer named '{obs.name}' already exists")


def list_observers() -> list[Observer]:
    return list(store.observers.values())


def get_observer(observer_id: int) -> Observer:
    obs = store.observers.get(observer_id)
    if obs is None:
        raise NotFound("observer_not_found", f"No observer with id {observer_id}")
    return obs


def create_observer(data: ObserverCreate) -> Observer:
    _check_name_free(data.name)
    obs = Observer(id=store.next_observer_id(), **data.model_dump())
    store.observers[obs.id] = obs
    return obs


def update_observer(observer_id: int, patch: ObserverUpdate) -> Observer:
    current = get_observer(observer_id)
    changes = patch.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        raise RuleViolation("empty_update", "Send at least one field to change")
    if "name" in changes:
        _check_name_free(changes["name"], own_id=observer_id)
    updated = current.model_copy(update=changes)
    store.observers[observer_id] = updated
    return updated


def delete_observer(observer_id: int) -> None:
    get_observer(observer_id)
    del store.observers[observer_id]


# --- Watchlist ----------------------------------------------------------------


def get_watchlist(observer_id: int) -> list[Satellite]:
    return [store.satellites[n] for n in get_observer(observer_id).watchlist]


def add_to_watchlist(observer_id: int, norad_id: int) -> Satellite:
    obs = get_observer(observer_id)
    sat = get_satellite(norad_id)
    if norad_id in obs.watchlist:
        raise Conflict("already_watched", f"{sat.OBJECT_NAME} is already on this watchlist")
    if len(obs.watchlist) >= MAX_WATCHLIST:
        raise Conflict("watchlist_full", f"A watchlist holds at most {MAX_WATCHLIST} satellites")
    obs.watchlist.append(norad_id)
    return sat


def remove_from_watchlist(observer_id: int, norad_id: int) -> None:
    obs = get_observer(observer_id)
    if norad_id not in obs.watchlist:
        raise NotFound("not_watched", f"Satellite {norad_id} is not on this watchlist")
    obs.watchlist.remove(norad_id)


# --- Passes -------------------------------------------------------------------


def _point(look: orbit.LookFn, ts: float) -> PassPoint:
    azimuth, _ = look(ts)
    time = datetime.fromtimestamp(round(ts), timezone.utc)
    return PassPoint(time=time, azimuth_deg=round(azimuth, 1), compass=orbit.azimuth_to_compass(azimuth))


def predict_passes(observer_id: int, start: datetime | None, hours: int, min_elevation: float | None) -> PassReport:
    obs = get_observer(observer_id)
    if not obs.watchlist:
        raise Conflict("empty_watchlist", "Add satellites to the watchlist before asking for passes")
    start = as_utc(start) if start else datetime.now(timezone.utc)
    end = start + timedelta(hours=hours)
    min_el = obs.min_elevation_deg if min_elevation is None else min_elevation

    passes, warnings = [], []
    for norad_id in obs.watchlist:
        sat = store.satellites[norad_id]
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
                    norad_id=norad_id,
                    name=sat.OBJECT_NAME,
                    rise=_point(look, p["rise"]),
                    peak=PeakPoint(**peak.model_dump(), elevation_deg=round(p["peak_elevation"], 1)),
                    set=_point(look, p["set"]),
                    duration_seconds=round(p["set"] - p["rise"]),
                )
            )

    passes.sort(key=lambda p: p.rise.time)
    return PassReport(observer_id=obs.id, start=start, end=end, min_elevation_deg=min_el, passes=passes, warnings=warnings)
