import os
from pathlib import Path

import pytest
from dotenv import dotenv_values, load_dotenv

# Point the app at the test database before app.db creates its engine.
load_dotenv()
TEST_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_URL:
    raise RuntimeError("Set TEST_DATABASE_URL in .env (see .env.example)")
if TEST_URL == dotenv_values().get("DATABASE_URL"):
    raise RuntimeError("TEST_DATABASE_URL must not be the main database: the tests wipe it")
os.environ["DATABASE_URL"] = TEST_URL
os.environ.setdefault("JWT_SECRET", "test-secret-" + "0" * 40)  # tests run even without a secret in .env

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db import engine, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    """Rebuild the test database from the migrations (this also checks they work both ways)."""
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.downgrade(config, "base")
    command.upgrade(config, "head")


@pytest.fixture
def db():
    """Each test runs in a transaction that is rolled back, so tests start from the seed data."""
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        app.dependency_overrides[get_db] = lambda: session
        yield session
        app.dependency_overrides.clear()
        session.close()
        transaction.rollback()


@pytest.fixture
def make_user(db):
    """make_user("alice", role="user") adds a user (password "password123") and returns headers with its token."""
    from app.models import UserModel
    from app.security import create_access_token, hash_password

    password_hash = hash_password("password123")

    def make(username, role="user"):
        user = UserModel(username=username, email=f"{username}@example.com", password_hash=password_hash, role=role)
        db.add(user)
        db.flush()
        return {"Authorization": f"Bearer {create_access_token(user.id)}"}

    return make
