import pytest
from app.jobstore import JobStore
from app.models import JobState

def test_queue_position_reports_fifo_order():
    s = JobStore()
    s.create("a"); s.create("b"); s.create("c")
    assert s.get("a")["queue_position"] == 1
    assert s.get("b")["queue_position"] == 2
    assert s.get("c")["queue_position"] == 3

def test_server_busy_at_capacity():
    s = JobStore()
    for i in range(5):                      # MAX_QUEUE = 5
        s.create(f"job{i}")
    assert s.is_full() is True

def test_completed_jobs_do_not_count_toward_capacity():
    s = JobStore()
    for i in range(5):
        s.create(f"job{i}")
        s.update(f"job{i}", status=JobState.COMPLETE)
    assert s.is_full() is False