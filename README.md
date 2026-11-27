# SatPass — Satellite Pass Predictor

SatPass predicts when satellites such as the ISS, Hubble and the Chinese space station fly over a location. It uses real orbital data from CelesTrak and the SGP4 orbit model.

The backend is a REST API built with **FastAPI**, **PostgreSQL**, **SQLAlchemy** and **Alembic**. It is in [`backend/`](backend/). See [`backend/README.md`](backend/README.md) for the endpoints, business rules, database schema and a Swagger test checklist.

A **React** (Vite, react-router) UI in [`src/`](src/) uses that API. Every page has its own URL:
- **`/satellites`:** browse and search the whole catalog page by page, tick up to 20 satellites and press **Predict passes**, and update orbit data from CelesTrak. The search and page are in the URL (`/satellites?q=starlink&page=3`).
- **Satellite details:** click a satellite's name on any page to see its orbit, where it is now (refreshed every 5 seconds), its next passes over your location, and Watch and Delete buttons. The details have their own link, for example `?sat=25544`.
- **`/passes`:** predict for the ticked satellites or for the location's watchlist, over a chosen time window.
- **`/locations`:** your locations. Add one by searching a town or village, by using your current location, or by typing coordinates. Elevation is filled in from the place, or estimated from the nearest one.
- **`/login`, `/register`:** accounts. Passes and locations need one; browsing satellites doesn't.
- **`/admin`** (admins only): user and catalog counts, the last orbit-data imports, and every user. Each user has a page (`/admin/users/:id`) with their profile, role, locations, and Delete/Restore buttons. Changing a role asks you to re-type your own password; deleting an account asks twice, with the buttons swapped on the second dialog. Deleting is a soft delete: the account can't log in but its data stays, and **Show deleted accounts** on `/admin` lists it so it can be restored.
- **Coming soon:** `/` (Tonight's visible passes), `/globe` and `/account`. Their pages are already there as placeholders.

Errors from the API, such as validation errors or a duplicate name, are shown on the page.

## How to run (Windows)

### 1. Install the prerequisites

- **Python 3.12 or newer**: https://www.python.org/downloads/
- **PostgreSQL 14 or newer**: either the installer from https://www.postgresql.org/download/windows/ or, in PowerShell:
  ```powershell
  winget install PostgreSQL.PostgreSQL.17
  ```
  Write down the password you choose for the `postgres` user.
- **Node.js 20 or newer** (for the UI): https://nodejs.org/
- **Git**

### 2. Get the code

```powershell
git clone https://github.com/qrtxx/SatPass.git
cd SatPass\backend
```

### 3. Create the database

Open `psql` as the `postgres` user. It is not on the PATH on Windows, so use the full path (change `17` to your version):

```powershell
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -h localhost
```

Enter the `postgres` password, then paste these lines and pick your own password:

```sql
CREATE ROLE satpass LOGIN PASSWORD 'choose-a-password';
CREATE DATABASE satpass OWNER satpass;
CREATE DATABASE satpass_test OWNER satpass;
\q
```

`satpass` is the app's database. `satpass_test` is used only by the automated tests, which wipe it on every run.

### 4. Install the Python packages

Still in `SatPass\backend`:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

### 5. Configure the connection

```powershell
copy .env.example .env
notepad .env
```

Replace `CHANGE_ME` with the password from step 3, on both database lines. Then replace the `JWT_SECRET` value with a long random secret; it signs the login tokens. Generate one with:

```powershell
.venv\Scripts\python -c "import secrets; print(secrets.token_hex(32))"
```

Save the file.

### 6. Create the tables and load the sample data

```powershell
.venv\Scripts\python -m alembic upgrade head
```

This runs the migrations in `backend/alembic/versions/`. They create the tables and add 20 satellites, an **admin** account, and one location, Almaty, owned by the admin and watching the ISS.

Then give the admin a password (it can't log in until you do). You type it twice; nothing is shown:

```powershell
.venv\Scripts\python -m app.cli set-password admin
```

Then load the towns and villages used by the place search ("Find a town or village" when adding a location):

```powershell
.venv\Scripts\python -m app.cli load-places
```

The data comes from [GeoNames](https://www.geonames.org/) (CC BY 4.0) and is stored in `backend\data\geonames\` (not in git). There are two sizes:

| | Files | Download | Contains |
|---|---|---|---|
| **Default** | `KZ.zip` + `cities1000.zip` | ~14 MB | Every town and village in Kazakhstan, plus towns of 1,000+ people worldwide. Enough to try the project. |
| **Full** (`load-places --full`) | `allCountries.zip` | ~400 MB | Every populated place in the world. Loading takes a few minutes. |

`load-places` uses `allCountries.zip` if it's already in `backend\data\geonames\`. Otherwise it uses whichever of the two small files are there, and downloads them if neither is. Running it again replaces the places with the current files. Without it, the place search finds nothing, but you can still type coordinates.

### 7. Start the server

```powershell
.venv\Scripts\python -m uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000/docs** to try every endpoint in Swagger UI. Stop the server with `Ctrl+C`. Your data stays in PostgreSQL, so it is still there the next time you start the server.

### 8. Start the UI

Keep the server from step 7 running. In a second terminal, from the `SatPass` folder (not `backend`):

```powershell
npm install
npm run dev
```

Open **http://localhost:5173**. Browsing satellites works without an account. To predict passes and save locations, press **Sign up** (or **Log in** as `admin`). The UI sends its requests to `/api/...`, and Vite forwards them to the API on port 8000, so no CORS setup is needed. If the API runs on another port, start the UI with `$env:API_URL="http://127.0.0.1:8001"; npm run dev`.

### 9. Load live orbit data

The sample data is a snapshot from 4 Nov 2026, so predictions from "now" are inaccurate or skipped. To get current data, log in as **admin**, open **Satellites**, choose a group and press **Update orbit data** (only admins see it):

- `stations`: the ISS, the Chinese station and a few others. Takes a few seconds.
- `active`: every working satellite (about 17,000). The download takes about a minute.

Each group can be updated once every 2 hours; CelesTrak blocks clients that download more often. Without live data, set the Passes tab's start to around 5 Nov 2026 to see the sample ISS passes.

### Run the tests

```powershell
.venv\Scripts\python -m pytest
```

### Reset to the sample data

```powershell
.venv\Scripts\python -m alembic downgrade base
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m app.cli set-password admin
```

This deletes everything, including all accounts and their locations, and the admin's password has to be set again.

### macOS / Linux

The steps are the same, with these differences:
- Run `.venv/bin/python` instead of `.venv\Scripts\python`.
- Use `cp .env.example .env` instead of `copy`.
- Open psql with `psql -U postgres -h localhost`, or `sudo -u postgres psql` on Linux.

## Troubleshooting

| Message | Fix |
|---|---|
| `uvicorn` / `alembic` / `pytest` is not recognized | Run it through the virtual environment, as above: `.venv\Scripts\python -m uvicorn ...` |
| `JWT_SECRET must be set to at least 32 characters` | Add a `JWT_SECRET` line to `backend\.env` (step 5). |
| `Wrong username/email or password` for `admin` | The admin has no password yet: run `.venv\Scripts\python -m app.cli set-password admin` (step 6). |
| The UI suddenly shows the login page | Your login expired (after 60 minutes, `JWT_EXPIRE_MINUTES`); log in again. |
| `DATABASE_URL is not set` | `backend\.env` is missing; do step 5. Run commands from inside `backend`. |
| `password authentication failed for user "satpass"` | The password in `.env` doesn't match the one from step 3. |
| `connection refused` / `Connection timed out` | PostgreSQL isn't running. In PowerShell as admin: `Start-Service postgresql-x64-17` |
| `relation "satellites" does not exist` | The tables weren't created; do step 6. |
| UI shows `Request failed (500). Is the backend running on port 8000?` | The API isn't running; do step 7 in another terminal. |
| `Address already in use` / port 8000 busy | Start on another port: add `--port 8001` and open http://127.0.0.1:8001/docs |
