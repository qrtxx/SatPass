from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from app.schemas import ErrorResponse, Observer, ObserverCreate, ObserverUpdate, PassReport, Satellite, WatchlistAdd
from app.services import observers as service

router = APIRouter(prefix="/observers", tags=["Observers & passes"])

NOT_FOUND = {404: {"model": ErrorResponse, "description": "Observer (or satellite) not found"}}
CONFLICT = {409: {"model": ErrorResponse, "description": "Conflicts with the current state"}}
RULE = {422: {"model": ErrorResponse, "description": "Validation or business-rule error"}}
ObserverId = Annotated[int, Path(gt=0)]


@router.get("", response_model=list[Observer])
def list_observers():
    return service.list_observers()


@router.post("", response_model=Observer, status_code=status.HTTP_201_CREATED, responses={**CONFLICT, **RULE})
def create_observer(data: ObserverCreate):
    return service.create_observer(data)


@router.get("/{observer_id}", response_model=Observer, responses=NOT_FOUND)
def get_observer(observer_id: ObserverId):
    return service.get_observer(observer_id)


@router.patch("/{observer_id}", response_model=Observer, responses={**NOT_FOUND, **CONFLICT, **RULE})
def update_observer(data: ObserverUpdate, observer_id: ObserverId):
    return service.update_observer(observer_id, data)


@router.delete("/{observer_id}", status_code=status.HTTP_204_NO_CONTENT, responses=NOT_FOUND)
def delete_observer(observer_id: ObserverId):
    service.delete_observer(observer_id)


@router.get("/{observer_id}/watchlist", response_model=list[Satellite], responses=NOT_FOUND)
def get_watchlist(observer_id: ObserverId):
    return service.get_watchlist(observer_id)


@router.post(
    "/{observer_id}/watchlist",
    response_model=Satellite,
    status_code=status.HTTP_201_CREATED,
    summary="Watch a satellite",
    responses={**NOT_FOUND, 409: {"model": ErrorResponse, "description": "Already watched, or the watchlist is full"}},
)
def add_to_watchlist(data: WatchlistAdd, observer_id: ObserverId):
    return service.add_to_watchlist(observer_id, data.norad_id)


@router.delete(
    "/{observer_id}/watchlist/{norad_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Stop watching a satellite",
    responses=NOT_FOUND,
)
def remove_from_watchlist(observer_id: ObserverId, norad_id: Annotated[int, Path(gt=0)]):
    service.remove_from_watchlist(observer_id, norad_id)


@router.get(
    "/{observer_id}/passes",
    response_model=PassReport,
    summary="Predict passes of the watched satellites over this observer",
    responses={**NOT_FOUND, 409: {"model": ErrorResponse, "description": "The watchlist is empty"}},
)
def get_passes(
    observer_id: ObserverId,
    hours: int = Query(24, ge=1, le=72, description="How far ahead to look"),
    min_elevation: float | None = Query(None, ge=0, le=90, description="Lowest peak height; defaults to the observer's setting"),
    start: datetime | None = Query(None, description="UTC start time, defaults to now"),
):
    return service.predict_passes(observer_id, start, hours, min_elevation)
