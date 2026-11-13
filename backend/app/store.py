"""In-memory data store, seeded from the bundled CelesTrak snapshot."""

import json
from itertools import count
from pathlib import Path

from app.schemas import Observer, Satellite

SNAPSHOT = Path(__file__).resolve().parents[2] / "src" / "data" / "sample-gp.json"
ISS_ID = 25544

satellites: dict[int, Satellite] = {}
observers: dict[int, Observer] = {}
_observer_ids = count(1)


def next_observer_id() -> int:
    return next(_observer_ids)


def reset() -> None:
    """Clear everything and load the seed data (also used by the tests)."""
    global _observer_ids
    satellites.clear()
    observers.clear()
    _observer_ids = count(1)
    for record in json.loads(SNAPSHOT.read_text(encoding="utf-8")):
        sat = Satellite.model_validate(record)
        satellites[sat.NORAD_CAT_ID] = sat
    almaty = Observer(id=next_observer_id(), name="Almaty", latitude=43.2389, longitude=76.8897, elevation_m=800, watchlist=[ISS_ID])
    observers[almaty.id] = almaty


reset()
