from fastapi.testclient import TestClient
from app.main import app
from app.jobstore import jobstore
import app.cache as cache

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