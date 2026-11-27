from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.exc import IntegrityError

from app.errors import DomainError
from app.routers import auth, observers, places, satellites

app = FastAPI(
    title="SatPass API",
    version="1.0.0",
    description="Predicts when satellites pass over an observer, from CelesTrak orbital elements. "
    "Data is stored in PostgreSQL.",
)
app.include_router(auth.router)
app.include_router(satellites.router)
app.include_router(observers.router)
app.include_router(places.router)


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message, "code": exc.code}, headers=exc.headers)


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    # Services check the rules first; this catches races, e.g. two requests creating the same name at once.
    return JSONResponse(status_code=409, content={"detail": "The change conflicts with existing data", "code": "integrity_error"})


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")
