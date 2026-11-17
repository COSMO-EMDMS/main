from fastapi.testclient import TestClient
from app.main import app
from app.jobstore import jobstore
from app import data_access
import app.cache as cache
from types import SimpleNamespace
from pathlib import Path

def test_cache_hit_returns_200_immediately(monkeypatch):
    monkeypatch.setattr(cache, "is_cached", lambda k: True)
    client = TestClient(app)
    r = client.post("/api/cutouts", json={"ra": 269.452, "dec": 4.693})
    assert r.status_code == 200
    assert r.json()["cached"] is True

def test_full_server_returns_503_with_retry_after():
    for i in range(5):
        jobstore.create(f"job{i}")
    client = TestClient(app)
    r = client.post("/api/cutouts", json={"ra": 1.0, "dec": 1.0})
    assert r.status_code == 503
    assert r.headers["Retry-After"] == "30"

def test_preview_epochs_are_capped_across_bands(monkeypatch):
    observations = [
        SimpleNamespace(band=band, mjd=float(index))
        for band in ("D1", "D2", "D3", "D4", "D5", "D6")
        for index in range(1, 11)
    ]
    query_results = SimpleNamespace(
        observations=observations,
        band_counts={},
    )
    pipeline = SimpleNamespace(
        state=SimpleNamespace(query_results=query_results),
    )
    monkeypatch.setattr(data_access.settings, "max_preview_epochs", 12)

    selected = data_access.limit_preview_epochs(pipeline)

    assert selected == 12
    assert len(query_results.observations) == 12
    assert set(query_results.band_counts) == {"D1", "D2", "D3", "D4", "D5", "D6"}

def test_prepare_preview_download_removes_stale_fits(tmp_path):
    stale = tmp_path / "old.fits"
    stale.write_bytes(b"stale")

    data_access.prepare_preview_download(tmp_path)

    assert not stale.exists()

def test_cache_hit_requires_preview_and_fits_files(monkeypatch, tmp_path):
    payload = {
        "epochs": [{
            "name": "epoch",
            "img": "/static/previews/test/epoch.png",
            "fits": "/static/fits/test/epoch.fits",
        }]
    }
    class FakeCache:
        def get(self, key):
            return payload
        def delete(self, key):
            pass

    monkeypatch.setattr(cache, "cache", FakeCache())
    monkeypatch.setattr(cache.settings, "static_dir", tmp_path)

    assert cache.is_cached("test") is False

def test_collect_epochs_deduplicates_and_caps(tmp_path):
    nested = tmp_path / "nested"
    nested.mkdir()
    (tmp_path / "epoch_a.fits").write_bytes(b"a")
    (nested / "epoch_a.fits").write_bytes(b"duplicate")
    for index in range(20):
        (tmp_path / f"epoch_{index}.fits").write_bytes(str(index).encode())

    payload = data_access.collect_epochs(tmp_path, "test-key")

    assert len(payload["epochs"]) == 12
    assert len({epoch["name"] for epoch in payload["epochs"]}) == 12

def test_observation_week_fallback_formats_as_date(tmp_path):
    fits_path = tmp_path / "2025W35_1A_0432_4.fits"
    date = data_access._observation_date(fits_path)

    assert date.startswith("2025-")