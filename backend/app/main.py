"""Local fixture-only job API. Workers, not HTTP requests, perform extraction."""

import hashlib
import json
from datetime import timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.constants import JOB_TIMEOUT_SECONDS
from app.database import SessionLocal
from app.models import Job, Outbox, ProductRecord, Snapshot, utcnow
from app.schemas import JobCreate


app = FastAPI(
    title="Competitor Product Intelligence",
    description="Local development API for approved catalog extraction.",
    version="0.1.0",
)


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    """Report API process liveness, not database or broker connectivity."""
    return {"status": "ok", "service": "api"}


def job_view(job: Job) -> dict[str, Any]:
    return {
        "id": job.id, "configuration": job.configuration, "status": job.status,
        "attempts": job.attempts, "last_error": job.last_error,
        "created_at": job.created_at, "deadline_at": job.deadline_at,
        "started_at": job.started_at, "finished_at": job.finished_at,
        "attempt_log": job.attempt_log,
    }


@app.get("/ready", tags=["operations"])
def ready() -> dict[str, str]:
    try:
        with SessionLocal() as db:
            db.execute(select(Job.id).limit(1))
    except SQLAlchemyError:
        raise HTTPException(503, "Database or migration is not ready") from None
    return {"status": "ready", "database": "ok"}


@app.post("/jobs", status_code=202, tags=["jobs"])
def create_job(
    body: JobCreate,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)],
) -> dict[str, Any]:
    configuration = body.model_dump()
    request_hash = hashlib.sha256(json.dumps(configuration, sort_keys=True).encode()).hexdigest()
    now = utcnow()
    try:
        with SessionLocal.begin() as db:
            job = Job(
                idempotency_key=idempotency_key, request_hash=request_hash,
                configuration=configuration, created_at=now,
                deadline_at=now + timedelta(seconds=JOB_TIMEOUT_SECONDS),
            )
            db.add(job)
            db.flush()
            db.add(Outbox(job_id=job.id, next_dispatch_at=now))
            result = job_view(job)
        return result
    except IntegrityError:
        with SessionLocal() as db:
            job = db.scalar(select(Job).where(Job.idempotency_key == idempotency_key))
            if job is None:
                raise HTTPException(503, "Could not persist the job") from None
            if job.request_hash != request_hash:
                raise HTTPException(409, "Idempotency key was already used for a different configuration") from None
            return job_view(job)


@app.get("/jobs", tags=["jobs"])
def list_jobs(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    with SessionLocal() as db:
        jobs = db.scalars(select(Job).order_by(Job.created_at.desc()).offset(offset).limit(limit))
        return {"items": [job_view(job) for job in jobs]}


@app.get("/jobs/{job_id}", tags=["jobs"])
def get_job(job_id: UUID) -> dict[str, Any]:
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job is None:
            raise HTTPException(404, "Job not found")
        return job_view(job)


@app.post("/jobs/{job_id}/cancel", tags=["jobs"])
def cancel_job(job_id: UUID) -> dict[str, Any]:
    with SessionLocal.begin() as db:
        job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if job is None:
            raise HTTPException(404, "Job not found")
        if job.status in {"completed", "failed"}:
            raise HTTPException(409, "Job has already finished")
        if job.status != "cancelled":
            job.status, job.finished_at = "cancelled", utcnow()
            job.attempt_log = [
                {**entry, "status": "cancelled", "finished_at": job.finished_at.isoformat()}
                if entry["status"] == "running" else entry
                for entry in job.attempt_log
            ]
            job.claim_token, job.lease_until = None, None
            db.execute(delete(Outbox).where(Outbox.job_id == job_id))
        return job_view(job)


@app.get("/jobs/{job_id}/records", tags=["results"])
def get_records(job_id: UUID) -> dict[str, Any]:
    with SessionLocal() as db:
        if db.get(Job, job_id) is None:
            raise HTTPException(404, "Job not found")
        records = db.scalars(select(ProductRecord).where(ProductRecord.job_id == job_id))
        return {"items": [
            {"id": record.id, "job_id": record.job_id, "snapshot_id": record.snapshot_id,
             "fields": record.fields, "extraction_method": record.extraction_method,
             "validation_status": record.validation_status}
            for record in records
        ]}


@app.get("/records/{record_id}/evidence", tags=["results"])
def get_evidence(record_id: UUID) -> dict[str, Any]:
    with SessionLocal() as db:
        record = db.get(ProductRecord, record_id)
        if record is None:
            raise HTTPException(404, "Record not found")
        snapshot = db.get(Snapshot, record.snapshot_id)
        return {
            "snapshot_id": snapshot.id, "source_url": snapshot.source_url,
            "observed_at": snapshot.observed_at, "sha256": snapshot.sha256,
            "snapshot_text_path": f"/snapshots/{snapshot.id}",
            "fields": record.fields,
        }


@app.get("/snapshots/{snapshot_id}", response_class=PlainTextResponse, tags=["results"])
def get_snapshot(snapshot_id: UUID) -> PlainTextResponse:
    with SessionLocal() as db:
        snapshot = db.get(Snapshot, snapshot_id)
        if snapshot is None:
            raise HTTPException(404, "Snapshot not found")
        return PlainTextResponse(snapshot.html, headers={
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store",
        })
