from pathlib import Path
import shutil
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from reproject import reproject_interp
from PIL import Image
from .config import settings

def align_to_reference(fits_paths: list[Path]) -> list[Path]:
    ref_hdul = fits.open(fits_paths[0])
    ref_wcs = WCS(ref_hdul[0].header)
    ref_shape = ref_hdul[0].data.shape
    aligned = []

    for path in fits_paths:
        hdul = fits.open(path)
        data = hdul[0].data
        wcs = WCS(hdul[0].header)
        reprojected, _ = reproject_interp((data, wcs), ref_wcs, shape_out=ref_shape)
        out_path = path.with_name(path.stem + "_aligned.fits")
        fits.writeto(out_path, reprojected, header=ref_wcs.to_header(), overwrite=True)
        aligned.append(out_path)
        hdul.close()

    ref_hdul.close()
    return aligned

def make_preview_png(fits_path: Path, out_path: Path, size_px: int = None):
    """Normalise FITS data to 8-bit and save a small PNG for fast blinking."""
    size_px = size_px or settings.preview_size_px
    data = fits.getdata(fits_path)
    vmin, vmax = np.nanpercentile(data, [1, 99])
    clipped = np.clip((data - vmin) / (vmax - vmin + 1e-9), 0, 1)
    img = Image.fromarray((clipped * 255).astype(np.uint8))
    img = img.resize((size_px, size_px), Image.LANCZOS)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)

def make_all_previews(
    output_dir: Path,
    key: str,
    progress_callback=None,
):
    fits_paths = sorted(output_dir.rglob("*.fits"))
    preview_dir = settings.static_dir / "previews" / key
    total = len(fits_paths)
    for index, fits_path in enumerate(fits_paths, start=1):
        make_preview_png(fits_path, preview_dir / f"{fits_path.stem}.png")
        fits_dir = settings.static_dir / "fits" / key
        fits_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(fits_path, fits_dir / fits_path.name)
        if progress_callback:
            progress_callback(index, total)