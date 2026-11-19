# SatPass — Satellite Pass Predictor

SatPass predicts when satellites such as the ISS, Hubble and the Chinese space station fly over a location. It uses real orbital data from CelesTrak and the SGP4 orbit model.

The backend is a REST API built with **FastAPI**, **PostgreSQL**, **SQLAlchemy** and **Alembic**. It is in [`backend/`](backend/). See [`backend/README.md`](backend/README.md) for the endpoints, business rules, database schema and a Swagger test checklist.

## How to run (Windows)

### 1. Install the prerequisites

- **Python 3.12 or newer**: https://www.python.org/downloads/
- **PostgreSQL 14 or newer**: either the installer from https://www.postgresql.org/download/windows/ or, in PowerShell:
  ```powershell
  winget install PostgreSQL.PostgreSQL.17
  ```
  Write down the password you choose for the `postgres` user.
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

Replace `CHANGE_ME` with the password from step 3, on both lines, then save.

### 6. Create the tables and load the sample data

```powershell
.venv\Scripts\python -m alembic upgrade head
```

This runs the migrations in `backend/alembic/versions/`. They create the tables and add 20 satellites plus one observer, Almaty (id 1), who watches the ISS.

### 7. Start the server

```powershell
.venv\Scripts\python -m uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000/docs** to try every endpoint in Swagger UI. Stop the server with `Ctrl+C`. Your data stays in PostgreSQL, so it is still there the next time you start the server.

### Run the tests

```powershell
.venv\Scripts\python -m pytest
```

### Reset to the sample data

```powershell
.venv\Scripts\python -m alembic downgrade base
.venv\Scripts\python -m alembic upgrade head
```

### macOS / Linux

The steps are the same, with these differences:
- Run `.venv/bin/python` instead of `.venv\Scripts\python`.
- Use `cp .env.example .env` instead of `copy`.
- Open psql with `psql -U postgres -h localhost`, or `sudo -u postgres psql` on Linux.

## Troubleshooting

| Message | Fix |
|---|---|
| `uvicorn` / `alembic` / `pytest` is not recognized | Run it through the virtual environment, as above: `.venv\Scripts\python -m uvicorn ...` |
| `DATABASE_URL is not set` | `backend\.env` is missing; do step 5. Run commands from inside `backend`. |
| `password authentication failed for user "satpass"` | The password in `.env` doesn't match the one from step 3. |
| `connection refused` / `Connection timed out` | PostgreSQL isn't running. In PowerShell as admin: `Start-Service postgresql-x64-17` |
| `relation "satellites" does not exist` | The tables weren't created; do step 6. |
| `Address already in use` / port 8000 busy | Start on another port: add `--port 8001` and open http://127.0.0.1:8001/docs |
