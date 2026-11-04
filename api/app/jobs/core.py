"""Database-backed job queue run by python -m app.jobs.run_due (Render cron). No Redis."""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models.system import Job

logger = logging.getLogger("campusplug.jobs")

Handler = Callable[[Session, dict[str, Any]], None]
_handlers: dict[str, Handler] = {}
_recurring: dict[str, timedelta] = {}
MAX_ATTEMPTS = 5


def handler(kind: str, *, every: timedelta | None = None) -> Callable[[Handler], Handler]:
    """Registers a job handler. With every=..., the job re-queues itself after each run."""

    def register(fn: Handler) -> Handler:
        _handlers[kind] = fn
        if every is not None:
            _recurring[kind] = every
        return fn

    return register


def enqueue(db: Session, kind: str, payload: dict[str, Any] | None = None, run_at: datetime | None = None) -> Job:
    job = Job(kind=kind, payload=payload or {}, run_at=run_at or utcnow())
    db.add(job)
    db.flush()
    return job


def ensure_recurring(db: Session, now: datetime) -> None:
    """Makes sure every recurring job has one pending row, so the cron run always has something to do."""
    for kind in _recurring:
        if db.scalar(select(Job.id).where(Job.kind == kind, Job.status == "pending")) is None:
            enqueue(db, kind, run_at=now)
    db.commit()


def run_due(db: Session, now: datetime | None = None, limit: int = 200) -> dict[str, int]:
    """Runs every pending job whose time has come. Safe to run twice at once: rows are claimed with SKIP LOCKED on PostgreSQL."""
    now = now or utcnow()
    ensure_recurring(db, now)
    jobs = db.scalars(
        select(Job).where(Job.status == "pending", Job.run_at <= now).order_by(Job.run_at).limit(limit).with_for_update(skip_locked=True)
    ).all()
    result = {"done": 0, "retried": 0, "failed": 0}
    for job in jobs:
        job_id, kind, payload = job.id, job.kind, job.payload or {}
        job.status = "running"
        db.commit()
        try:
            fn = _handlers.get(kind)
            if fn is None:
                raise LookupError(f"No handler for {kind}")
            fn(db, payload)
            db.get(Job, job_id).status = "done"  # type: ignore[union-attr]
            result["done"] += 1
            if kind in _recurring:
                enqueue(db, kind, run_at=now + _recurring[kind])
        except Exception as exc:  # noqa: BLE001 - one failing job must not stop the rest
            db.rollback()
            failed = db.get(Job, job_id)
            if failed is None:
                continue
            failed.attempts += 1
            failed.last_error = type(exc).__name__  # never store payload data or secrets
            if failed.attempts >= MAX_ATTEMPTS:
                failed.status = "failed"
                result["failed"] += 1
            else:
                failed.status = "pending"
                failed.run_at = now + timedelta(minutes=2**failed.attempts)
                result["retried"] += 1
            logger.warning("job %s failed: %s", kind, type(exc).__name__)
        db.commit()
    return result
