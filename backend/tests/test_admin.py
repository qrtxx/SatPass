import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import ObserverModel, UserModel
from app.security import create_access_token

client = TestClient(app)
HOME = {"name": "Home", "latitude": 43.2, "longitude": 76.9}
SEED_ADMIN = {"Authorization": f"Bearer {create_access_token(1)}"}  # user 1 = the seeded admin, owner of Almaty


def user_id(db, username):
    return db.scalar(select(UserModel.id).where(UserModel.username == username))


@pytest.mark.parametrize(
    "method, path, body",
    [
        ("get", "/admin/stats", None),
        ("get", "/admin/users", None),
        ("get", "/admin/users/1", None),
        ("patch", "/admin/users/1", {"role": "user"}),
        ("delete", "/admin/users/1", None),
    ],
)
def test_admin_routes_are_admin_only(db, make_user, method, path, body):
    assert client.request(method.upper(), path, json=body).status_code == 401
    r = client.request(method.upper(), path, json=body, headers=make_user("alice"))
    assert r.status_code == 403 and r.json()["code"] == "admin_only"


def test_users_list_counts_locations_and_searches(db, make_user):
    alice = make_user("alice")
    client.post("/observers", json=HOME, headers=alice)
    users = {u["username"]: u for u in client.get("/admin/users", headers=SEED_ADMIN).json()}
    assert users["admin"]["location_count"] == 1 and users["alice"]["location_count"] == 1
    assert "password_hash" not in str(users)
    found = client.get("/admin/users", params={"search": "ALI"}, headers=SEED_ADMIN).json()
    assert [u["username"] for u in found] == ["alice"]  # by username or email, ignoring case


def test_user_page_shows_their_locations(db, make_user):
    alice = make_user("alice")
    client.post("/observers", json=HOME, headers=alice)
    r = client.get(f"/admin/users/{user_id(db, 'alice')}", headers=SEED_ADMIN)
    assert r.status_code == 200
    assert r.json()["username"] == "alice" and [o["name"] for o in r.json()["locations"]] == ["Home"]
    assert client.get("/admin/users/999", headers=SEED_ADMIN).status_code == 404


def test_change_role(db, make_user):
    make_user("alice")
    alice_id = user_id(db, "alice")
    r = client.patch(f"/admin/users/{alice_id}", json={"role": "admin"}, headers=SEED_ADMIN)
    assert r.status_code == 200 and r.json()["role"] == "admin"
    assert client.patch(f"/admin/users/{alice_id}", json={"role": "boss"}, headers=SEED_ADMIN).status_code == 422


def test_last_admin_cannot_be_demoted_or_deleted(db, make_user):
    for r in [
        client.patch("/admin/users/1", json={"role": "user"}, headers=SEED_ADMIN),
        client.delete("/admin/users/1", headers=SEED_ADMIN),
    ]:
        assert r.status_code == 409 and r.json()["code"] == "last_admin"
    # With a second admin, the first one may step down.
    make_user("boss", "admin")
    assert client.patch("/admin/users/1", json={"role": "user"}, headers=SEED_ADMIN).status_code == 200


def test_deleting_a_user_deletes_their_locations(db, make_user):
    alice = make_user("alice")
    obs_id = client.post("/observers", json=HOME, headers=alice).json()["id"]
    assert client.delete(f"/admin/users/{user_id(db, 'alice')}", headers=SEED_ADMIN).status_code == 204
    db.expire_all()
    assert db.get(ObserverModel, obs_id) is None and user_id(db, "alice") is None


def test_stats(db, make_user):
    make_user("alice")
    stats = client.get("/admin/stats", headers=SEED_ADMIN).json()
    assert (stats["users"], stats["admins"]) == (2, 1)
    assert stats["satellites"] >= 20 and stats["places"] >= 0 and isinstance(stats["imports"], list)


def test_my_locations_are_my_own_even_for_admins(db, make_user):
    alice = make_user("alice")
    client.post("/observers", json=HOME, headers=alice)
    assert [o["name"] for o in client.get("/observers", headers=SEED_ADMIN).json()] == ["Almaty"]
