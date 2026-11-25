from fastapi import APIRouter, status

from app.db import DbSession
from app.dependencies import CurrentUser
from app.schemas import ErrorResponse, LoginRequest, Token, User, UserCreate
from app.services import auth as service

router = APIRouter(prefix="/auth", tags=["Auth"])

UNAUTHORIZED = {401: {"model": ErrorResponse, "description": "Not logged in, or the token is invalid or expired"}}


@router.post(
    "/register",
    response_model=User,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse, "description": "Username or email already taken"}},
)
def register(db: DbSession, data: UserCreate):
    return service.register_user(db, data)


@router.post(
    "/login",
    response_model=Token,
    summary="Log in with a username or email; returns a JWT access token",
    responses={401: {"model": ErrorResponse, "description": "Wrong username/email or password"}},
)
def login(db: DbSession, data: LoginRequest):
    return service.login(db, data)


@router.get("/me", response_model=User, summary="The logged-in user", responses=UNAUTHORIZED)
def me(user: CurrentUser):
    return user
