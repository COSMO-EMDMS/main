from fastapi import APIRouter, BackgroundTasks, HTTPException, Response
from ..models import CutoutRequest, CutoutJobResponse, CutoutStatus, JobState
from ..jobstore import jobstore
from .. import cache, data_access
from ..config import settings
import asyncio

router = APIRouter(prefix="/api/cutouts", tags=["cutouts"])

@router.post("", response_model=CutoutJobResponse, status_code=202)
async def submit(req: CutoutRequest, bg: BackgroundTasks, response: Response):
    key = cache.coord_key(req.ra, req.dec, req.cutout_size or settings.default_cutout_size)

    # 1. Cache hit — return immediately (200)
    if cache.is_cached(key):
        response.status_code = 200
        return CutoutJobResponse(job_id=key, status=JobState.COMPLETE,
                                 cached=True, poll_url=f"/api/cutouts/{key}")

    # 2. Same job already running — return the same job_id (idempotent)
    existing = jobstore.get(key)
    if existing and existing["status"] not in (JobState.COMPLETE, JobState.FAILED):
        response.status_code = 200
        return CutoutJobResponse(job_id=key, status=existing["status"], cached=False,
                                 queue_position=existing.get("queue_position"),
                                 poll_url=f"/api/cutouts/{key}")

    # 3. Server full — 503 with Retry-After (frontend shows "try again in N s")
    if jobstore.is_full():
        raise HTTPException(status_code=503,
                            detail="Server busy, try again shortly",
                            headers={"Retry-After": "30"})

    # 4. Accept the job
    jobstore.create(key)
    bg.add_task(_run_job_safely, key, req)
    return CutoutJobResponse(job_id=key, status=JobState.QUEUED, cached=False,
                             poll_url=f"/api/cutouts/{key}")


@router.get("/{job_id}", response_model=CutoutStatus)
async def status(job_id: str, response: Response):
    # Polling responses must never be cached by the browser
    response.headers["Cache-Control"] = "no-store"

    if cache.is_cached(job_id):
        return CutoutStatus(job_id=job_id, status=JobState.COMPLETE,
                            message="Ready", progress_percent=100.0,
                            result=cache.get_cached(job_id))

    job = jobstore.get(job_id)
    if job is None:
        raise HTTPException(404, "Unknown job")
    return CutoutStatus(job_id=job_id, **job)