"""Pydantic models for requests and responses."""

from datetime import datetime, timezone
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, computed_field


def as_utc(value: datetime) -> datetime:
    # CelesTrak epochs have no time zone but are UTC.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


UtcDatetime = Annotated[datetime, AfterValidator(as_utc)]
SatName = Annotated[str, Field(min_length=1, max_length=60)]
Angle = Annotated[float, Field(ge=0, lt=360)]
MeanMotion = Annotated[float, Field(gt=0, le=20, description="Revolutions per day")]
Eccentricity = Annotated[float, Field(ge=0, lt=1)]
Inclination = Annotated[float, Field(ge=0, le=180)]

ISS_EXAMPLE = {
    "OBJECT_NAME": "ISS (ZARYA)",
    "NORAD_CAT_ID": 25544,
    "EPOCH": "2026-11-04T21:15:15.204960",
    "MEAN_MOTION": 15.49180468,
    "ECCENTRICITY": 0.00072122,
    "INCLINATION": 51.6327,
    "RA_OF_ASC_NODE": 323.8448,
    "ARG_OF_PERICENTER": 348.649,
    "MEAN_ANOMALY": 11.4335,
    "BSTAR": 0.00010456704,
    "MEAN_MOTION_DOT": 0.00005352,
    "MEAN_MOTION_DDOT": 0,
}


class ErrorResponse(BaseModel):
    detail: str
    code: str


# --- Satellites -------------------------------------------------------------


class SatelliteCreate(BaseModel):
    """Orbital elements in CelesTrak's OMM JSON format, so a CelesTrak record can be pasted as is."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True, json_schema_extra={"example": ISS_EXAMPLE})

    OBJECT_NAME: SatName
    NORAD_CAT_ID: int = Field(gt=0, lt=1_000_000_000)
    EPOCH: UtcDatetime
    MEAN_MOTION: MeanMotion
    ECCENTRICITY: Eccentricity
    INCLINATION: Inclination
    RA_OF_ASC_NODE: Angle
    ARG_OF_PERICENTER: Angle
    MEAN_ANOMALY: Angle
    BSTAR: float = 0
    MEAN_MOTION_DOT: float = 0
    MEAN_MOTION_DDOT: float = 0


class SatelliteUpdate(BaseModel):
    """Rename a satellite, or replace its orbital elements with a newer set (a new EPOCH is required)."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={"example": {"EPOCH": "2026-11-05T09:30:00", "MEAN_ANOMALY": 120.5}},
    )

    OBJECT_NAME: SatName | None = None
    EPOCH: UtcDatetime | None = None
    MEAN_MOTION: MeanMotion | None = None
    ECCENTRICITY: Eccentricity | None = None
    INCLINATION: Inclination | None = None
    RA_OF_ASC_NODE: Angle | None = None
    ARG_OF_PERICENTER: Angle | None = None
    MEAN_ANOMALY: Angle | None = None
    BSTAR: float | None = None
    MEAN_MOTION_DOT: float | None = None
    MEAN_MOTION_DDOT: float | None = None


class Satellite(SatelliteCreate):
    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def period_minutes(self) -> float:
        return round(1440 / self.MEAN_MOTION, 2)


class Position(BaseModel):
    norad_id: int
    time: datetime
    latitude: float
    longitude: float
    altitude_km: float
    orbit_age_days: float


# --- Observers & watchlist ----------------------------------------------------


class ObserverCreate(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={"example": {"name": "Astana", "latitude": 51.1694, "longitude": 71.4491, "elevation_m": 347}},
    )

    name: str = Field(min_length=1, max_length=80)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    elevation_m: float = Field(0, ge=-500, le=9000, description="Height above sea level")
    min_elevation_deg: float = Field(10, ge=0, le=90, description="Default lowest peak height for passes")


class ObserverUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, json_schema_extra={"example": {"min_elevation_deg": 20}})

    name: str | None = Field(None, min_length=1, max_length=80)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    elevation_m: float | None = Field(None, ge=-500, le=9000)
    min_elevation_deg: float | None = Field(None, ge=0, le=90)


class Observer(ObserverCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    watchlist: list[int] = Field(default_factory=list, description="NORAD IDs of watched satellites")


class WatchlistAdd(BaseModel):
    norad_id: int = Field(gt=0, examples=[48274])


# --- Passes -------------------------------------------------------------------


class PassPoint(BaseModel):
    time: datetime
    azimuth_deg: float
    compass: str


class PeakPoint(PassPoint):
    elevation_deg: float


class SatellitePass(BaseModel):
    norad_id: int
    name: str
    rise: PassPoint
    peak: PeakPoint
    set: PassPoint
    duration_seconds: int


class PassReport(BaseModel):
    observer_id: int
    start: datetime
    end: datetime
    min_elevation_deg: float
    passes: list[SatellitePass]
    warnings: list[str]
