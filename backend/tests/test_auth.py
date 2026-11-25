import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import UserModel
from app.security import ACCESS_TOKEN_MINUTES
from app.services.auth import set_password

client = TestClient(app)
ALICE = {"username": "alice", "email": "alice@example.com", "password": "password123"}


def login(login_name, password):
    return client.post("/auth/login", json={"login": login_name, "password": password})


def test_register_returns_user_without_password(db):
    r = client.post("/auth/register", json=ALICE)
    assert r.status_code == 201
    body = r.json()
    assert (body["username"], body["email"], body["role"]) == ("alice", "alice@example.com", "user")
    assert "password" not in r.text and "hash" not in r.text


def test_password_is_stored_hashed(db):
    client.post("/auth/register", json=ALICE)
    stored = db.scalar(select(UserModel.password_hash).where(UserModel.username == "alice"))
    assert stored.startswith("$argon2id$") and "password123" not in stored


@pytest.mark.parametrize(
    "changes, code",
    [
        ({"username": "ALICE", "email": "other@example.com"}, "username_taken"),  # same username, other case
        ({"username": "alice2", "email": "Alice@Example.com"}, "email_taken"),  # same email, other case
    ],
)
def test_duplicate_registration(db, changes, code):
    client.post("/auth/register", json=ALICE)
    r = client.post("/auth/register", json={**ALICE, **changes})
    assert r.status_code == 409 and r.json()["code"] == code


def test_email_format_is_not_checked(db):  # a deliberate choice: any non-empty text is accepted
    assert client.post("/auth/register", json={**ALICE, "email": "not-an-email"}).status_code == 201


@pytest.mark.parametrize(
    "changes",
    [
        {"username": "al"},  # too short
        {"username": "al ice"},  # bad characters
        {"password": "short"},  # password < 8
        {"email": ""},  # email empty
        {"role": "admin"},  # role can't be chosen
    ],
)
def test_register_validation(db, changes):
    assert client.post("/auth/register", json={**ALICE, **changes}).status_code == 422


def test_login_and_me(db):
    client.post("/auth/register", json=ALICE)
    token = login("alice", "password123").json()
    assert token["token_type"] == "bearer" and token["expires_in"] == ACCESS_TOKEN_MINUTES * 60
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token['access_token']}"})
    assert me.status_code == 200 and me.json()["username"] == "alice"


@pytest.mark.parametrize("login_name", ["alice", "ALICE", "alice@example.com", "Alice@Example.COM"])
def test_login_with_username_or_email_ignoring_case(db, login_name):
    client.post("/auth/register", json=ALICE)
    assert login(login_name, "password123").status_code == 200


def test_password_whitespace_is_significant(db):
    client.post("/auth/register", json={**ALICE, "password": " pass word "})
    assert login("alice", " pass word ").status_code == 200
    assert login("alice", "pass word").status_code == 401


@pytest.mark.parametrize("login_name, password", [("alice", "wrong-password"), ("nobody", "password123")])
def test_invalid_credentials(db, login_name, password):
    client.post("/auth/register", json=ALICE)
    r = login(login_name, password)
    assert r.status_code == 401 and r.json()["code"] == "invalid_credentials"
    assert r.headers["WWW-Authenticate"] == "Bearer"


def test_wrong_user_and_wrong_password_get_the_same_answer(db):
    # Different messages would let anyone find out which usernames exist.
    client.post("/auth/register", json=ALICE)
    assert login("alice", "wrong-password").json() == login("nobody", "password123").json()


def test_seeded_admin_cannot_log_in_until_password_set(db):
    assert login("admin", "!").status_code == 401
    set_password(db, "admin", "admin-password-1")
    r = login("admin", "admin-password-1")
    assert r.status_code == 200
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.json()["role"] == "admin"


@pytest.mark.parametrize(
    "headers, code",
    [
        ({}, "not_authenticated"),
        ({"Authorization": "Basic abc"}, "not_authenticated"),
        ({"Authorization": "Bearer"}, "not_authenticated"),
        ({"Authorization": "Bearer garbage"}, "invalid_token"),
    ],
)
def test_malformed_authorization_header(db, headers, code):
    r = client.get("/auth/me", headers=headers)
    assert r.status_code == 401 and r.json()["code"] == code


def test_token_of_deleted_user_is_rejected(db, make_user):
    headers = make_user("ghost")
    db.delete(db.scalar(select(UserModel).where(UserModel.username == "ghost")))
    db.flush()
    assert client.get("/auth/me", headers=headers).json()["code"] == "invalid_token"


def test_cli_rejects_mismatched_passwords(monkeypatch, capsys):
    from app import cli

    answers = iter(["password-one", "password-two"])
    monkeypatch.setattr(cli, "getpass", lambda prompt: next(answers))
    assert cli.main(["set-password", "admin"]) == 1
    assert "don't match" in capsys.readouterr().err


def test_an_email_cannot_take_over_a_username_at_login(db):
    # Emails aren't format-checked, so "alice" is a valid email. A username match must win at login.
    client.post("/auth/register", json={"username": "bob", "email": "alice", "password": "bob-password-1"})
    client.post("/auth/register", json=ALICE)
    r = login("alice", "password123")
    assert r.status_code == 200
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}).json()
    assert me["username"] == "alice"
    assert login("bob", "bob-password-1").status_code == 200  # Bob still logs in with his username
