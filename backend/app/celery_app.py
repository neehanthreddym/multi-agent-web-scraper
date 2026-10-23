"""One bounded local worker; PostgreSQL remains the source of job state."""

import os
from urllib.parse import quote

from celery import Celery


password = quote(os.environ.get("RABBITMQ_PASSWORD", "catalog-local-only"), safe="")
celery_app = Celery(
    "catalog", broker=f"amqp://catalog:{password}@rabbitmq:5672//",
    include=["app.tasks"],
)
celery_app.conf.update(
    task_default_queue="catalog",
    task_default_delivery_mode=2,
    # RabbitMQ 4.3 rejects non-durable, non-exclusive queues. Control/reply
    # and event queues are temporary and belong to their creating connection;
    # the catalog task queue remains durable and non-exclusive.
    control_queue_exclusive=True,
    control_queue_durable=False,
    event_queue_exclusive=True,
    event_queue_durable=False,
    task_serializer="json",
    accept_content=["json"],
    task_ignore_result=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    worker_cancel_long_running_tasks_on_connection_loss=True,
    broker_connection_retry_on_startup=True,
    broker_connection_timeout=3,
    broker_transport_options={"confirm_publish": True, "read_timeout": 5, "write_timeout": 5},
    task_soft_time_limit=45,
    task_time_limit=60,
    timezone="UTC",
)
