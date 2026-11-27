from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from app.db import DbSession
from app.dependencies import AdminUser, require_admin
from app.schemas import AdminStats, AdminUserDetail, ErrorResponse, RoleUpdate, User
from app.schemas import AdminUser as AdminUserRow
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


@router.get("/users", response_model=list[AdminUserRow])
def list_users(
    db: DbSession,
    search: Annotated[str | None, Query(max_length=100, description="Part of a username or email")] = None,
    include_deleted: Annotated[bool, Query(description="Also list deleted (soft-deleted) accounts")] = False,
):
    return service.list_users(db, search, include_deleted)


@router.get("/users/{user_id}", response_model=AdminUserDetail, responses=NOT_FOUND)
def get_user(db: DbSession, user_id: UserId):
    return service.user_detail(db, user_id)


@router.patch(
    "/users/{user_id}",
    response_model=User,
    summary="Change a user's role (re-type your own password to confirm)",
    responses={**NOT_FOUND, **LAST_ADMIN},
)
def set_role(db: DbSession, user_id: UserId, data: RoleUpdate, actor: AdminUser):
    service.confirm_password(actor, data.password)
    return service.set_role(db, user_id, data.role)


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an account (soft delete: it can't log in; its data stays and it can be restored)",
    responses={**NOT_FOUND, 409: {"model": ErrorResponse, "description": "Already deleted, or the only administrator"}},
)
def delete_user(db: DbSession, user_id: UserId):
    service.delete_user(db, user_id)


@router.post(
    "/users/{user_id}/restore",
    response_model=AdminUserDetail,
    summary="Restore a deleted account",
    responses={**NOT_FOUND, 409: {"model": ErrorResponse, "description": "The account isn't deleted"}},
)
def restore_user(db: DbSession, user_id: UserId):
    service.restore_user(db, user_id)
    return service.user_detail(db, user_id)
