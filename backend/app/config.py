from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    cache_dir: Path = Path("cache")
    static_dir: Path = Path("static")
    default_cutout_size: str = "200px"
    max_workers: int = 1
    retry_delay: int = 10
    max_retries: int = 5
    preview_size_px: int = 256

    class Config:
        env_prefix = "SPHEREX_"

settings = Settings()
settings.cache_dir.mkdir(parents=True, exist_ok=True)
settings.static_dir.mkdir(parents=True, exist_ok=True)