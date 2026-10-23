"""Check actual Celery queue declarations without contacting the broker."""

from celery.events import EventReceiver

from app.celery_app import celery_app


def test_temporary_queues_are_compatible_with_rabbitmq_43():
    mailbox = celery_app.control.mailbox
    queues = [
        mailbox.get_queue("local-test-worker"),
        mailbox.get_reply_queue(),
        EventReceiver(None, app=celery_app).queue,
    ]
    for queue in queues:
        assert queue.exclusive is True
        assert queue.durable is False
        assert queue.auto_delete is True


def test_job_queue_remains_durable_and_shared():
    queue = celery_app.amqp.queues["catalog"]
    assert queue.durable is True
    assert not queue.exclusive
    assert celery_app.conf.task_default_delivery_mode == 2
