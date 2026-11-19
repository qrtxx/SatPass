import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.main import app
from app.models import ObserverModel, WatchlistEntry
from app.schemas import ISS_EXAMPLE

client = TestClient(app)
START = "2026-11-05T00:00:00Z"
NEW_SAT = {**ISS_EXAMPLE, "OBJECT_NAME": "TEST SAT", "NORAD_CAT_ID": 99999}


@pytest.fixture(autouse=True)
def fresh_data(db):
    pass  # the db fixture (conftest.py) gives every test the seed data in a rolled-back transaction


# --- Satellites ---------------------------------------------------------------


def test_list_and_search():
    assert len(client.get("/satellites").json()) == 20
    names = [s["OBJECT_NAME"] for s in client.get("/satellites", params={"search": "iss"}).json()]
    assert names == ["ISS (NAUKA)", "ISS (ZARYA)"]
    assert client.get("/satellites", params={"search": "25544"}).json()[0]["period_minutes"] == 92.95
    assert client.get("/satellites", params={"limit": 0}).status_code == 422


def test_get_unknown_satellite():
    r = client.get("/satellites/1")
    assert r.status_code == 404 and r.json()["code"] == "satellite_not_found"


def test_create_satellite():
    assert client.post("/satellites", json=NEW_SAT).status_code == 201
    r = client.post("/satellites", json=NEW_SAT)
    assert r.status_code == 409 and r.json()["code"] == "satellite_exists"


@pytest.mark.parametrize("field, value", [("ECCENTRICITY", 1.5), ("INCLINATION", -1), ("MEAN_MOTION", "fast"), ("OBJECT_NAME", "  ")])
def test_create_satellite_invalid_fields(field, value):
    assert client.post("/satellites", json={**NEW_SAT, field: value}).status_code == 422


def test_create_satellite_business_rules():
    r = client.post("/satellites", json={**NEW_SAT, "ECCENTRICITY": 0.9})  # perigee inside Earth
    assert r.status_code == 422 and r.json()["code"] == "invalid_orbit"
    r = client.post("/satellites", json={**NEW_SAT, "EPOCH": "2099-01-01T00:00:00"})
    assert r.status_code == 422 and r.json()["code"] == "epoch_in_future"


def test_update_satellite_rules():
    assert client.patch("/satellites/25544", json={"OBJECT_NAME": "ISS"}).json()["OBJECT_NAME"] == "ISS"
    assert client.patch("/satellites/25544", json={}).json()["code"] == "empty_update"
    assert client.patch("/satellites/25544", json={"MEAN_ANOMALY": 10}).json()["code"] == "epoch_required"
    r = client.patch("/satellites/25544", json={"EPOCH": "2026-11-01T00:00:00", "MEAN_ANOMALY": 10})
    assert r.status_code == 409 and r.json()["code"] == "outdated_elements"
    r = client.patch("/satellites/25544", json={"EPOCH": "2026-11-05T00:00:00", "MEAN_ANOMALY": 10})
    assert r.status_code == 200 and r.json()["MEAN_ANOMALY"] == 10
    assert client.patch("/satellites/25544", json={"NORAD_CAT_ID": 1}).status_code == 422


def test_delete_satellite_removes_it_from_watchlists():
    assert client.delete("/satellites/25544").status_code == 204
    assert client.get("/satellites/25544").status_code == 404
    assert client.get("/observers/1").json()["watchlist"] == []
    assert client.delete("/satellites/25544").status_code == 404


def test_position():
    r = client.get("/satellites/25544/position", params={"at": START})
    assert r.status_code == 200 and 370 < r.json()["altitude_km"] < 460
    r = client.get("/satellites/25544/position", params={"at": "2027-06-01T00:00:00Z"})
    assert r.status_code == 422 and r.json()["code"] == "orbit_data_too_old"


# --- Observers & watchlist ----------------------------------------------------


def test_observer_crud():
    r = client.post("/observers", json={"name": "Astana", "latitude": 51.17, "longitude": 71.45})
    assert r.status_code == 201
    obs_id = r.json()["id"]
    assert client.patch(f"/observers/{obs_id}", json={"min_elevation_deg": 20}).json()["min_elevation_deg"] == 20
    assert len(client.get("/observers").json()) == 2
    assert client.delete(f"/observers/{obs_id}").status_code == 204
    assert client.get(f"/observers/{obs_id}").status_code == 404


@pytest.mark.parametrize("body", [{"name": "X", "latitude": 91, "longitude": 0}, {"name": "X", "latitude": 0}, {"name": "", "latitude": 0, "longitude": 0}])
def test_observer_validation(body):
    assert client.post("/observers", json=body).status_code == 422


def test_observer_names_are_unique():
    r = client.post("/observers", json={"name": "almaty", "latitude": 0, "longitude": 0})
    assert r.status_code == 409 and r.json()["code"] == "observer_exists"


def test_watchlist_flow():
    assert client.post("/observers/1/watchlist", json={"norad_id": 48274}).status_code == 201
    assert [s["NORAD_CAT_ID"] for s in client.get("/observers/1/watchlist").json()] == [25544, 48274]
    assert client.post("/observers/1/watchlist", json={"norad_id": 48274}).json()["code"] == "already_watched"
    assert client.post("/observers/1/watchlist", json={"norad_id": 1}).status_code == 404
    assert client.post("/observers/9/watchlist", json={"norad_id": 48274}).status_code == 404
    assert client.delete("/observers/1/watchlist/48274").status_code == 204
    assert client.delete("/observers/1/watchlist/48274").status_code == 404


def test_watchlist_is_capped():
    ids = [s["NORAD_CAT_ID"] for s in client.get("/satellites").json() if s["NORAD_CAT_ID"] != 25544]
    for norad_id in ids[:9]:
        assert client.post("/observers/1/watchlist", json={"norad_id": norad_id}).status_code == 201
    r = client.post("/observers/1/watchlist", json={"norad_id": ids[9]})
    assert r.status_code == 409 and r.json()["code"] == "watchlist_full"


# --- Passes -------------------------------------------------------------------


def test_iss_passes_over_almaty():
    body = client.get("/observers/1/passes", params={"start": START}).json()
    assert len(body["passes"]) == 5 and body["warnings"] == []
    first = body["passes"][0]
    assert first["rise"]["time"] == "2026-11-05T15:59:26Z"
    assert first["rise"]["compass"] == "SW" and first["peak"]["elevation_deg"] == 61.5
    assert first["duration_seconds"] == 650


def test_passes_filters_and_sorting():
    client.post("/observers/1/watchlist", json={"norad_id": 48274})
    passes = client.get("/observers/1/passes", params={"start": START, "hours": 48, "min_elevation": 30}).json()["passes"]
    times = [p["rise"]["time"] for p in passes]
    assert times == sorted(times) and {p["norad_id"] for p in passes} == {25544, 48274}
    assert all(p["peak"]["elevation_deg"] >= 30 for p in passes)


def test_passes_errors_and_warnings():
    assert client.get("/observers/1/passes", params={"hours": 0}).status_code == 422
    assert client.get("/observers/9/passes").status_code == 404
    warned = client.get("/observers/1/passes", params={"start": "2026-11-12T00:00:00Z"}).json()
    assert "days old" in warned["warnings"][0] and warned["passes"]
    skipped = client.get("/observers/1/passes", params={"start": "2027-01-01T00:00:00Z"}).json()
    assert skipped["passes"] == [] and "skipped" in skipped["warnings"][0]
    client.delete("/observers/1/watchlist/25544")
    r = client.get("/observers/1/passes")
    assert r.status_code == 409 and r.json()["code"] == "empty_watchlist"


# --- Database integrity ---------------------------------------------------------


def test_data_is_saved_in_the_database(db):
    client.post("/observers", json={"name": "Astana", "latitude": 51.17, "longitude": 71.45})
    client.post("/observers/1/watchlist", json={"norad_id": 48274})
    db.expire_all()  # forget cached objects and read the rows back
    assert db.query(ObserverModel).filter_by(name="Astana").one().latitude == 51.17
    assert db.get(WatchlistEntry, (1, 48274)) is not None


@pytest.mark.parametrize(
    "row",
    [
        ObserverModel(name="Pole", latitude=95, longitude=0),  # CHECK latitude range
        ObserverModel(name="ALMATY", latitude=0, longitude=0),  # unique lower(name)
        WatchlistEntry(observer_id=1, norad_id=1),  # foreign key: no satellite 1
        WatchlistEntry(observer_id=1, norad_id=25544),  # primary key: already watched
    ],
)
def test_database_constraints_reject_bad_rows(db, row):
    db.add(row)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()
