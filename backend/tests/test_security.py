from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.errors import Unauthorized
from app.security import (
    JWT_SECRET,
    UNUSABLE_PASSWORD,
    create_access_token,
    decode_access_token,
    hash_password,
    load_secret,
    verify_password,
)

FUTURE = datetime.now(timezone.utc) + timedelta(hours=1)


def test_hash_is_salted_and_verifies():
    h1, h2 = hash_password("correct horse"), hash_password("correct horse")
    assert h1.startswith("$argon2id$") and h1 != h2 and "correct horse" not in h1
    assert verify_password("correct horse", h1) and not verify_password("wrong", h1)


def test_unusable_and_garbage_hashes_never_verify():
    assert not verify_password("anything", UNUSABLE_PASSWORD)
    assert not verify_password("anything", "not-a-hash")


def test_token_round_trip():
    assert decode_access_token(create_access_token(42)) == 42


def test_expired_token():
    with pytest.raises(Unauthorized) as e:
        decode_access_token(create_access_token(42, minutes=-1))
    assert e.value.code == "token_expired"


@pytest.mark.parametrize(
    "token",
    [
        "garbage",
        jwt.encode({"sub": "42", "exp": FUTURE}, "x" * 40, algorithm="HS256"),  # signed with another secret
        jwt.encode({"sub": "42", "exp": FUTURE}, None, algorithm="none"),  # unsigned
        jwt.encode({"exp": FUTURE}, JWT_SECRET, algorithm="HS256"),  # no subject
        jwt.encode({"sub": "abc", "exp": FUTURE}, JWT_SECRET, algorithm="HS256"),  # subject isn't a user id
    ],
)
def test_unsigned_and_foreign_tokens_are_rejected(token):
    with pytest.raises(Unauthorized) as e:
        decode_access_token(token)
    assert e.value.code == "invalid_token"


def test_unauthorized_asks_for_a_bearer_token():
    assert Unauthorized("invalid_token", "x").headers == {"WWW-Authenticate": "Bearer"}


@pytest.mark.parametrize("env", [{}, {"JWT_SECRET": "short"}])
def test_secret_is_required_and_long(env):
    with pytest.raises(RuntimeError):
        load_secret(env)
