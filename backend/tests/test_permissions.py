import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import UserModel
from app.schemas import ISS_EXAMPLE
from app.services.celestrak import get_fetcher

client = TestClient(app)
HOME = {"name": "Home", "latitude": 43.2, "longitude": 76.9}


def test_anonymous_gets_401_on_observers(db):
    assert client.get("/observers").status_code == 401
    assert client.post("/observers", json=HOME).status_code == 401
    assert client.get("/observers/1/passes").status_code == 401


def test_users_see_only_their_own_observers(db, make_user):
    alice, bob = make_user("alice"), make_user("bob")
    client.post("/observers", json=HOME, headers=alice)
    assert [o["name"] for o in client.get("/observers", headers=alice).json()] == ["Home"]
    assert client.get("/observers", headers=bob).json() == []


@pytest.mark.parametrize(
    "method, path, body",
    [
        ("get", "/observers/{id}", None),
        ("patch", "/observers/{id}", {"min_elevation_deg": 20}),
        ("delete", "/observers/{id}", None),
        ("get", "/observers/{id}/watchlist", None),
        ("post", "/observers/{id}/watchlist", {"norad_id": 25544}),
        ("delete", "/observers/{id}/watchlist/25544", None),
        ("get", "/observers/{id}/passes", None),
        ("get", "/observers/{id}/passes?norad_id=25544", None),  # choosing satellites doesn't bypass ownership
    ],
)
def test_other_users_observer_is_forbidden(db, make_user, method, path, body):
    alice, bob = make_user("alice"), make_user("bob")
    obs_id = client.post("/observers", json=HOME, headers=alice).json()["id"]
    r = client.request(method.upper(), path.format(id=obs_id), json=body, headers=bob)
    assert r.status_code == 403 and r.json()["code"] == "not_owner"


def test_missing_observer_is_still_404(db, make_user):
    assert client.get("/observers/999", headers=make_user("alice")).status_code == 404


def test_admin_can_manage_any_observer(db, make_user):
    alice, admin = make_user("alice"), make_user("boss", "admin")
    obs_id = client.post("/observers", json=HOME, headers=alice).json()["id"]
    # Not mixed into the admin's own list (that's on the admin user page), but reachable by id.
    assert obs_id not in [o["id"] for o in client.get("/observers", headers=admin).json()]
    assert client.get(f"/observers/{obs_id}", headers=admin).status_code == 200
    assert client.patch(f"/observers/{obs_id}", json={"name": "Alice's home"}, headers=admin).status_code == 200
    assert client.delete(f"/observers/{obs_id}", headers=admin).status_code == 204


def test_observer_names_are_unique_per_owner(db, make_user):
    alice, bob = make_user("alice"), make_user("bob")
    assert client.post("/observers", json=HOME, headers=alice).status_code == 201
    assert client.post("/observers", json=HOME, headers=bob).status_code == 201
    r = client.post("/observers", json={**HOME, "name": "HOME"}, headers=alice)
    assert r.status_code == 409 and r.json()["code"] == "observer_exists"


def test_admin_renaming_checks_the_owners_names(db, make_user):
    alice, admin = make_user("alice"), make_user("boss", "admin")
    client.post("/observers", json=HOME, headers=alice)
    other = client.post("/observers", json={**HOME, "name": "Cabin"}, headers=alice).json()["id"]
    client.post("/observers", json={**HOME, "name": "Admin place"}, headers=admin)
    # Clashes with Alice's own "Home", not with the admin's names.
    assert client.patch(f"/observers/{other}", json={"name": "home"}, headers=admin).json()["code"] == "observer_exists"
    assert client.patch(f"/observers/{other}", json={"name": "Admin place"}, headers=admin).status_code == 200


def test_new_observer_is_owned_by_creator(db, make_user):
    alice = make_user("alice")
    me = client.get("/auth/me", headers=alice).json()
    assert client.post("/observers", json=HOME, headers=alice).json()["owner_id"] == me["id"]


# --- Satellite catalog: anyone may read it, only admins may change it --------------------------------


NEW_SAT = {**ISS_EXAMPLE, "OBJECT_NAME": "TEST SAT", "NORAD_CAT_ID": 99999}


@pytest.mark.parametrize(
    "method, path, body",
    [
        ("post", "/satellites", NEW_SAT),
        ("patch", "/satellites/25544", {"OBJECT_NAME": "X"}),
        ("delete", "/satellites/25544", None),
        ("post", "/satellites/import", {"group": "stations"}),
    ],
)
def test_catalog_changes_are_admin_only(db, make_user, method, path, body):
    app.dependency_overrides[get_fetcher] = lambda: lambda group: pytest.fail("a refused import must not contact CelesTrak")
    assert client.request(method.upper(), path, json=body).status_code == 401
    r = client.request(method.upper(), path, json=body, headers=make_user("alice"))
    assert r.status_code == 403 and r.json()["code"] == "admin_only"


def test_catalog_reads_are_public(db):
    for path in ["/satellites", "/satellites/25544", "/satellites/25544/position"]:
        assert client.get(path).status_code in (200, 422)  # 422: the seed's orbit data may be too old to locate


def test_admin_can_change_the_catalog(db, make_user):
    assert client.delete("/satellites/25544", headers=make_user("boss", "admin")).status_code == 204


def test_demoted_admin_loses_access_immediately(db, make_user):
    headers = make_user("boss", "admin")
    db.scalar(select(UserModel).where(UserModel.username == "boss")).role = "user"
    db.flush()
    assert client.delete("/satellites/25544", headers=headers).status_code == 403
