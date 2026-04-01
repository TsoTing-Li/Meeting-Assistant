# Development Guide

## Prerequisites

- Python 3.11+
- Docker + Docker Compose (for the full stack)
- NVIDIA Container Toolkit (for GPU STT acceleration)

## Setup

```bash
git clone <repo-url>
cd meeting_assistant

# Install all dependencies including dev tools
pip install -e ".[dev]"

# Copy and configure environment
cp .env.example .env
# Edit .env — set at minimum LLM_MODEL, LLM_BASE_URL or LLM_API_KEY
```

### Start infrastructure only (recommended for development)

```bash
# Redis only — gateway and task_worker run locally
docker compose up redis -d

# Start gateway (in one terminal)
uvicorn services.gateway.main:app --reload --port 8000

# Start STT task worker (in another terminal)
celery -A services.task_worker.celery_app worker -Q stt --concurrency=2 --loglevel=info

# Start LLM task worker (in another terminal)
celery -A services.task_worker.celery_app worker -Q llm --concurrency=4 --loglevel=info
```

### Start full stack

```bash
docker compose up -d --build

# Code changes to core/ and services/ take effect without rebuilding
# (docker-compose.override.yml mounts source dirs as volumes)

# Rebuild after dependency or Dockerfile changes
docker compose up -d --build gateway task_worker_stt task_worker_llm

# STT service only (GPU machine, standalone)
docker compose up --build stt_service
```

## Testing

All tests are self-contained — no external services, no Docker required. The test suite uses in-memory SQLite, `MockStorage`, and mocked Celery.

```bash
# Run all tests
pytest

# Run a specific file
pytest tests/test_correction.py

# Run a specific test
pytest tests/test_api_meetings.py::test_upload_audio_queues_celery_task

# With coverage
pytest --cov=core --cov-report=term-missing
```

### Test structure

```
tests/
├── conftest.py              # Shared fixtures: MockLLM, MockStorage, MockSTT, api_client
├── test_models.py           # SQLAlchemy model property tests
├── test_correction.py       # CorrectionDictionary + TranscriptCorrector
├── test_summary.py          # MeetingContext, PromptTemplate, MeetingSummarizer
├── test_aggregation.py      # MeetingAggregator
├── test_document.py         # DocumentGenerator
├── test_llm.py              # BaseLLM / MockLLM
├── test_stt.py              # BaseSTT / MockSTT
├── test_storage.py          # BaseStorage / MockStorage
├── test_api_meetings.py     # /meetings endpoints (FastAPI TestClient)
├── test_api_tasks.py        # /tasks endpoints
├── test_api_prompts.py      # /prompts endpoints
├── test_api_documents.py    # /documents endpoints
└── test_cli.py              # CLI commands (Typer CliRunner)
```

The `api_client` fixture in `conftest.py` wires up a `TestClient` with:
- In-memory SQLite via `aiosqlite`
- `MockStorage` (in-memory, no filesystem)
- `celery_app.send_task` patched (no Redis)
- `init_db_async` patched (no-op, tables created before the client opens)

## Project Structure

```
meeting_assistant/
├── core/                        # Framework-agnostic Python library
│   ├── llm/
│   │   ├── base.py              # BaseLLM ABC
│   │   └── litellm_client.py   # LiteLLM implementation
│   ├── stt/
│   │   ├── base.py              # BaseSTT ABC
│   │   ├── faster_whisper_client.py  # Local faster-whisper
│   │   └── http_client.py      # HTTP client for stt_service
│   ├── storage/
│   │   ├── base.py              # BaseStorage ABC
│   │   └── local_client.py     # Local filesystem implementation
│   ├── correction/
│   │   ├── dictionary.py       # CorrectionDictionary (longest-match, single-pass)
│   │   └── corrector.py        # TranscriptCorrector (dict → LLM pipeline)
│   ├── summary/
│   │   ├── templates.py        # MeetingContext, PromptTemplate, BUILTIN_TEMPLATES
│   │   └── summarizer.py       # MeetingSummarizer
│   ├── aggregation/
│   │   └── aggregator.py       # MeetingAggregator
│   ├── document/
│   │   └── generator.py        # DocumentGenerator (Markdown with assets)
│   ├── models/
│   │   ├── meeting.py           # Meeting (UUID PK)
│   │   ├── transcript.py        # Transcript (audio_ref, raw_ref, corrected_ref)
│   │   ├── summary.py           # Summary (content, is_aggregated, source_meeting_ids)
│   │   ├── task.py              # Task (status, celery_task_id, input_ref, output_ref)
│   │   └── prompt.py            # SystemPrompt (builtin flag, scene enum)
│   ├── database.py              # Sync + async SQLAlchemy engines, Base
│   ├── config.py                # Pydantic Settings (reads .env)
│   └── exceptions.py            # Domain exceptions
│
├── cli/
│   └── main.py                  # Typer app: transcribe, correct, summarize, aggregate, prompts
│
├── services/
│   ├── gateway/
│   │   ├── main.py              # FastAPI app, lifespan, CORS, static, /info endpoint
│   │   ├── dependencies.py      # get_db (async), get_storage, get_llm
│   │   ├── routers/
│   │   │   ├── meetings.py      # /meetings CRUD, audio upload, transcript input, correct, summarize
│   │   │   ├── tasks.py         # /tasks list, get, cancel, SSE stream
│   │   │   ├── prompts.py       # /prompts CRUD
│   │   │   └── documents.py     # /documents aggregate, aggregations, generate
│   │   └── static/
│   │       └── index.html       # Single-file Web UI (vanilla JS, 4 tabs)
│   │
│   ├── stt_service/
│   │   └── main.py              # FastAPI: POST /transcribe → faster-whisper (GPU)
│   │
│   └── task_worker/
│       ├── celery_app.py        # Celery config (Redis broker/backend)
│       └── tasks/
│           ├── stt.py           # run_stt: HTTP → stt_service → write raw_ref
│           ├── correction.py    # run_correction: dict + LLM → write corrected_ref
│           ├── summary.py       # run_summary: template + LLM → write Summary row
│           └── aggregation.py   # run_aggregation: multiple summaries → write Summary row
│
├── docker/
│   ├── gateway.Dockerfile
│   ├── task_worker.Dockerfile
│   └── stt_service.Dockerfile   # CUDA 12.2 base image for GPU acceleration
│
├── tests/
├── docker-compose.yml
├── docker-compose.override.yml  # Dev overrides: source mounts, HuggingFace cache
├── pyproject.toml
└── .env.example
```

## Key Design Decisions

### `core/` is a pure sync library

`core/` has no framework dependency (no FastAPI, no Celery). Both the CLI and the API call `core/` directly. This keeps business logic testable in isolation and makes it easy to swap the serving layer.

The gateway uses async SQLAlchemy (`AsyncSession`). Celery workers use the sync engine. Both are maintained in `core/database.py` and share the same `Base`.

### UUID primary keys

All models use `uuid.UUID` primary keys (`Uuid` SQLAlchemy type). Celery serializes them as strings (`str(uuid)`) when passing as task args, and converts back with `uuid.UUID(...)` inside the task.

### Task status lives in the database

Task status (`pending → running → done / failed / cancelled`) is stored in the `tasks` table, not in Redis. Rationale: tasks are long-running (seconds to hours); status must survive beyond Redis TTL and be queryable by `meeting_id`.

### SSE polls the database

`GET /tasks/{id}/stream` opens a `StreamingResponse` that polls the DB every 2 seconds and yields an SSE event on each status change. No WebSocket needed; simple to implement and proxy-friendly.

### Per-request LLM/STT overrides

Every task endpoint (`/correct`, `/summarize`, `/aggregate`, `/audio`) accepts optional `llm_base_url`, `llm_model`, `llm_api_key` (and `stt_url` for audio upload). These are passed through to the Celery task and used to construct the client, falling back to `.env` values if not provided. The Web UI stores these overrides in `localStorage` and injects them per request.

### LLM `<think>` tag stripping

Qwen3 (and similar reasoning models) emit `<think>...</think>` blocks before the answer. `LiteLLMClient` strips these with a regex before returning content to callers.

## Adding a New LLM Provider

LiteLLM handles routing automatically. In `.env`, set:
- `LLM_MODEL` to `<prefix>/<model-name>` (prefix: `openai`, `ollama`, `anthropic`, etc.)
- `LLM_BASE_URL` if the server is not the default cloud endpoint
- `LLM_API_KEY` if required

No code changes needed.

## Adding a New STT Backend

Implement `core/stt/base.py::BaseSTT`:

```python
class MySTTClient(BaseSTT):
    def transcribe(self, audio_path: str, language: str = "zh") -> STTResult:
        ...
```

Then update `services/gateway/dependencies.py::get_stt()` to return the new client.

## Adding a New Storage Backend

Implement `core/storage/base.py::BaseStorage` and update `get_storage()` in `core/storage/__init__.py`:

```python
class S3Storage(BaseStorage):
    def upload(self, key, data, content_type): ...
    def download(self, key): ...
    def delete(self, key): ...
    def get_url(self, key, expires_seconds=3600): ...
    def exists(self, key): ...
```

## Useful Commands

```bash
# Check what's running
docker compose ps

# Follow task worker logs
docker compose logs -f task_worker_stt task_worker_llm

# Follow STT service logs (includes model download progress)
docker compose logs -f stt_service

# Open a shell in the gateway container
docker exec -it meeting_assistant-gateway-1 bash

# Manually trigger a Celery task (debugging)
docker exec -it meeting_assistant-task_worker_llm-1 \
  celery -A services.task_worker.celery_app inspect active

# Purge all Celery queues (clears stuck tasks)
docker exec -it meeting_assistant-task_worker_llm-1 \
  celery -A services.task_worker.celery_app purge
```
