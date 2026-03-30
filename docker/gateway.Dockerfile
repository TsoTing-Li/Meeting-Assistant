FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir \
    fastapi \
    "uvicorn[standard]" \
    python-multipart \
    litellm \
    sqlalchemy \
    aiosqlite \
    pydantic \
    pydantic-settings \
    python-dotenv \
    jinja2 \
    celery \
    redis \
    httpx

COPY core/ ./core/
COPY services/gateway/ ./services/gateway/

CMD ["uvicorn", "services.gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
