from enum import Enum
from pydantic import BaseModel, Field

class JobState(str, Enum):
    QUEUED = "queued"
    QUERYING = "querying"
    DOWNLOADING = "downloading"
    RATE_LIMITED = "rate_limited"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"

class CutoutRequest(BaseModel):
    ra: float = Field(..., ge=0, le=360)
    dec: float = Field(..., ge=-90, le=90)
    cutout_size: str | None = "200px"

class CutoutJobResponse(BaseModel):
    job_id: str
    status: JobState
    cached: bool
    queue_position: int | None = None       # set only when status == "queued"
    poll_url: str                            # convenience for frontend

class CutoutStatus(BaseModel):
    job_id: str
    status: JobState
    elapsed_seconds: float = 0.0
    estimated_seconds_remaining: float | None = None
    # Progress — frontend can render a real progress bar
    files_downloaded: int = 0
    files_total: int | None = None          # None until query completes
    progress_percent: float | None = None   # null when total unknown
    # Human-readable message — the single string your frontend displays
    message: str = ""
    # Backoff hint when rate-limited
    retry_after_seconds: int | None = None
    # Filled in when status == "complete"
    result: dict | None = None
    # Filled in when status == "failed"
    error: str | None = None