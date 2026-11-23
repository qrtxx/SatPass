import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.errors import BadGateway
from app.main import app
from app.models import CatalogImportModel, SatelliteModel
from app.schemas import ISS_EXAMPLE
from app.services import catalog_import
from app.services.celestrak import get_fetcher

client = TestClient(app)
SNAPSHOT = {s["NORAD_CAT_ID"]: s for s in json.loads((Path(__file__).resolve().parents[2] / "src" / "data" / "sample-gp.json").read_text())}
HST = SNAPSHOT[20580]  # seeded, same EPOCH as in the database
# A newer ISS element set, with keys CelesTrak sends that we don't store.
ISS_NEWER = {**ISS_EXAMPLE, "EPOCH": "2026-11-22T21:51:10.110816", "MEAN_ANOMALY": 100.0, "OBJECT_ID": "1998-067A", "ELEMENT_SET_NO": 999}
NEW_SAT = {**ISS_EXAMPLE, "NORAD_CAT_ID": 99999, "OBJECT_NAME": "NEW SAT"}


@pytest.fixture(autouse=True)
def fresh_data(db):
    pass  # every test runs on the seed data in a rolled-back transaction


def run_import(records, group="stations"):
    calls = []

    def fake_fetch(name):
        calls.append(name)
        return records

    app.dependency_overrides[get_fetcher] = lambda: fake_fetch
    response = client.post("/satellites/import", json={"group": group})
    response.fetch_calls = calls
    return response


def test_import_adds_updates_and_skips(db):
    broken = {**NEW_SAT, "NORAD_CAT_ID": 99998, "ECCENTRICITY": 1.5}
    r = run_import([ISS_NEWER, NEW_SAT, HST, broken])
    assert r.status_code == 200
    body = r.json()
    assert (body["received"], body["added"], body["updated"], body["unchanged"], body["skipped"]) == (4, 1, 1, 1, 1)
    assert body["skipped_examples"] == [{"norad_id": 99998, "reason": "invalid_fields"}]
    assert body["group"] == "stations"
    db.expire_all()
    assert db.get(SatelliteModel, 25544).MEAN_ANOMALY == 100.0
    assert db.get(SatelliteModel, 99999).OBJECT_NAME == "NEW SAT"


def test_older_epoch_never_overwrites(db):
    older = {**ISS_EXAMPLE, "EPOCH": "2026-11-01T00:00:00", "MEAN_ANOMALY": 200.0}
    body = run_import([older]).json()
    assert (body["updated"], body["unchanged"]) == (0, 1)
    db.expire_all()
    assert db.get(SatelliteModel, 25544).MEAN_ANOMALY == ISS_EXAMPLE["MEAN_ANOMALY"]


def test_update_keeps_watchlists(db):
    run_import([ISS_NEWER])
    assert client.get("/observers/1").json()["watchlist"] == [25544]


def test_duplicate_ids_in_feed_keep_latest(db):
    a = {**ISS_EXAMPLE, "EPOCH": "2026-11-20T00:00:00", "MEAN_ANOMALY": 10.0}
    b = {**ISS_EXAMPLE, "EPOCH": "2026-11-21T00:00:00", "MEAN_ANOMALY": 20.0}
    body = run_import([b, a]).json()
    assert body["updated"] == 1
    db.expire_all()
    assert db.get(SatelliteModel, 25544).MEAN_ANOMALY == 20.0


def test_invalid_records_are_skipped(db):
    future = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    in_future = {**NEW_SAT, "NORAD_CAT_ID": 99997, "EPOCH": future}
    bad_orbit = {**NEW_SAT, "NORAD_CAT_ID": 99996, "ECCENTRICITY": 0.9}
    no_name = {key: value for key, value in NEW_SAT.items() if key != "OBJECT_NAME"} | {"NORAD_CAT_ID": 99995}
    body = run_import([in_future, bad_orbit, no_name, NEW_SAT]).json()
    assert (body["added"], body["skipped"]) == (1, 3)
    assert body["skipped_examples"] == [
        {"norad_id": 99997, "reason": "epoch_in_future"},
        {"norad_id": 99996, "reason": "invalid_orbit"},
        {"norad_id": 99995, "reason": "invalid_fields"},
    ]


def test_skipped_examples_are_capped_at_ten(db):
    broken = [{**NEW_SAT, "NORAD_CAT_ID": 90000 + i, "ECCENTRICITY": 1.5} for i in range(15)]
    body = run_import(broken).json()
    assert body["skipped"] == 15 and len(body["skipped_examples"]) == 10


def test_second_import_within_two_hours_is_429(db):
    assert run_import([NEW_SAT]).status_code == 200
    r = run_import([NEW_SAT])
    assert r.status_code == 429 and r.json()["code"] == "import_too_soon"
    assert 0 < int(r.headers["Retry-After"]) <= 7200
    assert r.fetch_calls == []  # CelesTrak is not contacted again
    assert run_import([NEW_SAT], group="visual").status_code == 200  # the limit is per group


def test_limit_expires_after_two_hours(db):
    run_import([NEW_SAT])
    db.get(CatalogImportModel, "stations").fetched_at -= timedelta(hours=2, minutes=1)
    db.flush()
    assert run_import([NEW_SAT]).status_code == 200


def test_failed_fetch_writes_nothing(db):
    def offline(group):
        raise BadGateway("celestrak_unavailable", "Could not reach CelesTrak: offline")

    app.dependency_overrides[get_fetcher] = lambda: offline
    r = client.post("/satellites/import", json={"group": "stations"})
    assert r.status_code == 502 and r.json()["code"] == "celestrak_unavailable"
    assert db.get(CatalogImportModel, "stations") is None  # so an immediate retry is allowed


def test_concurrent_import_is_refused(db):
    with catalog_import.IMPORT_LOCK:  # as if another import were still downloading
        r = run_import([NEW_SAT])
    assert r.status_code == 409 and r.json()["code"] == "import_in_progress"
    assert r.fetch_calls == []  # CelesTrak is not contacted twice
    assert run_import([NEW_SAT]).status_code == 200  # free again afterwards


def test_unknown_group_is_422(db):
    r = run_import([NEW_SAT], group="nosuchgroup")
    assert r.status_code == 422 and r.fetch_calls == []
