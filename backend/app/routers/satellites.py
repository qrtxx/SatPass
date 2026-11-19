from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from app.db import DbSession
from app.schemas import ErrorResponse, Position, Satellite, SatelliteCreate, SatelliteUpdate
from app.services import satellites as service

router = APIRouter(prefix="/satellites", tags=["Satellites"])

NOT_FOUND = {404: {"model": ErrorResponse, "description": "Satellite not found"}}
RULE = {422: {"model": ErrorResponse, "description": "Validation or business-rule error"}}
NoradId = Annotated[int, Path(gt=0, description="NORAD catalog number, e.g. 25544 for the ISS")]


@router.get("", response_model=list[Satellite], summary="List or search the catalog")
def list_satellites(
    db: DbSession,
    search: str | None = Query(None, min_length=1, max_length=60, description="Part of the name, or an exact NORAD ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return service.list_satellites(db, search, limit, offset)


@router.post(
    "",
    response_model=Satellite,
    status_code=status.HTTP_201_CREATED,
    summary="Add a satellite from its orbital elements",
    responses={409: {"model": ErrorResponse, "description": "NORAD ID already in the catalog"}, **RULE},
)
def create_satellite(db: DbSession, data: SatelliteCreate):
    return service.create_satellite(db, data)


@router.get("/{norad_id}", response_model=Satellite, responses=NOT_FOUND)
def get_satellite(db: DbSession, norad_id: NoradId):
    return service.get_satellite(db, norad_id)


@router.patch(
    "/{norad_id}",
    response_model=Satellite,
    summary="Rename a satellite or load a newer element set",
    responses={**NOT_FOUND, 409: {"model": ErrorResponse, "description": "New EPOCH is not later than the current one"}, **RULE},
)
def update_satellite(db: DbSession, data: SatelliteUpdate, norad_id: NoradId):
    return service.update_satellite(db, norad_id, data)


@router.delete(
    "/{norad_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a satellite (also removes it from every watchlist)",
    responses=NOT_FOUND,
)
def delete_satellite(db: DbSession, norad_id: NoradId):
    service.delete_satellite(db, norad_id)


@router.get(
    "/{norad_id}/position",
    response_model=Position,
    summary="Where the satellite is above Earth",
    responses={**NOT_FOUND, **RULE},
)
def get_position(db: DbSession, norad_id: NoradId, at: datetime | None = Query(None, description="UTC time, defaults to now")):
    return service.get_position(db, norad_id, at)
