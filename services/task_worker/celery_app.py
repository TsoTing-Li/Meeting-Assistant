from celery import Celery
from kombu import Queue
from core.config import settings

celery_app = Celery(
    "meeting_assistant",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "services.task_worker.tasks.stt",
        "services.task_worker.tasks.correction",
        "services.task_worker.tasks.summary",
        "services.task_worker.tasks.aggregation",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=86400,           # 24 hours

    # Queue routing: STT tasks → stt queue, LLM tasks → llm queue
    task_queues=(
        Queue("stt"),
        Queue("llm"),
    ),
    task_routes={
        "services.task_worker.tasks.stt.*":         {"queue": "stt"},
        "services.task_worker.tasks.correction.*":  {"queue": "llm"},
        "services.task_worker.tasks.summary.*":     {"queue": "llm"},
        "services.task_worker.tasks.aggregation.*": {"queue": "llm"},
    },
    task_default_queue="llm",
)
