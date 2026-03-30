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

CMD ["celery", "-A", "services.task_worker.celery_app", "worker", "--loglevel=info", "--concurrency=1"]
