"""Import a CelesTrak group into the catalog: add new satellites, refresh ones with a newer element set."""

import math
import threading
from datetime import datetime, timedelta, timezone

from pydantic import ValidationError
from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from app.errors import Conflict, RuleViolation, TooManyRequests
from app.models import CatalogImportModel, SatelliteModel
from app.schemas import ImportResult, SatelliteCreate, SkippedRecord
from app.services.celestrak import Fetcher
from app.services.satellites import check_elements

# CelesTrak blocks clients that download the same data again before it can have changed.
MIN_INTERVAL = timedelta(hours=2)
MAX_SKIPPED_EXAMPLES = 10
# shortcut: an in-process lock only covers one server process; with several workers, use a database lock (pg_try_advisory_lock).
IMPORT_LOCK = threading.Lock()


def _check_interval(db: Session, group: str, now: datetime) -> None:
    last = db.get(CatalogImportModel, group)
    if last is None or now - last.fetched_at >= MIN_INTERVAL:
        return
    wait = MIN_INTERVAL - (now - last.fetched_at)
    raise TooManyRequests(
        "import_too_soon",
        f"'{group}' was imported less than 2 hours ago; CelesTrak allows one download per group every 2 hours. "
        f"Try again in {math.ceil(wait.total_seconds() / 60)} min.",
        headers={"Retry-After": str(math.ceil(wait.total_seconds()))},
    )


def _validate(records: list[dict]) -> tuple[dict[int, SatelliteCreate], list[SkippedRecord]]:
    """Run each record through the same rules as POST /satellites. Keeps the newest element set per NORAD ID."""
    valid: dict[int, SatelliteCreate] = {}
    skipped: list[SkippedRecord] = []
    for record in records:
        try:
            sat = SatelliteCreate.model_validate(record)
            check_elements(sat)
        except (ValidationError, RuleViolation) as exc:
            norad_id = record.get("NORAD_CAT_ID") if isinstance(record, dict) else None
            reason = exc.code if isinstance(exc, RuleViolation) else "invalid_fields"
            skipped.append(SkippedRecord(norad_id=norad_id if isinstance(norad_id, int) else None, reason=reason))
            continue
        kept = valid.get(sat.NORAD_CAT_ID)
        if kept is None or sat.EPOCH > kept.EPOCH:
            valid[sat.NORAD_CAT_ID] = sat
    return valid, skipped


def import_group(db: Session, group: str, fetch: Fetcher, now: datetime | None = None) -> ImportResult:
    # One import at a time: two overlapping downloads would hit CelesTrak twice and could insert the same satellites twice.
    if not IMPORT_LOCK.acquire(blocking=False):
        raise Conflict("import_in_progress", "Another import is still running. Wait for it to finish, then try again.")
    try:
        return _import_group(db, group, fetch, now or datetime.now(timezone.utc))
    finally:
        IMPORT_LOCK.release()


def _import_group(db: Session, group: str, fetch: Fetcher, now: datetime) -> ImportResult:
    _check_interval(db, group, now)
    records = fetch(group)  # a failed download raises before anything is written
    valid, skipped = _validate(records)

    # One query for what we have, then one bulk INSERT and one bulk UPDATE instead of a query per satellite.
    stored_epochs = dict(db.execute(select(SatelliteModel.NORAD_CAT_ID, SatelliteModel.EPOCH)).all())
    new_rows = [sat.model_dump() for norad_id, sat in valid.items() if norad_id not in stored_epochs]
    newer_rows = [sat.model_dump() for norad_id, sat in valid.items() if norad_id in stored_epochs and sat.EPOCH > stored_epochs[norad_id]]
    if new_rows:
        db.execute(insert(SatelliteModel), new_rows)
    if newer_rows:
        db.execute(update(SatelliteModel), newer_rows)

    result = ImportResult(
        group=group,
        fetched_at=now,
        received=len(records),
        added=len(new_rows),
        updated=len(newer_rows),
        unchanged=len(valid) - len(new_rows) - len(newer_rows),
        skipped=len(skipped),
        skipped_examples=skipped[:MAX_SKIPPED_EXAMPLES],
    )
    log = db.get(CatalogImportModel, group) or CatalogImportModel(group_name=group)
    for field in ("fetched_at", "received", "added", "updated", "unchanged", "skipped"):
        setattr(log, field, getattr(result, field))
    db.add(log)
    db.commit()  # satellites and the import log are saved together or not at all
    return result
