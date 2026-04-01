FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    litellm \
    sqlalchemy \
    aiosqlite \
    pydantic \
    pydantic-settings \
    python-dotenv \
    celery \
    redis \
    httpx

COPY core/ ./core/
COPY services/task_worker/ ./services/task_worker/

CMD ["sh", "-c", "celery -A services.task_worker.celery_app worker -Q ${CELERY_QUEUES:-llm} --concurrency=${CELERY_CONCURRENCY:-1} --loglevel=info"]
