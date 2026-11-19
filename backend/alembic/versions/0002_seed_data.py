"""seed snapshot satellites and Almaty observer

Loads the 20 satellites from src/data/sample-gp.json and one observer (Almaty) watching the ISS,
so a fresh database is ready for the Swagger demo.

Revision ID: 0e7e290e1691
Revises: aeb112db3fed
Create Date: 2026-11-19 08:13:40.000000

"""

import json
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision: str = "0e7e290e1691"
down_revision: str | Sequence[str] | None = "aeb112db3fed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SNAPSHOT = Path(__file__).resolve().parents[3] / "src" / "data" / "sample-gp.json"
ISS_ID = 25544
OMM_FIELDS = [
    "NORAD_CAT_ID", "OBJECT_NAME", "EPOCH", "MEAN_MOTION", "ECCENTRICITY", "INCLINATION", "RA_OF_ASC_NODE",
    "ARG_OF_PERICENTER", "MEAN_ANOMALY", "BSTAR", "MEAN_MOTION_DOT", "MEAN_MOTION_DDOT",
]  # fmt: skip

# Table definitions frozen at this revision, so later model changes can't break the migration.
satellites = sa.table("satellites", *(sa.column(f.lower()) for f in OMM_FIELDS))
observers = sa.table("observers", sa.column("id"), sa.column("name"), sa.column("latitude"), sa.column("longitude"), sa.column("elevation_m"))
watchlist_entries = sa.table("watchlist_entries", sa.column("observer_id"), sa.column("norad_id"))


def upgrade() -> None:
    records = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    rows = [{f.lower(): r[f] for f in OMM_FIELDS} for r in records]
    for row in rows:
        # CelesTrak epochs are UTC without a zone marker.
        row["epoch"] = datetime.fromisoformat(row["epoch"]).replace(tzinfo=timezone.utc)
    op.bulk_insert(satellites, rows)

    observer_id = op.get_bind().scalar(
        observers.insert()
        .values(name="Almaty", latitude=43.2389, longitude=76.8897, elevation_m=800)
        .returning(observers.c.id)
    )
    op.bulk_insert(watchlist_entries, [{"observer_id": observer_id, "norad_id": ISS_ID}])


def downgrade() -> None:
    norad_ids = [r["NORAD_CAT_ID"] for r in json.loads(SNAPSHOT.read_text(encoding="utf-8"))]
    # Watchlist entries of these satellites and of Almaty go too (ON DELETE CASCADE).
    op.execute(observers.delete().where(observers.c.name == "Almaty"))
    op.execute(satellites.delete().where(satellites.c.norad_cat_id.in_(norad_ids)))
