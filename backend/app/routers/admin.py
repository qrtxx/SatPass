from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from app.db import DbSession
from app.dependencies import require_admin
from app.schemas import AdminStats, AdminUser, AdminUserDetail, ErrorResponse, RoleUpdate, User
from app.services import admin as service

# Everything here is for administrators only.
router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(require_admin)],
    responses={
        401: {"model": ErrorResponse, "description": "Not logged in"},
        403: {"model": ErrorResponse, "description": "Administrators only"},
    },
)
UserId = Annotated[int, Path(gt=0)]
LAST_ADMIN = {409: {"model": ErrorResponse, "description": "This is the only administrator"}}
NOT_FOUND = {404: {"model": ErrorResponse, "description": "No such user"}}


@router.get("/stats", response_model=AdminStats, summary="Counts for the dashboard, and the last orbit-data imports")
def stats(db: DbSession):
    return service.stats(db)


@router.get("/users", response_model=list[AdminUser])
def list_users(db: DbSession, search: Annotated[str | None, Query(max_length=100, description="Part of a username or email")] = None):
    return service.list_users(db, search)


@router.get("/users/{user_id}", response_model=AdminUserDetail, responses=NOT_FOUND)
def get_user(db: DbSession, user_id: UserId):
    return service.user_detail(db, user_id)


@router.patch("/users/{user_id}", response_model=User, summary="Change a user's role", responses={**NOT_FOUND, **LAST_ADMIN})
def set_role(db: DbSession, user_id: UserId, data: RoleUpdate):
    return service.set_role(db, user_id, data.role)


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an account and its locations",
    responses={**NOT_FOUND, **LAST_ADMIN},
)
def delete_user(db: DbSession, user_id: UserId):
    service.delete_user(db, user_id)
