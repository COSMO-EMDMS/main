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
        max_download_workers=settings.max_workers,
        max_retries=settings.max_retries,
        retry_delay=settings.retry_delay,
        chunk_size=64 * 1024,
        timeout=300,
    )
    pipeline = SPXQueryPipeline(AdvancedConfig(query=query, download=download))
    return pipeline, output_dir, key

def limit_preview_epochs(pipeline) -> int:
    """Keep only a small, evenly spaced set of observations for preview jobs."""
    query_results = getattr(getattr(pipeline, "state", None), "query_results", None)
    observations = getattr(query_results, "observations", None)
    if not observations:
        return 0

    per_band = max(1, settings.max_preview_epochs // 6)
    selected = []
    for band in ("D1", "D2", "D3", "D4", "D5", "D6"):
        band_observations = sorted(
            (observation for observation in observations if observation.band == band),
            key=lambda observation: observation.mjd,
        )
        if not band_observations:
            continue
        if len(band_observations) <= per_band:
            selected.extend(band_observations)
            continue
        indexes = {
            round(index * (len(band_observations) - 1) / (per_band - 1))
            for index in range(per_band)
        } if per_band > 1 else {0}
        selected.extend(band_observations[index] for index in sorted(indexes))

    selected = sorted(selected, key=lambda observation: observation.mjd)
    query_results.observations = selected[:settings.max_preview_epochs]
    query_results.band_counts = {
        band: sum(observation.band == band for observation in query_results.observations)
        for band in ("D1", "D2", "D3", "D4", "D5", "D6")
        if any(observation.band == band for observation in query_results.observations)
    }
    return len(query_results.observations)

def prepare_preview_download(output_dir: Path) -> None:
    """Remove stale FITS files so cache keys cannot report files from earlier jobs."""
    for fits_path in output_dir.rglob("*.fits"):
        fits_path.unlink(missing_ok=True)

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

def collect_epochs(output_dir: Path, key: str) -> dict:
    fits_paths = sorted(output_dir.rglob("*.fits"))
    return {
        "epochs": [
            {
                "name": path.stem,
                "img": f"/static/previews/{key}/{path.stem}.png",
                "fits": f"/static/fits/{key}/{path.name}",
            }
            for path in fits_paths
        ]
    }