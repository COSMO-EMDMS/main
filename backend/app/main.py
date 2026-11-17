from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from .routes import cutouts
from .config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-create static subdirectories so Aladin Lite can fetch files immediately
    (settings.static_dir / "fits").mkdir(parents=True, exist_ok=True)
    (settings.static_dir / "previews").mkdir(parents=True, exist_ok=True)
    yield

app = FastAPI(title="SPHEREx Blink Backend", lifespan=lifespan)
app.include_router(cutouts.router)

@app.middleware("http")
async def disable_frontend_asset_cache(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.endswith((".html", ".js", ".css")):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Serve FITS and PNGs directly — Aladin Lite loads FITS from a URL
app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")

frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
if frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")