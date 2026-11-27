import zipfile

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import PlaceModel
from app.services.places import load_places, parse_places, parse_regions

client = TestClient(app)

# Real GeoNames format: 19 tab-separated columns (geonameid, name, asciiname, alternatenames, latitude, longitude,
# feature class, feature code, country code, cc2, admin1..4, population, elevation, dem, timezone, modification date).
SAMPLE = "\n".join(
    "\t".join(row)
    for row in [
        ["1526384", "Almaty", "Almaty", "", "43.25667", "76.92861", "P", "PPLA", "KZ", "", "02", "", "", "", "2000900", "", "780", "Asia/Almaty", "2024-01-01"],
        ["1526273", "Astana", "Astana", "", "51.1801", "71.44598", "P", "PPLC", "KZ", "", "05", "", "", "", "1078362", "347", "349", "Asia/Almaty", "2024-01-01"],
        ["9999001", "Tiny Aul", "Tiny Aul", "", "43.3", "76.9", "P", "PPL", "KZ", "", "02", "", "", "", "0", "", "-9999", "Asia/Almaty", "2024-01-01"],
        ["9999002", "Ile", "Ile", "", "44.0", "77.0", "H", "STM", "KZ", "", "02", "", "", "", "0", "", "500", "Asia/Almaty", "2024-01-01"],  # a river
    ]
)
REGIONS = "KZ.02\tAlmaty Qalasy\tAlmaty Qalasy\t1537162\nKZ.05\tAstana Qalasy\tAstana Qalasy\t1538317"


@pytest.fixture
def places(db):
    rows = [
        PlaceModel(id=1, name="Astana", ascii_name="Astana", country_code="KZ", region="Astana Qalasy", latitude=51.18, longitude=71.446, elevation_m=347, population=1078362),
        PlaceModel(id=2, name="Astana", ascii_name="Astana", country_code="KZ", region="Pavlodar", latitude=52.0, longitude=76.0, elevation_m=120, population=0),
        PlaceModel(id=3, name="Astrakhan'", ascii_name="Astrakhan'", country_code="RU", region="Astrakhan", latitude=46.35, longitude=48.04, elevation_m=-23, population=502533),
        PlaceModel(id=4, name="Almaty", ascii_name="Almaty", country_code="KZ", region="Almaty Qalasy", latitude=43.2567, longitude=76.9286, elevation_m=780, population=2000900),
        PlaceModel(id=5, name="Ақтау", ascii_name="Aktau", country_code="KZ", region="Mangghystau", latitude=43.65, longitude=51.17, elevation_m=10, population=147443),
    ]
    db.add_all(rows)
    db.flush()


def test_parse_keeps_populated_places_with_region_and_elevation():
    rows = list(parse_places(SAMPLE.splitlines(), parse_regions(REGIONS.splitlines())))
    assert [r[1] for r in rows] == ["Almaty", "Astana", "Tiny Aul"]  # the river (class H) is skipped
    almaty, astana, aul = rows
    assert almaty == (1526384, "Almaty", "Almaty", "KZ", "Almaty Qalasy", 43.25667, 76.92861, 780, 2000900)  # elevation from dem
    assert astana[7] == 347  # the recorded elevation wins over dem
    assert aul[7] is None  # dem -9999 means "no data"


def test_load_places_replaces_the_table(db, tmp_path):
    db.add(PlaceModel(id=1, name="Old", ascii_name="Old", country_code="XX", latitude=0, longitude=0, population=0))
    db.flush()
    places_zip, regions_txt = tmp_path / "allCountries.zip", tmp_path / "admin1CodesASCII.txt"
    with zipfile.ZipFile(places_zip, "w") as z:
        z.writestr("allCountries.txt", SAMPLE + "\n")
    regions_txt.write_text(REGIONS, encoding="utf-8")
    assert load_places(db, [places_zip], regions_txt) == 3
    db.expire_all()
    assert sorted(p.name for p in db.query(PlaceModel)) == ["Almaty", "Astana", "Tiny Aul"]


def test_load_places_from_the_small_files_skips_duplicates(db, tmp_path):
    # KZ.zip and cities1000.zip overlap: Kazakh towns over 1,000 people are in both.
    kz, cities = tmp_path / "KZ.zip", tmp_path / "cities1000.zip"
    with zipfile.ZipFile(kz, "w") as z:
        z.writestr("KZ.txt", SAMPLE + "\n")
        z.writestr("readme.txt", "not data")
    almaty_row = SAMPLE.splitlines()[0]
    paris_row = almaty_row.replace("1526384\tAlmaty\tAlmaty", "2988507\tParis\tParis").replace("\tKZ\t", "\tFR\t")
    with zipfile.ZipFile(cities, "w") as z:
        z.writestr("cities1000.txt", almaty_row + "\n" + paris_row + "\n")
    regions_txt = tmp_path / "admin1CodesASCII.txt"
    regions_txt.write_text(REGIONS, encoding="utf-8")
    assert load_places(db, [kz, cities], regions_txt) == 4  # Almaty once, plus Astana, Tiny Aul and Paris
    db.expire_all()
    assert sorted(p.name for p in db.query(PlaceModel)) == ["Almaty", "Astana", "Paris", "Tiny Aul"]


def test_search_ranks_bigger_places_first(places):
    names = [(p["name"], p["region"]) for p in client.get("/places", params={"search": "ast"}).json()]
    assert names == [("Astana", "Astana Qalasy"), ("Astrakhan'", "Astrakhan"), ("Astana", "Pavlodar")]
    exact = client.get("/places", params={"search": "Astana"}).json()
    assert [p["region"] for p in exact] == ["Astana Qalasy", "Pavlodar"]  # both exact; the bigger first


def test_search_ignores_case_and_matches_ascii_or_local_name(places):
    assert client.get("/places", params={"search": "ALMATY"}).json()[0]["elevation_m"] == 780
    assert client.get("/places", params={"search": "Ақт"}).json()[0]["ascii_name"] == "Aktau"
    assert client.get("/places", params={"search": "aktau"}).json()[0]["name"] == "Ақтау"


@pytest.mark.parametrize("search", ["a%", "__", "%%"])
def test_search_wildcards_are_literal(places, search):
    assert client.get("/places", params={"search": search}).json() == []


def test_search_needs_two_characters_and_caps_the_limit(places):
    assert client.get("/places", params={"search": "a"}).status_code == 422
    assert client.get("/places", params={"search": "as", "limit": 50}).status_code == 422
    assert len(client.get("/places", params={"search": "as", "limit": 2}).json()) == 2


def test_nearest_place_gives_distance_and_elevation(places):
    r = client.get("/places/nearest", params={"latitude": 43.3, "longitude": 76.95})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Almaty" and body["elevation_m"] == 780
    assert 4 < body["distance_km"] < 6


def test_no_place_nearby(places):
    r = client.get("/places/nearest", params={"latitude": -40.0, "longitude": -30.0})  # the South Atlantic
    assert r.status_code == 404 and r.json()["code"] == "no_place_nearby"


@pytest.mark.parametrize(
    "present, full, expected",
    [
        ([], False, ["KZ.zip", "cities1000.zip"]),  # nothing downloaded yet: the small set
        (["KZ.zip"], False, ["KZ.zip"]),  # use what's there
        (["KZ.zip", "allCountries.zip"], False, ["allCountries.zip"]),  # the full file wins
        ([], True, ["allCountries.zip"]),  # --full
    ],
)
def test_load_places_chooses_its_files(tmp_path, monkeypatch, present, full, expected):
    from app import cli

    monkeypatch.setattr(cli, "DATA_DIR", tmp_path)
    for name in present:
        (tmp_path / name).touch()
    assert cli.choose_files(full) == expected


@pytest.mark.parametrize("search", ["  ", " a ", "\t\t"])
def test_blank_or_padded_short_search_is_rejected(places, search):
    # Otherwise "  " becomes the pattern "%" and sorts the whole table.
    assert client.get("/places", params={"search": search}).status_code == 422


def test_tiny_exact_matches_do_not_bury_big_places(db):
    # On the real data, "ka" matched hundreds of villages called exactly "Ka" (population unknown) before Kabul.
    db.add_all([
        PlaceModel(id=11, name="Ka", ascii_name="Ka", country_code="NG", latitude=9.0, longitude=8.0, population=0),
        PlaceModel(id=12, name="Kabul", ascii_name="Kabul", country_code="AF", latitude=34.5, longitude=69.2, population=4434550),
        PlaceModel(id=13, name="Kaba", ascii_name="Kaba", country_code="HU", latitude=47.4, longitude=21.3, population=0),
    ])
    db.flush()
    names = [p["name"] for p in client.get("/places", params={"search": "ka"}).json()]
    assert names == ["Kabul", "Ka", "Kaba"]  # biggest first; among unknown sizes the exact name wins
