"""Administration: users, their roles and their data."""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.errors import Conflict, NotFound
from app.models import CatalogImportModel, ObserverModel, PlaceModel, SatelliteModel, UserModel
from app.schemas import AdminStats, AdminUser, AdminUserDetail, ImportSummary, Observer


def _count(db: Session, query) -> int:
    return db.scalar(select(func.count()).select_from(query.subquery()))


def stats(db: Session) -> AdminStats:
    return AdminStats(
        users=_count(db, select(UserModel.id)),
        admins=_count(db, select(UserModel.id).where(UserModel.role == "admin")),
        satellites=_count(db, select(SatelliteModel.NORAD_CAT_ID)),
        places=_count(db, select(PlaceModel.id)),
        imports=[ImportSummary.model_validate(i) for i in db.scalars(select(CatalogImportModel).order_by(CatalogImportModel.group_name))],
    )


def list_users(db: Session, search: str | None) -> list[AdminUser]:
    locations = select(func.count(ObserverModel.id)).where(ObserverModel.owner_id == UserModel.id).scalar_subquery()
    query = select(UserModel, locations).order_by(UserModel.id)
    if search:
        query = query.where(or_(func.lower(UserModel.username).contains(search.lower(), autoescape=True), func.lower(UserModel.email).contains(search.lower(), autoescape=True)))
    return [AdminUser(**_user_fields(user), location_count=count) for user, count in db.execute(query)]


def _user_fields(user: UserModel) -> dict:
    return {"id": user.id, "username": user.username, "email": user.email, "role": user.role, "created_at": user.created_at}


def get_user(db: Session, user_id: int) -> UserModel:
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
    admins = db.scalars(select(UserModel.id).where(UserModel.role == "admin").with_for_update()).all()
    if user.role == "admin" and len(admins) == 1:
        raise Conflict("last_admin", "This is the only administrator; make someone else an admin first")


def set_role(db: Session, user_id: int, role: str) -> UserModel:
    user = get_user(db, user_id)
    if role != "admin":
        _check_not_last_admin(db, user)
    user.role = role
    db.commit()
    return user


def delete_user(db: Session, user_id: int) -> None:
    user = get_user(db, user_id)
    _check_not_last_admin(db, user)
    db.delete(user)  # their locations and watchlists go too (ON DELETE CASCADE)
    db.commit()
