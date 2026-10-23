"""Publish committed outbox entries; repeat delivery is safe for the worker."""

import logging
import time
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select

from app.celery_app import celery_app
from app.constants import LEASE_SECONDS
from app.database import SessionLocal
from app.models import Outbox, utcnow


HEARTBEAT = Path("/tmp/catalog-dispatcher-heartbeat")
logger = logging.getLogger(__name__)


def dispatch_once() -> None:
    now = utcnow()
    with SessionLocal.begin() as db:
        pending = list(db.scalars(
            select(Outbox).where(Outbox.next_dispatch_at <= now)
            .order_by(Outbox.next_dispatch_at).limit(10).with_for_update(skip_locked=True)
        ))
        for entry in pending:
            # Publish before marking: crashes can duplicate messages, never silently
            # discard the database's request. Worker leases guard duplicate execution.
            celery_app.send_task("app.process_job", args=[str(entry.job_id)], retry=False)
            entry.next_dispatch_at = now + timedelta(seconds=LEASE_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            dispatch_once()
            HEARTBEAT.touch()
        except Exception as error:
            # Do not print connection strings or credentials.
            logger.error("Dispatch loop failed (%s); will retry", type(error).__name__)
        time.sleep(2)
