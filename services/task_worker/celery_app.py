from celery import Celery
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
    worker_prefetch_multiplier=1,   # One task at a time (STT is memory-intensive)
    result_expires=86400,           # 24 hours
)
