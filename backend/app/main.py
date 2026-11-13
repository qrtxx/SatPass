from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.errors import DomainError
from app.routers import observers, satellites

app = FastAPI(
    title="SatPass API",
    version="1.0.0",
    description="Predicts when satellites pass over an observer, from CelesTrak orbital elements. "
    "Data lives in memory and is reset to a seed snapshot on every restart.",
)
app.include_router(satellites.router)
app.include_router(observers.router)


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message, "code": exc.code})


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")
