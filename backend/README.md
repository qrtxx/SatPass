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
| `JWT_SECRET` | signing login tokens (required, at least 32 characters) | output of `python -c "import secrets; print(secrets.token_hex(32))"` |
| `JWT_EXPIRE_MINUTES` | how long a login token is valid (default 60) | `60` |

They are read from the environment, or from `backend/.env` (git-ignored). `.env.example` is the template.

## Database

```
users 1 ──< observers 1 ──< watchlist_entries >── 1 satellites
```

| Table | Columns | Constraints |
|---|---|---|
| `users` | `id` (serial PK), `username`, `email`, `password_hash` (Argon2id, never the password), `role` (`user`/`admin`), `created_at` | Unique indexes on `lower(username)` and `lower(email)`; CHECK `role IN ('user','admin')` |
| `satellites` | `norad_cat_id` (PK, the NORAD catalog number), `object_name`, `epoch` (timestamptz), 9 orbital elements (double precision) | CHECK ranges for mean motion, eccentricity, inclination and the angles |
| `observers` | `id` (serial PK), `owner_id` (FK → `users`), `name`, `latitude`, `longitude`, `elevation_m`, `min_elevation_deg`, `created_at` | CHECK coordinate ranges, non-blank name; unique index on (`owner_id`, `lower(name)`); FK `ON DELETE CASCADE` |
| `watchlist_entries` | `observer_id` (FK), `norad_id` (FK), `added_at` | PK (`observer_id`, `norad_id`) so a satellite is watched once per observer; both FKs `ON DELETE CASCADE` |
| `catalog_imports` | `group_name` (PK), `fetched_at`, `received`, `added`, `updated`, `unchanged`, `skipped` | One row per CelesTrak group: the last successful import, used for the 2-hour limit |

Relationships: one user owns many observers (locations). One observer has many watchlist entries, and one satellite appears in many watchlist entries. Together they form a many-to-many between observers and satellites. Deleting a user deletes their observers, deleting an observer deletes its watchlist, and deleting a satellite removes it from every watchlist.

Migrations are in `alembic/versions/`: 0001 creates the tables, 0002 loads the seed data, 0003 adds `catalog_imports`, 0004 adds `users` and an `admin` with an unusable password, and 0005 gives every observer an owner (existing ones go to the admin).

The API checks every rule first and returns a readable error. The database constraints are a second line of defence; if one fires anyway, the API answers 409 `integrity_error` instead of crashing.

## Structure

```
app/
├─ main.py              app, routers, error → JSON handlers
├─ db.py                engine, session per request (DATABASE_URL)
├─ models.py            SQLAlchemy tables and relationships
├─ schemas.py           Pydantic request/response models
├─ errors.py            Unauthorized (401), Forbidden (403), NotFound (404), Conflict (409), RuleViolation (422), …
├─ security.py          password hashing (Argon2id), JWT access tokens
├─ dependencies.py      CurrentUser and require_admin (who is making the request)
├─ cli.py               python -m app.cli set-password <username>
├─ routers/             HTTP only: parameters, status codes, docs
│  ├─ auth.py
│  ├─ satellites.py
│  └─ observers.py
└─ services/            business logic, no FastAPI imports
   ├─ orbit.py          SGP4, look angles, ground point, pass search (pure math)
   ├─ satellites.py     catalog rules
   ├─ celestrak.py      downloads a group of orbital elements from CelesTrak
   ├─ catalog_import.py adds/refreshes the catalog from a download (2-hour limit)
   ├─ auth.py           registration, login, set password
   └─ observers.py      observers, watchlist, pass prediction
alembic/versions/       migrations: schema, then seed data
tests/                  pytest: orbit math, every endpoint, database constraints, security, permissions
```

## Authentication and permissions

- **Register:** `POST /auth/register` `{"username", "email", "password"}` → 201.
  - Username: 3–32 letters, digits, `.`, `_` or `-`. Password: 8–128 characters. The email isn't format-checked.
  - Usernames and emails are unique, ignoring case: 409 `username_taken` / `email_taken`.
  - Registration can't choose a role.
- **Log in:** `POST /auth/login` `{"login": "<username or email>", "password"}` → `{"access_token", "token_type": "bearer", "expires_in"}`. Wrong username or password: 401 `invalid_credentials`, with the same answer for both.
- **Send the token** as `Authorization: Bearer <access_token>`. `GET /auth/me` returns the logged-in user.
- **Passwords** are stored as Argon2id hashes. Tokens are JWTs (HS256) that expire after `JWT_EXPIRE_MINUTES`. The user and their role are read from the database on every request.
- **The first admin** comes from migration 0004, with no usable password. Set one with `python -m app.cli set-password admin`.

| Endpoint | Anonymous | User | Admin |
|---|---|---|---|
| `POST /auth/register`, `POST /auth/login` | ✅ | ✅ | ✅ |
| `GET /auth/me` | 401 | ✅ | ✅ |
| `GET /satellites`, `/satellites/{id}`, `/satellites/{id}/position` | ✅ | ✅ | ✅ |
| `POST /satellites`, `PATCH`/`DELETE /satellites/{id}`, `POST /satellites/import` | 401 | 403 `admin_only` | ✅ |
| `GET /observers` | 401 | own only | all |
| `POST /observers` | 401 | ✅ (owner = you) | ✅ (owner = you) |
| `GET`/`PATCH`/`DELETE /observers/{id}`, `…/watchlist`, `…/passes` (also with `norad_id`) | 401 | own ✅, others 403 `not_owner` | ✅ any |

**401 codes:**
- `not_authenticated`: no token sent;
- `invalid_token`: the token is bad, or its user is gone;
- `token_expired`;
- `invalid_credentials`.

Every 401 carries `WWW-Authenticate: Bearer`.

**In Swagger:**
1. Call `POST /auth/login` and copy `access_token`.
2. Click **Authorize** (top right), paste the token and confirm.
3. Every request now carries it.

## Workflows and business rules

| Workflow | Endpoints | Rules |
|---|---|---|
| **1. Satellite catalog**: add, search, refresh and remove orbital element sets | `GET/POST /satellites`, `GET/PATCH/DELETE /satellites/{norad_id}`, `GET /satellites/{norad_id}/position` | NORAD ID is unique (409). Elements must describe a real orbit, e.g. not a perigee inside Earth (422). EPOCH can't be in the future (422). Changing elements requires a new EPOCH (422) that is later than the current one (409). Deleting a satellite removes it from every watchlist. Positions are refused when the elements are more than 30 days from the requested time. |
| **1b. Live data**: refresh the catalog from CelesTrak | `POST /satellites/import` `{"group": "active"}` | Groups: `active`, `stations`, `visual`, `weather`, `science`, `gps-ops`, `galileo`, `starlink` (others 422). Each record passes the same checks as `POST /satellites`; invalid ones are skipped and counted, with up to 10 examples. New satellites are added; existing ones are updated only if CelesTrak's EPOCH is newer. Satellites missing from the download are kept. Everything is saved in one transaction. A group can be imported once every 2 hours, CelesTrak's rule (429 with `Retry-After`). Only one import runs at a time (409 `import_in_progress`). CelesTrak down or answering with text instead of data: 502. `received` counts duplicates too, so the numbers can add up to less than it. |
| **2. Observers & watchlist**: save locations and the satellites each one follows | `GET/POST /observers`, `GET/PATCH/DELETE /observers/{id}`, `GET/POST /observers/{id}/watchlist`, `DELETE /observers/{id}/watchlist/{norad_id}` | Latitude/longitude ranges (422). Every location belongs to the user who created it. Names are unique per user, ignoring case (409). A satellite must exist to be watched (404), can't be watched twice (409), and a watchlist holds at most 10 (409). |
| **3. Pass prediction**: when will my satellites fly over me? | `GET /observers/{id}/passes?hours=&min_elevation=&start=&norad_id=` | With `norad_id` (repeat it, up to 20, e.g. `norad_id=25544&norad_id=48274`) predicts for exactly those satellites, watched or not; an unknown ID is 404, more than 20 is 422. Without it, the watchlist is used and must not be empty (409). Window 1–72 h. Passes peaking below the minimum height (default: the observer's setting) are dropped. Elements older than 3 days give a warning, older than 30 days are skipped with a warning. Result is sorted by rise time across all watched satellites. |

Errors from business rules look like `{"detail": "Satellite 25544 is already in the catalog", "code": "satellite_exists"}`. Pydantic validation errors use FastAPI's standard 422 format.

## Swagger test checklist

Reset to the seed data first (`alembic downgrade base`, then `alembic upgrade head`, then `python -m app.cli set-password admin`). Each row is a request in `/docs` → "Try it out". **Rows 1–28 run as the admin:** log in as `admin` and press **Authorize** (see above); Almaty (id 1) belongs to the admin.

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
| 29 | Log out of Swagger (**Authorize** → Logout), then `GET /observers` | 401 `not_authenticated` |
| 30 | `GET /satellites/25544` without a token | 200 (the catalog is public) |
| 31 | `POST /auth/register` `{"username": "alice", "email": "alice@example.com", "password": "password123"}` | 201, with no password in the response; again → 409 `username_taken` |
| 32 | `POST /auth/login` `{"login": "alice", "password": "wrong-password"}` | 401 `invalid_credentials` |
| 33 | Log in as alice, **Authorize** with her token, `GET /observers` | 200, `[]`: she sees only her own |
| 34 | As alice: `GET /observers/1` | 403 `not_owner` (Almaty is the admin's) |
| 35 | As alice: `DELETE /satellites/48274` | 403 `admin_only` |
| 36 | As alice: `POST /observers` with `{"name": "Almaty", "latitude": 43.2, "longitude": 76.9}` | 201: names are unique per user, so she can also have an "Almaty" |

The first ISS pass in row 15 rises at 15:59:26 UTC in the SW and peaks at 61.5°. This matches satellite.js on the same data.
