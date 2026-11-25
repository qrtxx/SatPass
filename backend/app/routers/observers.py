from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from app.db import DbSession
from app.dependencies import CurrentUser
from app.schemas import ErrorResponse, Observer, ObserverCreate, ObserverUpdate, PassReport, Satellite, WatchlistAdd
from app.services import observers as service

router = APIRouter(
    prefix="/observers",
    tags=["Observers & passes"],
    responses={
        401: {"model": ErrorResponse, "description": "Not logged in"},
        403: {"model": ErrorResponse, "description": "The location belongs to another user"},
    },
)

NOT_FOUND = {404: {"model": ErrorResponse, "description": "Observer (or satellite) not found"}}
CONFLICT = {409: {"model": ErrorResponse, "description": "Conflicts with the current state"}}
RULE = {422: {"model": ErrorResponse, "description": "Validation or business-rule error"}}
ObserverId = Annotated[int, Path(gt=0)]
# Each satellite costs ~1,500 SGP4 runs per day of predictions, like a watchlist entry.
MAX_SELECTED = 20


@router.get("", response_model=list[Observer])
def list_observers(db: DbSession, user: CurrentUser):
    return service.list_observers(db, user)


@router.post("", response_model=Observer, status_code=status.HTTP_201_CREATED, responses={**CONFLICT, **RULE})
def create_observer(db: DbSession, user: CurrentUser, data: ObserverCreate):
    return service.create_observer(db, user, data)


@router.get("/{observer_id}", response_model=Observer, responses=NOT_FOUND)
def get_observer(db: DbSession, user: CurrentUser, observer_id: ObserverId):
    return service.get_observer(db, user, observer_id)


@router.patch("/{observer_id}", response_model=Observer, responses={**NOT_FOUND, **CONFLICT, **RULE})
def update_observer(db: DbSession, user: CurrentUser, data: ObserverUpdate, observer_id: ObserverId):
    return service.update_observer(db, user, observer_id, data)


@router.delete("/{observer_id}", status_code=status.HTTP_204_NO_CONTENT, responses=NOT_FOUND)
def delete_observer(db: DbSession, user: CurrentUser, observer_id: ObserverId):
    service.delete_observer(db, user, observer_id)


@router.get("/{observer_id}/watchlist", response_model=list[Satellite], responses=NOT_FOUND)
def get_watchlist(db: DbSession, user: CurrentUser, observer_id: ObserverId):
    return service.get_watchlist(db, user, observer_id)


@router.post(
    "/{observer_id}/watchlist",
    response_model=Satellite,
    status_code=status.HTTP_201_CREATED,
    summary="Watch a satellite",
    responses={**NOT_FOUND, 409: {"model": ErrorResponse, "description": "Already watched, or the watchlist is full"}},
)
def add_to_watchlist(db: DbSession, user: CurrentUser, data: WatchlistAdd, observer_id: ObserverId):
    return service.add_to_watchlist(db, user, observer_id, data.norad_id)


@router.delete(
    "/{observer_id}/watchlist/{norad_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Stop watching a satellite",
    responses=NOT_FOUND,
)
def remove_from_watchlist(db: DbSession, user: CurrentUser, observer_id: ObserverId, norad_id: Annotated[int, Path(gt=0)]):
    service.remove_from_watchlist(db, user, observer_id, norad_id)


@router.get(
    "/{observer_id}/passes",
    response_model=PassReport,
    summary="Predict passes over this observer, for the watchlist or for chosen satellites",
    responses={**NOT_FOUND, 409: {"model": ErrorResponse, "description": "The watchlist is empty"}},
)
def get_passes(
    db: DbSession,
    user: CurrentUser,
    observer_id: ObserverId,
    hours: int = Query(24, ge=1, le=72, description="How far ahead to look"),
    min_elevation: float | None = Query(None, ge=0, le=90, description="Lowest peak height; defaults to the observer's setting"),
    start: datetime | None = Query(None, description="UTC start time, defaults to now"),
    norad_id: list[int] | None = Query(
        None, max_length=MAX_SELECTED, description=f"Satellites to predict for (repeat the parameter, up to {MAX_SELECTED}); defaults to the watchlist"
    ),
):
    return service.predict_passes(db, user, observer_id, start, hours, min_elevation, norad_id)
