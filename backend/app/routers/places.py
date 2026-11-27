from typing import Annotated

from fastapi import APIRouter, Query

from app.db import DbSession
from app.errors import RuleViolation
from app.schemas import ErrorResponse, NearestPlace, Place
from app.services import places as service

router = APIRouter(prefix="/places", tags=["Places"])


@router.get("", response_model=list[Place], summary="Find towns and villages by name (suggestions while typing)")
def search_places(
    db: DbSession,
    search: Annotated[str, Query(min_length=2, max_length=100, description="Start of the name, e.g. 'ast'")],
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
):
    # Count the characters that matter: "  " or " a" would otherwise match (and sort) the whole table.
    if len(search.strip()) < 2:
        raise RuleViolation("search_too_short", "Type at least 2 letters of the name")
    return service.search_places(db, search, limit)


@router.get(
    "/nearest",
    response_model=NearestPlace,
    summary="The nearest town or village (e.g. to estimate a location's elevation)",
    responses={404: {"model": ErrorResponse, "description": "Nothing within 50 km"}},
)
def nearest_place(
    db: DbSession,
    latitude: Annotated[float, Query(ge=-90, le=90)],
    longitude: Annotated[float, Query(ge=-180, le=180)],
):
    place, distance = service.nearest_place(db, latitude, longitude)
    return NearestPlace(**Place.model_validate(place).model_dump(), distance_km=round(distance, 1))
