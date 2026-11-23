from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response, status

from app.db import DbSession
from app.schemas import ErrorResponse, ImportRequest, ImportResult, Position, Satellite, SatelliteCreate, SatelliteUpdate
from app.services import catalog_import
from app.services import satellites as service
from app.services.celestrak import Fetcher, get_fetcher

router = APIRouter(prefix="/satellites", tags=["Satellites"])

NOT_FOUND = {404: {"model": ErrorResponse, "description": "Satellite not found"}}
RULE = {422: {"model": ErrorResponse, "description": "Validation or business-rule error"}}
NoradId = Annotated[int, Path(gt=0, description="NORAD catalog number, e.g. 25544 for the ISS")]


@router.get(
    "",
    response_model=list[Satellite],
    summary="List or search the catalog",
    description="The X-Total-Count response header holds the number of matches, for paging.",
)
def list_satellites(
    db: DbSession,
    response: Response,
    search: str | None = Query(None, min_length=1, max_length=60, description="Part of the name, or an exact NORAD ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    response.headers["X-Total-Count"] = str(service.count_satellites(db, search))
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


@router.post(
    "/import",
    response_model=ImportResult,
    summary="Download a CelesTrak group and add or refresh its satellites",
    description="Adds new satellites and updates those with a newer EPOCH. Invalid records are skipped. "
    "Each group can be imported once every 2 hours (CelesTrak's rule). The 'active' group takes about a minute.",
    responses={
        409: {"model": ErrorResponse, "description": "Another import is still running"},
        429: {"model": ErrorResponse, "description": "This group was imported less than 2 hours ago (see Retry-After)"},
        502: {"model": ErrorResponse, "description": "CelesTrak could not be reached or sent no orbital data"},
    },
)
def import_catalog(db: DbSession, data: ImportRequest, fetch: Annotated[Fetcher, Depends(get_fetcher)]):
    return catalog_import.import_group(db, data.group, fetch)


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
