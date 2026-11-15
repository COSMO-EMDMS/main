from pathlib import Path
import matplotlib
from spxquery import SPXQueryPipeline, Source, QueryConfig
from spxquery.core.config import DownloadConfig, AdvancedConfig
from .config import settings
from . import cache

if not hasattr(matplotlib.cm, "get_cmap"):
    def _get_cmap(name=None, lut=None):
        if name is None:
            name = matplotlib.rcParams["image.cmap"]
        if isinstance(name, matplotlib.colors.Colormap):
            return name
        return matplotlib.colormaps[name]

    matplotlib.cm.get_cmap = _get_cmap

def build_pipeline(ra: float, dec: float, cutout_size: str):
    key = cache.coord_key(ra, dec, cutout_size)
    output_dir = settings.cache_dir / "fits" / key
    output_dir.mkdir(parents=True, exist_ok=True)

    source = Source(ra=ra, dec=dec, name=key)
    query = QueryConfig(source=source, output_dir=str(output_dir))
    download = DownloadConfig(
        cutout_size=cutout_size,
        max_download_workers=settings.max_workers,  # ← правильно
        max_retries=settings.max_retries,
        retry_delay=settings.retry_delay,
        timeout=300,
    )
    pipeline = SPXQueryPipeline(AdvancedConfig(query=query, download=download))
    return pipeline, output_dir, key

def count_expected_files(pipeline, output_dir: Path) -> int | None:
    for candidate in output_dir.glob("query_results*.csv"):
        with open(candidate) as f:
            return sum(1 for _ in f) - 1   # minus header
    # Some versions keep it on the pipeline object
    for attr in ("query_results", "_query_results", "results_table"):
        obj = getattr(pipeline, attr, None)
        if obj is not None:
            try:
                return len(obj)
            except TypeError:
                pass
    return None