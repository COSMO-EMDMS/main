import pytest
from app import data_access

HACKATHON_TARGETS = [
    ("barnards_star",   269.452,   4.693),
    ("epsilon_indib",   330.833,  -56.786),
    ("wise_0855",       133.795,  -7.245),
    ("rw_aurigae",       73.933,  30.262),
    ("r_draconis",      245.617,  66.933),
]

@pytest.mark.hackathon
@pytest.mark.integration
@pytest.mark.parametrize("name,ra,dec", HACKATHON_TARGETS)
def test_target_returns_epochs(name, ra, dec):
    """Verify that a real query returns at least 2 epochs for each target."""
    result = data_access.fetch_cutouts(ra, dec, cutout_size="200px")
    assert len(result["epochs"]) >= 2, f"{name}: need >=2 epochs to blink"

@pytest.mark.hackathon
@pytest.mark.integration
def test_coordinate_key_is_stable():
    """The same coordinate must produce the same cache key across runs."""
    k1 = data_access.cache.coord_key(269.452, 4.693, "200px")
    k2 = data_access.cache.coord_key(269.452, 4.693, "200px")
    assert k1 == k2