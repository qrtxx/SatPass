"""SQLAlchemy tables.

satellites 1 ─< watchlist_entries >─ 1 observers
An observer has many watchlist entries, and so does a satellite (two one-to-many relationships).
"""

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Double, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SatelliteModel(Base):
    __tablename__ = "satellites"
    __table_args__ = (
        CheckConstraint("norad_cat_id > 0", name="norad_positive"),
        CheckConstraint("mean_motion > 0 AND mean_motion <= 20", name="mean_motion_range"),
        CheckConstraint("eccentricity >= 0 AND eccentricity < 1", name="eccentricity_range"),
        CheckConstraint("inclination BETWEEN 0 AND 180", name="inclination_range"),
        CheckConstraint(
            "ra_of_asc_node >= 0 AND ra_of_asc_node < 360 AND arg_of_pericenter >= 0 AND arg_of_pericenter < 360 "
            "AND mean_anomaly >= 0 AND mean_anomaly < 360",
            name="angles_range",
        ),
    )

    # Attribute names match the CelesTrak OMM keys used by the API and orbit code; columns are snake_case.
    NORAD_CAT_ID: Mapped[int] = mapped_column("norad_cat_id", Integer, primary_key=True, autoincrement=False)
    OBJECT_NAME: Mapped[str] = mapped_column("object_name", String(60), index=True)
    EPOCH: Mapped[datetime] = mapped_column("epoch", DateTime(timezone=True))
    MEAN_MOTION: Mapped[float] = mapped_column("mean_motion", Double)
    ECCENTRICITY: Mapped[float] = mapped_column("eccentricity", Double)
    INCLINATION: Mapped[float] = mapped_column("inclination", Double)
    RA_OF_ASC_NODE: Mapped[float] = mapped_column("ra_of_asc_node", Double)
    ARG_OF_PERICENTER: Mapped[float] = mapped_column("arg_of_pericenter", Double)
    MEAN_ANOMALY: Mapped[float] = mapped_column("mean_anomaly", Double)
    BSTAR: Mapped[float] = mapped_column("bstar", Double, default=0, server_default="0")
    MEAN_MOTION_DOT: Mapped[float] = mapped_column("mean_motion_dot", Double, default=0, server_default="0")
    MEAN_MOTION_DDOT: Mapped[float] = mapped_column("mean_motion_ddot", Double, default=0, server_default="0")

    # The database deletes the entries (ON DELETE CASCADE) when a satellite is removed.
    entries: Mapped[list["WatchlistEntry"]] = relationship(back_populates="satellite", cascade="all, delete-orphan", passive_deletes=True)


class ObserverModel(Base):
    __tablename__ = "observers"
    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="latitude_range"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="longitude_range"),
        CheckConstraint("elevation_m BETWEEN -500 AND 9000", name="elevation_range"),
        CheckConstraint("min_elevation_deg BETWEEN 0 AND 90", name="min_elevation_range"),
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        # "Almaty" and "almaty" count as the same name.
        Index("uq_observers_name_lower", text("lower(name)"), unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    latitude: Mapped[float] = mapped_column(Double)
    longitude: Mapped[float] = mapped_column(Double)
    elevation_m: Mapped[float] = mapped_column(Double, default=0, server_default="0")
    min_elevation_deg: Mapped[float] = mapped_column(Double, default=10, server_default="10")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())

    entries: Mapped[list["WatchlistEntry"]] = relationship(
        back_populates="observer", cascade="all, delete-orphan", passive_deletes=True, order_by="WatchlistEntry.added_at"
    )

    @property
    def watchlist(self) -> list[int]:
        return [entry.norad_id for entry in self.entries]


class WatchlistEntry(Base):
    __tablename__ = "watchlist_entries"

    # The composite primary key stops a satellite from being on the same watchlist twice.
    observer_id: Mapped[int] = mapped_column(ForeignKey("observers.id", ondelete="CASCADE"), primary_key=True)
    norad_id: Mapped[int] = mapped_column(ForeignKey("satellites.norad_cat_id", ondelete="CASCADE"), primary_key=True, index=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())

    observer: Mapped[ObserverModel] = relationship(back_populates="entries")
    satellite: Mapped[SatelliteModel] = relationship(back_populates="entries")
