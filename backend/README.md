# SatPass API

FastAPI backend for SatPass: it predicts when satellites (ISS, Hubble, Chinese space station, …) pass over an observer, using real CelesTrak orbital elements and the SGP4 orbit model.

Data is stored in PostgreSQL through SQLAlchemy, and the schema is built by Alembic migrations. The migrations also load seed data: the 20 satellites in `../src/data/sample-gp.json` (a snapshot from 4 Nov 2026) and one observer, **Almaty (id 1)**, watching the ISS.

To get **current** orbital data, call `POST /satellites/import` (or press **Update orbit data** in the UI's Satellites tab). It downloads a CelesTrak group, for example `active` (about 17,000 working satellites), and adds or refreshes them.

## Run

Step-by-step setup (PostgreSQL, `.env`, migrations, server, tests, troubleshooting) is in the [main README](../README.md#how-to-run-windows). In short, from `backend/` once PostgreSQL and `.env` are set up:

```powershell
.venv\Scripts\python -m alembic upgrade head               # create the tables and load the seed data
.venv\Scripts\python -m uvicorn app.main:app --reload       # then open http://127.0.0.1:8000/docs
.venv\Scripts\python -m pytest                              # tests use TEST_DATABASE_URL
```

## Configuration

| Variable | Used by | Example |
|---|---|---|
| `DATABASE_URL` | the app and Alembic | `postgresql+psycopg://satpass:secret@localhost:5432/satpass` |
| `TEST_DATABASE_URL` | pytest only | `postgresql+psycopg://satpass:secret@localhost:5432/satpass_test` |

They are read from the environment, or from `backend/.env` (git-ignored). `.env.example` is the template.

## Database

```
satellites 1 ──< watchlist_entries >── 1 observers
```

| Table | Columns | Constraints |
|---|---|---|
| `satellites` | `norad_cat_id` (PK, the NORAD catalog number), `object_name`, `epoch` (timestamptz), 9 orbital elements (double precision) | CHECK ranges for mean motion, eccentricity, inclination and the angles |
| `observers` | `id` (serial PK), `name`, `latitude`, `longitude`, `elevation_m`, `min_elevation_deg`, `created_at` | CHECK coordinate ranges, non-blank name; unique index on `lower(name)` |
| `watchlist_entries` | `observer_id` (FK), `norad_id` (FK), `added_at` | PK (`observer_id`, `norad_id`) so a satellite is watched once per observer; both FKs `ON DELETE CASCADE` |
| `catalog_imports` | `group_name` (PK), `fetched_at`, `received`, `added`, `updated`, `unchanged`, `skipped` | One row per CelesTrak group: the last successful import, used for the 2-hour limit |

Relationships: one observer has many watchlist entries, and one satellite appears in many watchlist entries. Together they form a many-to-many between observers and satellites. Deleting an observer deletes its watchlist; deleting a satellite removes it from every watchlist.

Migrations are in `alembic/versions/`: the first creates the tables, the second loads the seed data, the third adds `catalog_imports`.

The API checks every rule first and returns a readable error. The database constraints are a second line of defence; if one fires anyway, the API answers 409 `integrity_error` instead of crashing.

## Structure

```
app/
├─ main.py              app, routers, error → JSON handlers
├─ db.py                engine, session per request (DATABASE_URL)
├─ models.py            SQLAlchemy tables and relationships
├─ schemas.py           Pydantic request/response models
├─ errors.py            NotFound (404), Conflict (409), RuleViolation (422)
├─ routers/             HTTP only: parameters, status codes, docs
│  ├─ satellites.py
│  └─ observers.py
└─ services/            business logic, no FastAPI imports
   ├─ orbit.py          SGP4, look angles, ground point, pass search (pure math)
   ├─ satellites.py     catalog rules
   ├─ celestrak.py      downloads a group of orbital elements from CelesTrak
   ├─ catalog_import.py adds/refreshes the catalog from a download (2-hour limit)
   └─ observers.py      observers, watchlist, pass prediction
alembic/versions/       migrations: schema, then seed data
tests/                  pytest: orbit math, every endpoint, database constraints
```

## Workflows and business rules

| Workflow | Endpoints | Rules |
|---|---|---|
| **1. Satellite catalog**: add, search, refresh and remove orbital element sets | `GET/POST /satellites`, `GET/PATCH/DELETE /satellites/{norad_id}`, `GET /satellites/{norad_id}/position` | NORAD ID is unique (409). Elements must describe a real orbit, e.g. not a perigee inside Earth (422). EPOCH can't be in the future (422). Changing elements requires a new EPOCH (422) that is later than the current one (409). Deleting a satellite removes it from every watchlist. Positions are refused when the elements are more than 30 days from the requested time. |
| **1b. Live data**: refresh the catalog from CelesTrak | `POST /satellites/import` `{"group": "active"}` | Groups: `active`, `stations`, `visual`, `weather`, `science`, `gps-ops`, `galileo`, `starlink` (others 422). Each record passes the same checks as `POST /satellites`; invalid ones are skipped and counted, with up to 10 examples. New satellites are added; existing ones are updated only if CelesTrak's EPOCH is newer. Satellites missing from the download are kept. Everything is saved in one transaction. A group can be imported once every 2 hours, CelesTrak's rule (429 with `Retry-After`). Only one import runs at a time (409 `import_in_progress`). CelesTrak down or answering with text instead of data: 502. `received` counts duplicates too, so the numbers can add up to less than it. |
| **2. Observers & watchlist**: save locations and the satellites each one follows | `GET/POST /observers`, `GET/PATCH/DELETE /observers/{id}`, `GET/POST /observers/{id}/watchlist`, `DELETE /observers/{id}/watchlist/{norad_id}` | Latitude/longitude ranges (422). Names are unique, ignoring case (409). A satellite must exist to be watched (404), can't be watched twice (409), and a watchlist holds at most 10 (409). |
| **3. Pass prediction**: when will my satellites fly over me? | `GET /observers/{id}/passes?hours=&min_elevation=&start=&norad_id=` | With `norad_id` (repeat it, up to 20, e.g. `norad_id=25544&norad_id=48274`) predicts for exactly those satellites, watched or not; an unknown ID is 404, more than 20 is 422. Without it, the watchlist is used and must not be empty (409). Window 1–72 h. Passes peaking below the minimum height (default: the observer's setting) are dropped. Elements older than 3 days give a warning, older than 30 days are skipped with a warning. Result is sorted by rise time across all watched satellites. |

Errors from business rules look like `{"detail": "Satellite 25544 is already in the catalog", "code": "satellite_exists"}`. Pydantic validation errors use FastAPI's standard 422 format.

## Swagger test checklist

Reset to the seed data first (`alembic downgrade base`, then `alembic upgrade head`). Each row is a request in `/docs` → "Try it out".

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
| 21 | `POST /observers` with a new name, stop the server (Ctrl+C), start it again, `GET /observers` | The new observer is still there |
| 22 | `POST /satellites/import` `{"group": "stations"}` | 200; `updated` > 0 (the seeded stations get current epochs) |
| 23 | The same request again | 429 `import_too_soon`, with a `Retry-After` header |
| 24 | `POST /satellites/import` `{"group": "nosuchgroup"}` | 422 |
| 25 | `GET /observers/1/passes` (no `start`) after row 22 | 200, ISS passes from now, `warnings` empty |
| 26 | `GET /observers/1/passes?norad_id=48274` | 200, passes of the Chinese station, which Almaty doesn't watch |
| 27 | `GET /observers/1/passes` with `norad_id` given 21 times | 422 |
| 28 | `GET /satellites?limit=5` | 200, 5 satellites; the `X-Total-Count` response header holds the number of all matches |

The first ISS pass in row 15 rises at 15:59:26 UTC in the SW and peaks at 61.5°. This matches satellite.js on the same data.
