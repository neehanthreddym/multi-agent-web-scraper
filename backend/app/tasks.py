"""Claim, fetch, extract and persist a single page with bounded recovery."""

import hashlib
from datetime import timedelta
from uuid import UUID, uuid4

import httpx
from billiard.exceptions import SoftTimeLimitExceeded
from sqlalchemy import delete, select

from app.celery_app import celery_app
from app.constants import LEASE_SECONDS, MAX_ATTEMPTS
from app.database import SessionLocal
from app.extraction import ExtractionError, extract_fields, fetch_page
from app.models import Job, Outbox, ProductRecord, Snapshot, utcnow
from app.schemas import JobCreate


def clear_dispatch(db, job: Job) -> None:
    job.claim_token, job.lease_until = None, None
    db.execute(delete(Outbox).where(Outbox.job_id == job.id))


def update_attempt(job: Job, status: str, error: str | None = None) -> None:
    job.attempt_log = [
        {**entry, "status": status, "finished_at": utcnow().isoformat(), "error": error}
        if entry["attempt"] == job.attempts else entry
        for entry in job.attempt_log
    ]


@celery_app.task(name="app.process_job")
def process_job(job_id: str) -> None:
    identity, token = UUID(job_id), uuid4()
    now = utcnow()
    with SessionLocal.begin() as db:
        job = db.scalar(select(Job).where(Job.id == identity).with_for_update())
        if job is None or job.status in {"completed", "failed", "cancelled"}:
            return
        if job.status == "running" and job.lease_until and job.lease_until > now:
            return
        if job.status == "running":
            update_attempt(job, "interrupted", "Previous worker lease expired")
        if job.attempts >= MAX_ATTEMPTS or job.deadline_at <= now:
            job.status, job.finished_at = "failed", now
            job.last_error = "Attempt or job-time budget exhausted"
            clear_dispatch(db, job)
            return
        job.attempts += 1
        job.status, job.claim_token = "running", token
        job.started_at = job.started_at or now
        job.lease_until = now + timedelta(seconds=LEASE_SECONDS)
        job.attempt_log = [*job.attempt_log, {
            "attempt": job.attempts, "status": "running", "started_at": now.isoformat(),
        }]
        attempt, configuration = job.attempts, dict(job.configuration)

    try:
        config = JobCreate.model_validate(configuration)
        # Recheck cancellation immediately before network work.
        with SessionLocal() as db:
            job = db.get(Job, identity)
            if job.status != "running" or job.claim_token != token:
                return
        raw = fetch_page(config.seed_url)
        observed_at, html = utcnow(), raw.decode("utf-8")
        with SessionLocal.begin() as db:
            job = db.scalar(select(Job).where(Job.id == identity).with_for_update())
            if job.status != "running" or job.claim_token != token:
                return
            snapshot = Snapshot(
                job_id=identity, attempt=attempt, source_url=config.seed_url,
                observed_at=observed_at, sha256=hashlib.sha256(raw).hexdigest(), html=html,
            )
            db.add(snapshot)
            db.flush()
            snapshot_id = snapshot.id
        # Retain the fetched snapshot even when extraction subsequently fails.
        fields = extract_fields(html, config.selected_fields, source_url=config.seed_url)
        with SessionLocal.begin() as db:
            job = db.scalar(select(Job).where(Job.id == identity).with_for_update())
            if job.status != "running" or job.claim_token != token:
                return
            if job.deadline_at <= utcnow():
                raise ExtractionError("Job-time budget exhausted")
            db.add(ProductRecord(
                job_id=identity, snapshot_id=snapshot_id, fields=fields,
                validation_status="valid" if all(
                    item["value"] is not None for item in fields.values()
                ) else "needs_review",
            ))
            job.status, job.finished_at, job.last_error = "completed", utcnow(), None
            update_attempt(job, "completed")
            clear_dispatch(db, job)
    except Exception as error:
        retryable = isinstance(error, (httpx.RequestError, SoftTimeLimitExceeded))
        if isinstance(error, httpx.HTTPStatusError):
            retryable = error.response.status_code in {408, 429} or error.response.status_code >= 500
        message = str(error) if isinstance(error, ExtractionError) else f"Processing failed ({type(error).__name__})"
        with SessionLocal.begin() as db:
            job = db.scalar(select(Job).where(Job.id == identity).with_for_update())
            if job.status != "running" or job.claim_token != token:
                return
            update_attempt(job, "failed", message)
            job.last_error, job.claim_token, job.lease_until = message, None, None
            if retryable and job.attempts < MAX_ATTEMPTS and job.deadline_at > utcnow():
                job.status = "queued"
                entry = db.get(Outbox, identity)
                entry.next_dispatch_at = utcnow() + timedelta(seconds=2 ** job.attempts)
            else:
                job.status, job.finished_at = "failed", utcnow()
                clear_dispatch(db, job)
