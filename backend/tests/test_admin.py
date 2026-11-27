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
        ("patch", "/admin/users/1", {"role": "user", "password": "x"}),
        ("delete", "/admin/users/1", None),
        ("post", "/admin/users/1/restore", None),
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


def seed_admin_password(db):
    """The seeded admin has an unusable password; give it one for tests that must re-type it."""
    from app.services.auth import set_password

    set_password(db, "admin", ADMIN_PASSWORD)


ADMIN_PASSWORD = "admin-password-1"


def test_change_role(db, make_user):
    seed_admin_password(db)
    make_user("alice")
    alice_id = user_id(db, "alice")
    r = client.patch(f"/admin/users/{alice_id}", json={"role": "admin", "password": ADMIN_PASSWORD}, headers=SEED_ADMIN)
    assert r.status_code == 200 and r.json()["role"] == "admin"
    bad_role = {"role": "boss", "password": ADMIN_PASSWORD}
    assert client.patch(f"/admin/users/{alice_id}", json=bad_role, headers=SEED_ADMIN).status_code == 422


def test_role_change_needs_the_admins_own_password(db, make_user):
    seed_admin_password(db)
    make_user("alice")
    alice_id = user_id(db, "alice")
    assert client.patch(f"/admin/users/{alice_id}", json={"role": "admin"}, headers=SEED_ADMIN).status_code == 422  # missing
    r = client.patch(f"/admin/users/{alice_id}", json={"role": "admin", "password": "wrong"}, headers=SEED_ADMIN)
    # 403, not 401: a wrong re-typed password must not log the admin out.
    assert r.status_code == 403 and r.json()["code"] == "wrong_password"
    db.expire_all()
    assert db.get(UserModel, alice_id).role == "user"


def test_last_admin_cannot_be_demoted_or_deleted(db, make_user):
    seed_admin_password(db)
    demote = {"role": "user", "password": ADMIN_PASSWORD}
    for r in [
        client.patch("/admin/users/1", json=demote, headers=SEED_ADMIN),
        client.delete("/admin/users/1", headers=SEED_ADMIN),
    ]:
        assert r.status_code == 409 and r.json()["code"] == "last_admin"
    # With a second admin, the first one may step down.
    make_user("boss", "admin")
    assert client.patch("/admin/users/1", json=demote, headers=SEED_ADMIN).status_code == 200


def test_deleting_an_account_hides_it_but_keeps_its_data(db, make_user):
    alice = make_user("alice")
    obs_id = client.post("/observers", json=HOME, headers=alice).json()["id"]
    alice_id = user_id(db, "alice")
    assert client.delete(f"/admin/users/{alice_id}", headers=SEED_ADMIN).status_code == 204
    db.expire_all()
    assert db.get(UserModel, alice_id).deleted_at is not None  # soft delete: still in the database
    assert db.get(ObserverModel, obs_id) is not None  # with her locations
    assert client.get("/auth/me", headers=alice).json()["code"] == "invalid_token"  # her token stops working
    assert client.post("/auth/login", json={"login": "alice", "password": "password123"}).status_code == 401
    assert "alice" not in [u["username"] for u in client.get("/admin/users", headers=SEED_ADMIN).json()]
    shown = client.get("/admin/users", params={"include_deleted": True}, headers=SEED_ADMIN).json()
    assert next(u for u in shown if u["username"] == "alice")["deleted_at"] is not None
    taken = {"username": "alice", "email": "new@example.com", "password": "password123"}  # the name stays reserved
    assert client.post("/auth/register", json=taken).json()["code"] == "username_taken"
    assert client.delete(f"/admin/users/{alice_id}", headers=SEED_ADMIN).json()["code"] == "already_deleted"


def test_restore_account(db, make_user):
    make_user("alice")
    alice_id = user_id(db, "alice")
    client.delete(f"/admin/users/{alice_id}", headers=SEED_ADMIN)
    r = client.post(f"/admin/users/{alice_id}/restore", headers=SEED_ADMIN)
    assert r.status_code == 200 and r.json()["deleted_at"] is None
    assert client.post("/auth/login", json={"login": "alice", "password": "password123"}).status_code == 200
    assert client.post(f"/admin/users/{alice_id}/restore", headers=SEED_ADMIN).json()["code"] == "not_deleted"


def test_a_deleted_accounts_role_cannot_change(db, make_user):
    seed_admin_password(db)
    make_user("alice")
    alice_id = user_id(db, "alice")
    client.delete(f"/admin/users/{alice_id}", headers=SEED_ADMIN)
    r = client.patch(f"/admin/users/{alice_id}", json={"role": "admin", "password": ADMIN_PASSWORD}, headers=SEED_ADMIN)
    assert r.status_code == 409 and r.json()["code"] == "user_deleted"


def test_deleted_admins_do_not_count_as_admins(db, make_user):
    seed_admin_password(db)
    make_user("boss", "admin")
    assert client.delete(f"/admin/users/{user_id(db, 'boss')}", headers=SEED_ADMIN).status_code == 204
    demote = {"role": "user", "password": ADMIN_PASSWORD}
    assert client.patch("/admin/users/1", json=demote, headers=SEED_ADMIN).json()["code"] == "last_admin"
    assert client.get("/admin/stats", headers=SEED_ADMIN).json()["admins"] == 1


def test_stats(db, make_user):
    make_user("alice")
    stats = client.get("/admin/stats", headers=SEED_ADMIN).json()
    assert (stats["users"], stats["admins"], stats["deleted_users"]) == (2, 1, 0)
    assert stats["satellites"] >= 20 and stats["places"] >= 0 and isinstance(stats["imports"], list)


def test_my_locations_are_my_own_even_for_admins(db, make_user):
    alice = make_user("alice")
    client.post("/observers", json=HOME, headers=alice)
    assert [o["name"] for o in client.get("/observers", headers=SEED_ADMIN).json()] == ["Almaty"]


def test_concurrent_demotions_cannot_remove_every_admin():
    # Two admins demoting each other at the same moment: the second check must wait for the first to commit.
    # Uses committed rows and its own sessions (the rollback fixture can't show two transactions), cleaned up below.
    import threading

    from app.db import SessionLocal
    from app.errors import Conflict
    from app.services.admin import _check_not_last_admin, set_role

    with SessionLocal() as setup:
        a = UserModel(username="race_a", email="race_a@example.com", password_hash="x", role="admin")
        b = UserModel(username="race_b", email="race_b@example.com", password_hash="x", role="admin")
        setup.add_all([a, b])
        setup.query(UserModel).filter(UserModel.id == 1).update({"role": "user"})  # leave exactly a and b as admins
        setup.commit()
        a_id, b_id = a.id, b.id
    outcome = {}
    try:
        first = SessionLocal()
        _check_not_last_admin(first, first.get(UserModel, a_id))  # first request has checked (2 admins), not yet committed

        def second_request():
            with SessionLocal() as second:
                try:
                    set_role(second, b_id, "user")
                    outcome["second"] = "demoted"
                except Conflict as exc:
                    outcome["second"] = exc.code

        thread = threading.Thread(target=second_request)
        thread.start()
        thread.join(timeout=1)
        assert thread.is_alive(), "the second request didn't wait for the first one"
        first.get(UserModel, a_id).role = "user"
        first.commit()
        first.close()
        thread.join(timeout=10)
        assert outcome["second"] == "last_admin"
    finally:
        with SessionLocal() as cleanup:
            cleanup.query(UserModel).filter(UserModel.username.in_(["race_a", "race_b"])).delete()
            cleanup.query(UserModel).filter(UserModel.id == 1).update({"role": "admin"})
            cleanup.commit()
