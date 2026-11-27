"""Administration: users, their roles and their data. Deleting an account is a soft delete (see delete_user)."""

from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.errors import Conflict, Forbidden, NotFound
from app.models import CatalogImportModel, ObserverModel, PlaceModel, SatelliteModel, UserModel
from app.schemas import AdminStats, AdminUser, AdminUserDetail, ImportSummary, Observer
from app.security import verify_password

ACTIVE = UserModel.deleted_at.is_(None)


def _count(db: Session, query) -> int:
    return db.scalar(select(func.count()).select_from(query.subquery()))


def stats(db: Session) -> AdminStats:
    return AdminStats(
        users=_count(db, select(UserModel.id).where(ACTIVE)),
        admins=_count(db, select(UserModel.id).where(ACTIVE, UserModel.role == "admin")),
        deleted_users=_count(db, select(UserModel.id).where(UserModel.deleted_at.is_not(None))),
        satellites=_count(db, select(SatelliteModel.NORAD_CAT_ID)),
        places=_count(db, select(PlaceModel.id)),
        imports=[ImportSummary.model_validate(i) for i in db.scalars(select(CatalogImportModel).order_by(CatalogImportModel.group_name))],
    )


def list_users(db: Session, search: str | None, include_deleted: bool = False) -> list[AdminUser]:
    locations = select(func.count(ObserverModel.id)).where(ObserverModel.owner_id == UserModel.id).scalar_subquery()
    query = select(UserModel, locations).order_by(UserModel.id)
    if not include_deleted:
        query = query.where(ACTIVE)
    if search:
        word = search.lower()
        query = query.where(
            or_(func.lower(UserModel.username).contains(word, autoescape=True), func.lower(UserModel.email).contains(word, autoescape=True))
        )
    return [AdminUser(**_user_fields(user), location_count=count) for user, count in db.execute(query)]


def _user_fields(user: UserModel) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "created_at": user.created_at,
        "deleted_at": user.deleted_at,
    }


def get_user(db: Session, user_id: int) -> UserModel:
    """Any account, deleted ones included (admins can view and restore them)."""
    user = db.get(UserModel, user_id)
    if user is None:
        raise NotFound("user_not_found", f"No user with id {user_id}")
    return user


def user_detail(db: Session, user_id: int) -> AdminUserDetail:
    user = get_user(db, user_id)
    return AdminUserDetail(**_user_fields(user), locations=[Observer.model_validate(o) for o in user.observers])


def _check_not_last_admin(db: Session, user: UserModel) -> None:
    # Without any admin nobody could manage users again, short of editing the database by hand.
    # FOR UPDATE locks the admin rows until this request commits, so two admins demoting each other at the
    # same moment can't both see "2 admins": the second waits, re-reads, and gets last_admin.
    # Deleted admins don't count: they can't log in.
    admins = db.scalars(select(UserModel.id).where(ACTIVE, UserModel.role == "admin").with_for_update()).all()
    if user.role == "admin" and user.deleted_at is None and len(admins) == 1:
        raise Conflict("last_admin", "This is the only administrator; make someone else an admin first")


def confirm_password(actor: UserModel, password: str) -> None:
    """Sensitive changes ask the admin to re-type their own password, in case someone else is at their screen.
    403, not 401: a wrong password here must not log the admin out."""
    if not verify_password(password, actor.password_hash):
        raise Forbidden("wrong_password", "That password is wrong")


def set_role(db: Session, user_id: int, role: str) -> UserModel:
    user = get_user(db, user_id)
    if user.deleted_at is not None:
        raise Conflict("user_deleted", "This account is deleted; restore it first")
    if role != "admin":
        _check_not_last_admin(db, user)
    user.role = role
    db.commit()
    return user


def delete_user(db: Session, user_id: int) -> None:
    """Soft delete: the account is marked deleted and can't log in; its data stays and an admin can restore it.
    The username and email stay reserved, so nobody can register as a deleted user."""
    user = get_user(db, user_id)
    if user.deleted_at is not None:
        raise Conflict("already_deleted", "This account is already deleted")
    _check_not_last_admin(db, user)
    user.deleted_at = datetime.now(timezone.utc)
    db.commit()


def restore_user(db: Session, user_id: int) -> UserModel:
    user = get_user(db, user_id)
    if user.deleted_at is None:
        raise Conflict("not_deleted", "This account isn't deleted")
    user.deleted_at = None
    db.commit()
    return user
