# SatPass API

FastAPI backend for SatPass: it predicts when satellites (ISS, Hubble, Chinese space station, …) pass over an observer, using real CelesTrak orbital elements and the SGP4 orbit model.

Data is kept in memory. Every restart reloads the seed: the 20 satellites in `../src/data/sample-gp.json` and one observer, **Almaty (id 1)**, watching the ISS.

## Run

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs (Swagger UI). Run the automated tests with `pytest`.

## Structure

```
app/
├─ main.py              app, routers, DomainError → JSON handler
├─ schemas.py           Pydantic request/response models
├─ errors.py            NotFound (404), Conflict (409), RuleViolation (422)
├─ store.py             in-memory dicts + seed data
├─ routers/             HTTP only: parameters, status codes, docs
│  ├─ satellites.py
│  └─ observers.py
└─ services/            business logic, no FastAPI imports
   ├─ orbit.py          SGP4, look angles, ground point, pass search (pure math)
   ├─ satellites.py     catalog rules
   └─ observers.py      observers, watchlist, pass prediction
tests/                  pytest: orbit math + every endpoint
```

## Workflows and business rules

| Workflow | Endpoints | Rules |
|---|---|---|
| **1. Satellite catalog**: add, search, refresh and remove orbital element sets | `GET/POST /satellites`, `GET/PATCH/DELETE /satellites/{norad_id}`, `GET /satellites/{norad_id}/position` | NORAD ID is unique (409). Elements must describe a real orbit, e.g. not a perigee inside Earth (422). EPOCH can't be in the future (422). Changing elements requires a new EPOCH (422) that is later than the current one (409). Deleting a satellite removes it from every watchlist. Positions are refused when the elements are more than 30 days from the requested time. |
| **2. Observers & watchlist**: save locations and the satellites each one follows | `GET/POST /observers`, `GET/PATCH/DELETE /observers/{id}`, `GET/POST /observers/{id}/watchlist`, `DELETE /observers/{id}/watchlist/{norad_id}` | Latitude/longitude ranges (422). Names are unique, ignoring case (409). A satellite must exist to be watched (404), can't be watched twice (409), and a watchlist holds at most 10 (409). |
| **3. Pass prediction**: when will my satellites fly over me? | `GET /observers/{id}/passes?hours=&min_elevation=&start=` | Watchlist must not be empty (409). Window 1–72 h. Passes peaking below the minimum height (default: the observer's setting) are dropped. Elements older than 3 days give a warning, older than 30 days are skipped with a warning. Result is sorted by rise time across all watched satellites. |

Errors from business rules look like `{"detail": "Satellite 25544 is already in the catalog", "code": "satellite_exists"}`. Pydantic validation errors use FastAPI's standard 422 format.

## Swagger test checklist

Restart the server first so you start from the seed data. Each row is a request in `/docs` → "Try it out".

| # | Request | Expected |
|---|---|---|
| 1 | `GET /satellites?search=iss` | 200, ISS (NAUKA) and ISS (ZARYA) |
| 2 | `GET /satellites/1` | 404 `satellite_not_found` |
| 3 | `POST /satellites` with the example body | 409 `satellite_exists` (the ISS is seeded) |
| 4 | Same body with `"NORAD_CAT_ID": 99999` | 201 |
| 5 | Same with `"ECCENTRICITY": 0.9` and a new ID | 422 `invalid_orbit` |
| 6 | Same with `"INCLINATION": 200` | 422 validation error |
| 7 | `PATCH /satellites/25544` `{"MEAN_ANOMALY": 10}` | 422 `epoch_required` |
| 8 | `PATCH /satellites/25544` `{"EPOCH": "2026-11-01T00:00:00", "MEAN_ANOMALY": 10}` | 409 `outdated_elements` |
| 9 | `GET /satellites/25544/position` | 200, altitude ≈ 400–440 km |
| 10 | `POST /observers` with the example body | 201, id 2 |
| 11 | `POST /observers` `{"name": "almaty", "latitude": 0, "longitude": 0}` | 409 `observer_exists` |
| 12 | `POST /observers` `{"name": "X", "latitude": 95, "longitude": 0}` | 422 |
| 13 | `PATCH /observers/2` `{"min_elevation_deg": 20}` | 200 |
| 14 | `POST /observers/1/watchlist` `{"norad_id": 48274}` | 201; again → 409 `already_watched` |
| 15 | `GET /observers/1/passes?start=2026-11-05T00:00:00Z&hours=48` | 200, ISS and CSS passes sorted by time |
| 16 | `GET /observers/1/passes?hours=100` | 422 |
| 17 | `GET /observers/2/passes` | 409 `empty_watchlist` |
| 18 | `DELETE /satellites/48274`, then `GET /observers/1` | 204; watchlist no longer has 48274 |
| 19 | `DELETE /observers/1/watchlist/48274` | 404 `not_watched` |
| 20 | `DELETE /observers/2`, then `GET /observers/2` | 204, then 404 |

The first ISS pass in row 15 rises at 15:59:26 UTC in the SW and peaks at 61.5°. This matches satellite.js on the same data.
