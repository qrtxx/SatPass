"""Places from GeoNames: load the dataset, search it by name, find the nearest place to a point."""

import io
import math
import zipfile
from collections.abc import Iterable, Iterator
from pathlib import Path

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.errors import NotFound
from app.models import PlaceModel

NEARBY_KM = 50
EARTH_RADIUS_KM = 6371.0
COLUMNS = "id, name, ascii_name, country_code, region, latitude, longitude, elevation_m, population"


def parse_regions(lines: Iterable[str]) -> dict[str, str]:
    """admin1CodesASCII.txt: 'KZ.02<TAB>Almaty Qalasy<TAB>…' → {'KZ.02': 'Almaty Qalasy'}."""
    regions = {}
    for line in lines:
        code, name, *_ = line.rstrip("\n").split("\t") + [""]
        if code and name:
            regions[code] = name
    return regions


def parse_places(lines: Iterable[str], regions: dict[str, str]) -> Iterator[tuple]:
    """Rows of the GeoNames dump that are populated places (feature class P), ready for COPY."""
    for line in lines:
        f = line.rstrip("\n").split("\t")
        if len(f) < 19 or f[6] != "P":
            continue
        # The recorded elevation if there is one, else the terrain model's (-9999 = no data, e.g. over the sea).
        elevation = int(f[15]) if f[15] else (int(f[16]) if f[16] and f[16] != "-9999" else None)
        region = regions.get(f"{f[8]}.{f[10]}")
        yield (int(f[0]), f[1][:200], f[2][:200], f[8][:2], region, float(f[4]), float(f[5]), elevation, int(f[14] or 0))


def _rows(zip_path: Path, regions: dict[str, str]) -> Iterator[tuple]:
    with zipfile.ZipFile(zip_path) as archive:
        member = next(n for n in archive.namelist() if n.endswith(".txt") and n != "readme.txt")
        with archive.open(member) as raw:
            yield from parse_places(io.TextIOWrapper(raw, encoding="utf-8"), regions)


def load_places(db: Session, place_zips: list[Path], regions_txt: Path) -> int:
    """Replace the places table with the populated places of one or more GeoNames files (allCountries.zip, or
    KZ.zip + cities1000.zip). One transaction: a failed load keeps the old data."""
    regions = parse_regions(regions_txt.read_text(encoding="utf-8").splitlines())
    seen: set[int] = set()  # the small files overlap (Kazakh towns are in both); one file has no duplicates
    count = 0
    db.execute(text("TRUNCATE places"))
    # COPY streams millions of rows in minutes; individual INSERTs would take far longer.
    cursor = db.connection().connection.cursor()
    with cursor.copy(f"COPY places ({COLUMNS}) FROM STDIN") as copy:
        for zip_path in place_zips:
            for row in _rows(zip_path, regions):
                if len(place_zips) > 1:
                    if row[0] in seen:
                        continue
                    seen.add(row[0])
                copy.write_row(row)
                count += 1
    db.commit()
    return count


def search_places(db: Session, search: str, limit: int) -> list[PlaceModel]:
    """Names starting with the text, in the local or Latin spelling, ignoring case.
    Bigger places first; an exact name breaks ties, then alphabetical. (Exact-first buried Kabul under hundreds
    of villages called "Ka" on the full data: many villages have population 0 = unknown.)"""
    word = search.strip().lower()
    pattern = word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"  # the user's % and _ are literal
    name, ascii_name = func.lower(PlaceModel.name), func.lower(PlaceModel.ascii_name)
    query = (
        select(PlaceModel)
        .where(or_(ascii_name.like(pattern, escape="\\"), name.like(pattern, escape="\\")))
        .order_by(PlaceModel.population.desc(), or_(name == word, ascii_name == word).desc(), PlaceModel.ascii_name)
        .limit(limit)
    )
    return list(db.scalars(query))


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle (haversine) distance."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def nearest_place(db: Session, latitude: float, longitude: float) -> tuple[PlaceModel, float]:
    """The closest place within 50 km, e.g. to estimate the elevation of a typed or GPS location."""
    lat_band = NEARBY_KM / 111.0  # degrees of latitude
    lon_band = min(180.0, lat_band / max(math.cos(math.radians(latitude)), 0.01))
    # Pick the candidate with a cheap flat-earth distance in SQL, then measure it properly.
    flat = (PlaceModel.latitude - latitude) * (PlaceModel.latitude - latitude) + (
        (PlaceModel.longitude - longitude) * math.cos(math.radians(latitude))
    ) * ((PlaceModel.longitude - longitude) * math.cos(math.radians(latitude)))
    place = db.scalar(
        select(PlaceModel)
        .where(PlaceModel.latitude.between(latitude - lat_band, latitude + lat_band))
        .where(PlaceModel.longitude.between(longitude - lon_band, longitude + lon_band))
        .order_by(flat)
        .limit(1)
    )
    distance = place and _distance_km(latitude, longitude, place.latitude, place.longitude)
    if place is None or distance > NEARBY_KM:
        raise NotFound("no_place_nearby", f"No town or village within {NEARBY_KM} km")
    return place, distance
