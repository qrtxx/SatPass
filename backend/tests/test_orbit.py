import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.schemas import Satellite
from app.services import orbit

SNAPSHOT = Path(__file__).resolve().parents[2] / "src" / "data" / "sample-gp.json"

HOUR = 3600


def bump(center, height):
    """Triangle-shaped fake pass: `height`° at `center` s, 0° at center ± height*10 s."""
    return lambda t: height - abs(t - center) / 10


@pytest.mark.parametrize("deg, expected", [(0, "N"), (45, "NE"), (56.25, "ENE"), (90, "E"), (227, "SW"), (350, "N"), (359.9, "N")])
def test_azimuth_to_compass(deg, expected):
    assert orbit.azimuth_to_compass(deg) == expected


def test_refine_crossing_is_accurate_to_one_second():
    assert abs(orbit.refine_crossing(bump(600, 30), 300, 360) - 300) <= 1
    assert abs(orbit.refine_crossing(bump(600, 30), 840, 900) - 900) <= 1


def test_one_pass():
    [p] = orbit.find_passes(bump(600, 30), 0, HOUR)
    assert abs(p["rise"] - 300) <= 1 and abs(p["set"] - 900) <= 1
    assert abs(p["peak"] - 600) <= 10 and p["peak_elevation"] > 29


def test_two_passes():
    passes = orbit.find_passes(lambda t: max(bump(600, 30)(t), bump(2400, 20)(t)), 0, HOUR)
    assert len(passes) == 2 and abs(passes[1]["rise"] - 2200) <= 1


def test_pass_already_in_progress():
    [p] = orbit.find_passes(bump(0, 30), 0, HOUR)
    assert p["rise"] == 0 and abs(p["set"] - 300) <= 1


def test_no_passes_and_min_elevation():
    assert orbit.find_passes(lambda t: -10, 0, HOUR) == []
    assert orbit.find_passes(bump(600, 5), 0, HOUR) == []
    assert len(orbit.find_passes(bump(600, 5), 0, HOUR, min_elevation=0)) == 1


def test_iss_over_almaty_matches_satellite_js():
    # Reference values from satellite.js 7.1 on the same snapshot.
    iss = next(s for s in json.loads(SNAPSHOT.read_text()) if s["NORAD_CAT_ID"] == 25544)
    rec = orbit.build_satrec(Satellite.model_validate(iss))
    look = orbit.observer_view(rec, 43.2389, 76.8897, 0.8)
    t0 = datetime(2026, 11, 5, tzinfo=timezone.utc).timestamp()
    passes = orbit.find_passes(lambda t: look(t)[1], t0, t0 + 24 * HOUR)
    assert len(passes) == 5
    first = passes[0]
    assert abs(first["rise"] - datetime(2026, 11, 5, 15, 59, 25, 781000, tzinfo=timezone.utc).timestamp()) < 0.5
    assert first["peak_elevation"] == pytest.approx(61.47, abs=0.01)
    assert look(first["rise"])[0] == pytest.approx(227.38, abs=0.01)
    lat, _, alt = orbit.subpoint(rec, t0)
    assert 370 < alt < 460 and abs(lat) <= 51.7
