# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Meeting Assistant — microservices-based system that records/ingests audio, transcribes via faster-whisper, corrects transcripts with LLM + custom dictionary, and generates structured meeting summaries. Multiple meeting summaries can be aggregated into cross-meeting reports. All outputs can be enriched with assets (images, documents) and exported as Markdown.

## Commands

### Setup
```bash
# Install dependencies (Python 3.11+)
pip install -e ".[dev]"

# Copy and configure environment
cp .env.example .env

# Start infrastructure (Redis + MinIO)
docker compose up -d
```

### Testing
```bash
# Run all tests
pytest

# Run a single test file
pytest tests/test_correction.py

# Run a single test function
pytest tests/test_correction.py::test_corrector_applies_dictionary_before_llm

# Run with coverage
pytest --cov=core --cov-report=term-missing
```

Tests are fully self-contained — no external services needed. All LLM, storage, and STT calls use mock doubles defined in `tests/conftest.py`.

## Architecture

### Core Design Principle
`core/` is a pure sync Python library with no framework dependencies. Both the CLI and Web API call `core/` directly. This keeps business logic framework-agnostic.

### Service Map
```
Audio Input (file or recording)
    ↓
STT Service (faster-whisper)        → core/stt/
    ↓
Correction Pipeline                 → core/correction/
  Stage 1: Dictionary substitution  (deterministic, proper nouns)
  Stage 2: LLM contextual repair    (handles long-tail errors)
    ↓
LLM Summarizer + Prompt Template    → core/summary/
    ↓
Single Meeting Summary
    ├── + Assets → Markdown doc      → core/document/
    └── ↓ (multiple summaries)
       Aggregator                   → core/aggregation/
           ↓
       Cross-meeting Report + Assets → core/document/
```

### Abstraction Layers (swap without changing callers)
| Layer | Base Class | Implementations |
|-------|-----------|-----------------|
| Storage | `core/storage/base.py::BaseStorage` | `MinIOStorage` (local) → S3 (cloud) |
| LLM | `core/llm/base.py::BaseLLM` | `LiteLLMClient` supports OpenAI format + Ollama |
| STT | `core/stt/base.py::BaseSTT` | `FasterWhisperSTT` → NVIDIA Riva (future) |
| Correction | `core/correction/corrector.py` | LLM + Dictionary → replaceable pipeline |

### LLM Configuration
LiteLLM is used for all LLM calls. To switch providers, update `.env`:
- OpenAI: `LLM_MODEL=gpt-4o`, set `LLM_API_KEY`
- Ollama: `LLM_MODEL=ollama/llama3.2`, set `LLM_BASE_URL=http://localhost:11434`
- Anthropic: `LLM_MODEL=claude-sonnet-4-6`, set `LLM_API_KEY`

### Prompt Templates
Four built-in templates in `core/summary/templates.py`: `weekly_standup`, `project_review`, `client_interview`, `general`. All require `meeting_type`, `date`, `participants`, `topics` — validated before LLM call via `MeetingContext.validate()`.

### Correction Dictionary
CSV format (`wrong,correct`) or JSON format (`{"wrong": "correct"}`). Loaded via `CorrectionDictionary.load_csv()` or `.load_json()`. Applied with longest-match-first before LLM correction. Use for high-frequency proper nouns, company names, technical terms.

### CLI Usage
```bash
# Meeting management
meeting-assistant meeting create --title "Sprint Review" --date 2026-03-20 \
  --participants "Alice,Bob" --topics "進度,問題"
meeting-assistant meeting list
meeting-assistant meeting show 1

# Processing pipeline
meeting-assistant transcribe audio.mp3 --meeting-id 1
meeting-assistant correct --meeting-id 1 --dictionary dict.csv
meeting-assistant summarize --meeting-id 1 --scene weekly_standup

# Aggregation and output
meeting-assistant aggregate 1 2 3 --labels "Week1,Week2,Week3"
meeting-assistant document generate 1 --asset arch.png --output report.md

# Utilities
meeting-assistant prompt list
meeting-assistant dict validate dict.csv
```

### Web API
Gateway runs at `http://localhost:8000`. Key endpoints:
- `POST /meetings` — create meeting
- `POST /meetings/{id}/audio` — upload audio → queues STT task
- `POST /meetings/{id}/correct` — queues correction task
- `POST /meetings/{id}/summarize` — queues summary task
- `GET /tasks/{id}` — poll task status (`pending` → `running` → `done`/`failed`)
- `POST /documents/aggregate` — queues cross-meeting aggregation
- `POST /documents/generate/{summary_id}` — returns Markdown immediately
- `GET /prompts` — list prompt templates
- `GET /docs` — Swagger UI (FastAPI auto-generated)

Long-running operations (STT, LLM calls) are always async via Celery. Poll `GET /tasks/{id}` for completion.

### Infrastructure (Docker Compose)

| Container | Port | Role |
|-----------|------|------|
| `gateway` | 8000 | FastAPI REST API |
| `stt_service` | 8080 | faster-whisper，`POST /transcribe` |
| `llm_proxy` | 8001 | LiteLLM proxy，OpenAI 相容介面 |
| `task_worker` | — | Celery worker，透過 HTTP 呼叫 stt_service + llm_proxy |
| `redis` | 6379 | Celery queue broker |
| `minio` | 9000/9001 | 物件儲存（console: 9001） |

`gateway` 和 `task_worker` 不直接持有 LLM API key，全部透過 `llm_proxy` 轉發。

STT 設定（`litellm_config.yaml`）在 `llm_proxy` container 內，切換 LLM 只需改該 container 的 env vars。

Upgrade path:
- DB → PostgreSQL: `DATABASE_URL` in `.env`
- Storage → AWS S3/GCS: `MINIO_ENDPOINT` + credentials
- STT → NVIDIA Riva: 實作 `core/stt/base.py::BaseSTT` 新 client
- Docker Compose → K8s: each service 1:1 Deployment
