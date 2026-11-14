from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
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

# Serve FITS and PNGs directly — Aladin Lite loads FITS from a URL
app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")