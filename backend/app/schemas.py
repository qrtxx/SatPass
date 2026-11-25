"""Pydantic models for requests and responses."""

from datetime import datetime, timezone
from typing import Annotated, Literal

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
    owner_id: int = Field(description="The user this location belongs to")
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


# --- Catalog import -------------------------------------------------------------

CelestrakGroup = Literal["active", "stations", "visual", "weather", "science", "gps-ops", "galileo", "starlink"]


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"group": "stations"}})

    group: CelestrakGroup = Field(description="CelesTrak group: 'active' is every working satellite (~17k, takes about a minute)")


class SkippedRecord(BaseModel):
    norad_id: int | None
    reason: str


class ImportResult(BaseModel):
    group: str
    fetched_at: datetime
    received: int = Field(description="Records CelesTrak sent (duplicates included)")
    added: int
    updated: int = Field(description="Existing satellites that got a newer element set")
    unchanged: int = Field(description="Existing satellites whose stored element set is as new or newer")
    skipped: int = Field(description="Records rejected by validation")
    skipped_examples: list[SkippedRecord] = Field(description="Up to 10 rejected records and why")


# --- Accounts -------------------------------------------------------------------

Username = Annotated[str, Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")]
Email = Annotated[str, Field(min_length=1, max_length=254)]  # deliberately no format check
Password = Annotated[str, Field(min_length=8, max_length=128)]  # not stripped: spaces are part of the password


class UserCreate(BaseModel):
    # extra="forbid" so a client can't choose its own role.
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"username": "alice", "email": "alice@example.com", "password": "correct horse battery"}},
    )

    username: Username
    email: Email
    password: Password


class LoginRequest(BaseModel):
    # Plain strings: a wrong value is just bad credentials (401), not a validation error.
    model_config = ConfigDict(json_schema_extra={"example": {"login": "alice", "password": "correct horse battery"}})

    login: str = Field(description="Username or email")
    password: str


class User(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    role: Literal["user", "admin"]
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(description="Seconds until the token expires")
