import diskcache
from pathlib import Path
from .config import settings

cache = diskcache.Cache(str(settings.cache_dir / "metadata"))

def coord_key(ra: float, dec: float, cutout_size: str) -> str:
    return f"ra{ra:.4f}_dec{dec:.4f}_{cutout_size}"

def is_cached(key: str) -> bool:
    return cache.get(key) is not None

def mark_cached(key: str, payload: dict) -> None:
    cache.set(key, payload, expire=None)

def get_cached(key: str) -> dict | None:
    return cache.get(key)