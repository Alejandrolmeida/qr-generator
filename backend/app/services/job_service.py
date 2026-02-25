"""
Job Service — gestión del ciclo de vida de jobs de generación.
Implementación en memoria para desarrollo; en producción puede sustituirse
por Redis o Azure Queue Storage.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Any

from app.models.schemas import GenerationJobResponse, JobStatus


# ─── Almacén en memoria ───────────────────────────────────────────────────────
_jobs: dict[str, GenerationJobResponse] = {}
_job_locks: dict[str, asyncio.Lock] = {}


def create_job(session_id: str, total_attendees: int) -> GenerationJobResponse:
    job_id = str(uuid.uuid4())
    job = GenerationJobResponse(
        job_id=job_id,
        session_id=session_id,
        status=JobStatus.pending,
        total_attendees=total_attendees,
    )
    _jobs[job_id] = job
    _job_locks[job_id] = asyncio.Lock()
    return job


def get_job(job_id: str) -> GenerationJobResponse | None:
    return _jobs.get(job_id)


def update_job(job_id: str, **kwargs: Any) -> GenerationJobResponse | None:
    job = _jobs.get(job_id)
    if not job:
        return None
    updated = job.model_copy(update=kwargs)
    _jobs[job_id] = updated
    return updated


def mark_running(job_id: str) -> GenerationJobResponse | None:
    return update_job(job_id, status=JobStatus.running, started_at=datetime.utcnow())


def mark_completed(
    job_id: str,
    generated: int,
    skipped: int,
    failed: int,
    download_url: str,
    stats: dict[str, Any] | None = None,
) -> GenerationJobResponse | None:
    return update_job(
        job_id,
        status=JobStatus.completed,
        generated=generated,
        skipped=skipped,
        failed=failed,
        download_url=download_url,
        stats=stats or {},
        completed_at=datetime.utcnow(),
    )


def mark_failed(job_id: str, error: str) -> GenerationJobResponse | None:
    return update_job(
        job_id,
        status=JobStatus.failed,
        error=error,
        completed_at=datetime.utcnow(),
    )


def increment_progress(job_id: str, *, generated: int = 0, skipped: int = 0, failed: int = 0) -> None:
    job = _jobs.get(job_id)
    if not job:
        return
    _jobs[job_id] = job.model_copy(
        update={
            "generated": job.generated + generated,
            "skipped": job.skipped + skipped,
            "failed": job.failed + failed,
        }
    )
