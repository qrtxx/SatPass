"""Accounts: registration, login and passwords."""

from pydantic import TypeAdapter
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import Conflict, NotFound, Unauthorized
from app.models import UserModel
from app.schemas import LoginRequest, Password, Token, UserCreate
from app.security import ACCESS_TOKEN_MINUTES, create_access_token, hash_password, verify_password

# Checked when the user doesn't exist, so a wrong username takes as long as a wrong password.
_DUMMY_HASH = hash_password("timing-equalizer")


def _same(column, value: str):
    # Both sides lowercased by PostgreSQL, the same way as the unique indexes (Python's lower() can differ for non-ASCII).
    return func.lower(column) == func.lower(value)


def find_user(db: Session, login: str) -> UserModel | None:
    """By username, or else by email, ignoring case. A username match wins: emails aren't format-checked,
    so someone could register the email "alice" and would otherwise shadow the user named alice."""
    return db.scalar(select(UserModel).where(_same(UserModel.username, login))) or db.scalar(
        select(UserModel).where(_same(UserModel.email, login))
    )


def register_user(db: Session, data: UserCreate) -> UserModel:
    # The unique indexes on lower(username)/lower(email) are the final guard; these give readable errors first.
    if db.scalar(select(UserModel.id).where(_same(UserModel.username, data.username))):
        raise Conflict("username_taken", f"The username '{data.username}' is already taken")
    if db.scalar(select(UserModel.id).where(_same(UserModel.email, data.email))):
        raise Conflict("email_taken", "An account with this email already exists")
    user = UserModel(username=data.username, email=data.email, password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    return user


def login(db: Session, data: LoginRequest) -> Token:
    user = find_user(db, data.login)
    password_ok = verify_password(data.password, user.password_hash if user else _DUMMY_HASH)
    if not (user and password_ok):
        # One message for both cases, so nobody can find out which usernames exist.
        raise Unauthorized("invalid_credentials", "Wrong username/email or password")
    return Token(access_token=create_access_token(user.id), expires_in=ACCESS_TOKEN_MINUTES * 60)


def set_password(db: Session, username: str, password: str) -> None:
    user = db.scalar(select(UserModel).where(_same(UserModel.username, username)))
    if user is None:
        raise NotFound("user_not_found", f"No user named '{username}'")
    user.password_hash = hash_password(TypeAdapter(Password).validate_python(password))
    db.commit()
