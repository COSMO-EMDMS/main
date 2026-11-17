from pathlib import Path
import sys
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SPHEREX_")

    cache_dir: Path = Path("cache")
    static_dir: Path = Path("static")
    default_cutout_size: str = "200px"
    max_workers: int = 1
    retry_delay: int = 10
    max_retries: int = 5
    preview_size_px: int = 256
    query_timeout_seconds: int = 120


settings = Settings()
settings.cache_dir.mkdir(parents=True, exist_ok=True)
settings.static_dir.mkdir(parents=True, exist_ok=True)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")