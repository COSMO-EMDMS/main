import asyncio
from datetime import datetime, timezone
from .models import JobState

# Server policy
MAX_QUEUE = 5              # after this, POST returns 503
DOWNLOAD_SLOTS = 1         # only one spxquery download at a time (avoids 503s)

class JobStore:
    def __init__(self):
        self.jobs: dict[str, dict] = {}
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(DOWNLOAD_SLOTS)

    def _active_count(self) -> int:
        return sum(1 for j in self.jobs.values()
                   if j["status"] in (JobState.QUEUED, JobState.QUERYING,
                                      JobState.DOWNLOADING, JobState.RATE_LIMITED,
                                      JobState.PROCESSING))

    def _queue_position(self, key: str) -> int | None:
        """Position in FIFO order among non-running jobs. None if not queued."""
        if self.jobs.get(key, {}).get("status") != JobState.QUEUED:
            return None
        queued = [k for k, j in self.jobs.items() if j["status"] == JobState.QUEUED]
        try:
            return queued.index(key) + 1
        except ValueError:
            return None

    def is_full(self) -> bool:
        return self._active_count() >= MAX_QUEUE

    def create(self, key: str) -> None:
        self.jobs[key] = {
            "status": JobState.QUEUED,
            "files_downloaded": 0,
            "files_total": None,
            "progress_percent": None,
            "message": "Queued",
            "retry_after_seconds": None,
            "result": None,
            "error": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def update(self, key: str, **fields) -> None:
        if key in self.jobs:
            self.jobs[key].update(fields)

    def get(self, key: str) -> dict | None:
        job = self.jobs.get(key)
        if job is None:
            return None
        out = dict(job)
        out["queue_position"] = self._queue_position(key)
        return out

    async def acquire_slot(self):
        async with self._semaphore:
            yield

jobstore = JobStore()