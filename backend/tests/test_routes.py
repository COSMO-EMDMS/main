from fastapi.testclient import TestClient
from app.main import app
from app.jobstore import jobstore
from app import data_access
import app.cache as cache
from types import SimpleNamespace

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