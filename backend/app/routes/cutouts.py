import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response

from ..models import CutoutRequest, CutoutJobResponse, CutoutStatus, JobState
from ..jobstore import jobstore
from .. import cache, data_access, processing
from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cutouts", tags=["cutouts"])

# ============================================================================
# 1. ROUTES (ендпоінти)
# ============================================================================

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

    # 3. Server full — 503 with Retry-After
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
    response.headers["Cache-Control"] = "no-store"

    if cache.is_cached(job_id):
        return CutoutStatus(job_id=job_id, status=JobState.COMPLETE,
                            message="Ready", progress_percent=100.0,
                            result=cache.get_cached(job_id))

    job = jobstore.get(job_id)
    if job is None:
        raise HTTPException(404, "Unknown job")
    return CutoutStatus(job_id=job_id, **job)


# ============================================================================
# 2. BACKGROUND TASKS (фонова логіка)
# ============================================================================

async def _run_job_safely(key: str, req: CutoutRequest):
    """Обгортка, яка ловить будь-які помилки, щоб сервер не падав."""
    try:
        await _run_job(key, req)
    except Exception as exc:
        logger.exception(f"Job {key} failed")
        jobstore.update(
            key,
            status=JobState.FAILED,
            message="Failed due to an internal error",
            error=str(exc),
        )

async def _run_job(key: str, req: CutoutRequest):
    """Основна логіка: запит -> завантаження -> обробка -> кеш."""
    cutout_size = req.cutout_size or settings.default_cutout_size
    
    # Підготовка пайплайну (швидкий запит до IRSA)
    pipeline, output_dir, _ = data_access.build_pipeline(req.ra, req.dec, cutout_size)

    jobstore.update(key, status=JobState.QUERYING, message="Querying IRSA for available epochs…")
    query_started = asyncio.get_running_loop().time()
    query_heartbeat = asyncio.create_task(_query_heartbeat(key, query_started))
    try:
        await asyncio.wait_for(
            asyncio.to_thread(pipeline.run_query),
            timeout=settings.query_timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        raise RuntimeError(
            f"IRSA query timed out after {settings.query_timeout_seconds} seconds"
        ) from exc
    finally:
        query_heartbeat.cancel()

    preview_limit = data_access.limit_preview_epochs(pipeline)
    expected = data_access.count_expected_files(pipeline, output_dir)
    if preview_limit:
        expected = preview_limit
    data_access.prepare_preview_download(output_dir)
    jobstore.update(key, files_total=expected, status=JobState.QUEUED,
                    message="Waiting for download slot…")

    # Завантаження (використовує семафор з jobstore, щоб не робити паралельних запитів)
    async with jobstore.acquire_slot():
        jobstore.update(key, status=JobState.DOWNLOADING,
                        message=f"Downloading 0 / {expected or '?'} files",
                        _phase_started_monotonic=asyncio.get_running_loop().time())
        
        # Запускаємо фоновий таск для оновлення прогресу
        poller = asyncio.create_task(_poll_progress(key, output_dir, expected))
        try:
            await asyncio.to_thread(pipeline.run_download, skip_existing=True)
        finally:
            poller.cancel()

    # Обробка (створення PNG)
    jobstore.update(key, status=JobState.PROCESSING,
                    progress_percent=0.0, message="Generating previews…",
                    _phase_started_monotonic=asyncio.get_running_loop().time())
    await asyncio.to_thread(
        processing.make_all_previews,
        output_dir,
        key,
        lambda done, total: jobstore.update(
            key,
            progress_percent=round(100 * done / total, 1) if total else None,
            message=f"Generating previews {done} / {total}",
        ),
    )

    # Формування результату
    payload = data_access.collect_epochs(output_dir, key)
    if not payload["epochs"]:
        raise RuntimeError("No FITS observations were downloaded")
    cache.mark_cached(key, payload)
    
    jobstore.update(key, status=JobState.COMPLETE, message="Ready",
                    progress_percent=100.0, result=payload)


async def _query_heartbeat(key: str, started: float):
    while True:
        await asyncio.sleep(2)
        elapsed = asyncio.get_running_loop().time() - started
        jobstore.update(
            key,
            message=f"Querying IRSA for available epochs… ({elapsed:.0f}s elapsed)",
        )


async def _poll_progress(key: str, output_dir: Path, expected: int | None):
    """Кожні 2 секунди рахує файли на диску і оновлює статус."""
    while True:
        await asyncio.sleep(2)
        n = sum(
            1 for fits_path in output_dir.rglob("*.fits")
            if not fits_path.stem.endswith("_aligned")
        )
        n = min(n, expected) if expected else n
        pct = round(100 * n / expected, 1) if expected else None
        msg = f"Downloading {n} / {expected or '?'} files"
        jobstore.update(key, files_downloaded=n, progress_percent=pct, message=msg)