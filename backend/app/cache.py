import diskcache
from pathlib import Path
from .config import settings

cache = diskcache.Cache(str(settings.cache_dir / "metadata"))

def coord_key(ra: float, dec: float, cutout_size: str) -> str:
    return f"ra{ra:.4f}_dec{dec:.4f}_{cutout_size}"

def is_cached(key: str) -> bool:
    payload = cache.get(key)
    if not payload:
        return False

    epochs = payload.get("epochs") if isinstance(payload, dict) else None
    if not isinstance(epochs, list) or not epochs:
        return False

    for epoch in epochs:
        if not isinstance(epoch, dict):
            return False
        preview_url = epoch.get("img")
        fits_url = epoch.get("fits")
        if not preview_url or not fits_url:
            return False

        preview_path = settings.static_dir / preview_url.removeprefix("/static/")
        fits_path = settings.static_dir / fits_url.removeprefix("/static/")
        if not preview_path.is_file() or not fits_path.is_file():
            cache.delete(key)
            return False
    return True

def mark_cached(key: str, payload: dict) -> None:
    cache.set(key, payload, expire=None)

def get_cached(key: str) -> dict | None:
    return cache.get(key)