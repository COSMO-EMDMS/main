# tests/conftest.py
import pytest
from pathlib import Path
import numpy as np
from astropy.io import fits

@pytest.fixture
def fake_spxquery(monkeypatch, tmp_path):
    """Replace spxquery pipeline with a fake that writes 3 dummy FITS files."""
    output = tmp_path / "fits"
    output.mkdir()

    class FakePipeline:
        def __init__(self, config):
            self.config = config

        def run_query(self):
            pass  # pretend TAP query succeeded

        def run_download(self, skip_existing=True):
            for i in range(3):
                path = output / f"epoch_{i}.fits"
                fits.writeto(path, np.random.rand(50, 50), overwrite=True)

    monkeypatch.setattr("app.data_access.SPXQueryPipeline", FakePipeline)
    monkeypatch.setattr("app.data_access.settings.cache_dir", tmp_path)
    return output