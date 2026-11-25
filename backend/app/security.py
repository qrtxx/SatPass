"""Password hashing (Argon2id) and JWT access tokens (HS256)."""

import os
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from dotenv import load_dotenv

from app.errors import Unauthorized

JWT_ALGORITHM = "HS256"
# Stored for an account that must not be able to log in yet (the seeded admin); no password ever matches it.
UNUSABLE_PASSWORD = "!"
MIN_SECRET_LENGTH = 32  # a short HMAC key can be brute-forced, letting anyone forge tokens


def load_secret(env: Mapping[str, str]) -> str:
    secret = env.get("JWT_SECRET", "")
    if len(secret) < MIN_SECRET_LENGTH:
        raise RuntimeError(
            f'JWT_SECRET must be set to at least {MIN_SECRET_LENGTH} characters. Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
        )
    return secret


load_dotenv()  # reads backend/.env; real environment variables win
JWT_SECRET = load_secret(os.environ)
ACCESS_TOKEN_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "60"))

_hasher = PasswordHasher()  # Argon2id with a random salt stored inside each hash


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: int, minutes: int = ACCESS_TOKEN_MINUTES) -> str:
    now = datetime.now(timezone.utc)
    claims = {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(claims, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> int:
    """The user id in a valid token. The algorithm is fixed, so unsigned ("alg": "none") tokens are rejected."""
    try:
        claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"require": ["exp", "sub"]})
        return int(claims["sub"])
    except jwt.ExpiredSignatureError as exc:
        raise Unauthorized("token_expired", "Your login has expired; log in again") from exc
    except (jwt.InvalidTokenError, ValueError) as exc:
        raise Unauthorized("invalid_token", "The access token is not valid") from exc
