# Architecture

## Overview

Meeting Assistant is a microservices system. All services run in Docker containers and communicate over HTTP or through a shared message queue (Redis + Celery).

The central design principle is that **`core/` is a pure sync Python library with no framework dependencies**. Both the CLI and the API call `core/` directly, keeping business logic testable in isolation.

---

## Service Map

```
┌────────────────────────────────────────────────────────────┐
│                     Client Layer                           │
│        Browser (Web UI)          CLI (standalone)          │
└──────────────────┬─────────────────────────────────────────┘
                   │ HTTP
                   ▼
┌──────────────────────────────────────────────────────────────┐
│   gateway  (port 8000)                                       │
│   FastAPI + async SQLAlchemy                                 │
│   Serves Web UI at GET /                                     │
│   Serves stored files at GET /storage/{key}                  │
│   Forwards long tasks → Redis → task_worker via Celery       │
└───────┬─────────────────────────────────────────────────────┘
        │ Celery (Redis broker)
        ▼
┌──────────────────────────────────────────────────────────────┐
│   task_worker                                                │
│   Celery workers (sync)                                      │
│   - run_stt        → HTTP → stt_service                     │
│   - run_correction → LLM API (direct)                       │
│   - run_summary    → LLM API (direct)                       │
│   - run_aggregation→ LLM API (direct)                       │
└───────┬─────────────────────────────────────────────────────┘
        │
        ├─── HTTP ──► stt_service (port 8080)  [faster-whisper, GPU]
        │
        └─── HTTP ──► LLM server (user-configured, any OpenAI-compatible)
                      e.g. vLLM, Ollama, OpenAI, Anthropic

Shared resources (all containers):
  ┌──────────────┐  ┌──────────────────────┐  ┌──────────────┐
  │  Redis :6379 │  │  Local filesystem    │  │  SQLite file │
  │  (Celery)    │  │  ./data/storage/     │  │  (metadata)  │
  └──────────────┘  └──────────────────────┘  └──────────────┘
```

---

## Data Flow

### Option A: Audio Upload → Summary

```
POST /meetings/{id}/audio
  → Store audio to ./data/storage/meetings/{id}/audio/{filename}
  → Create Transcript row (audio_ref set, raw_ref = null)
  → Create Task row (status = pending)
  → celery_app.send_task("run_stt", [task_id, transcript_id, audio_ref, language, stt_url?])
  → Return {task_id, transcript_id}

[Celery worker: run_stt]
  → Task.status = running
  → HTTP POST stt_service/transcribe (sends audio bytes)
  → stt_service returns {text, duration_seconds, language, segments}
  → Store transcript text to ./data/storage/meetings/{id}/transcripts/raw.txt
  → Update Transcript.raw_ref
  → Task.status = done
```

### Option B: Direct Transcript Input → Summary (skip STT)

```
POST /meetings/{id}/transcript  {"text": "...", "language": "zh"}
  → Store text to raw.txt AND corrected.txt
  → Create Transcript row with both refs set
  → Return TranscriptResponse immediately (no task queued)
```

### Correction → Summary (common path)

```
POST /meetings/{id}/correct
  → Read Transcript.raw_ref
  → Create Task row (status = pending)
  → celery_app.send_task("run_correction", [..., llm_base_url?, llm_model?, llm_api_key?])

[Celery worker: run_correction]
  → Apply dictionary substitutions (longest-match, single-pass)
  → Call LLM with corrected text + dictionary hints
  → Store result to ./data/storage/meetings/{id}/transcripts/corrected.txt
  → Update Transcript.corrected_ref → Task.status = done

POST /meetings/{id}/summarize
  → Read Transcript (corrected_ref if available, else raw_ref)
  → celery_app.send_task("run_summary", [..., llm_base_url?, llm_model?, llm_api_key?])

[Celery worker: run_summary]
  → Resolve system prompt: custom_system_prompt > prompt_id (DB) > scene template
  → Build MeetingContext from participants, topics, date
  → Call LLM → strip <think>...</think> → store Summary row
  → Task.status = done
```

### Task Status Tracking

```
Client polls GET /tasks/{id}    → DB lookup → return TaskResponse
            OR
Client opens GET /tasks/{id}/stream (SSE)
  → StreamingResponse polls DB every 2s
  → Yields SSE event on each status change
  → Closes stream when status is done / failed / cancelled
```

---

## Abstraction Layers

Every external dependency has a base class that can be swapped without touching callers.

| Layer | Base class | Current implementation | Swap to |
|-------|-----------|----------------------|---------|
| LLM | `core/llm/base.py::BaseLLM` | `LiteLLMClient` (OpenAI-compatible, Ollama, Anthropic) | Any provider via LiteLLM |
| STT | `core/stt/base.py::BaseSTT` | `FasterWhisperSTT` (local) / `HTTPSTTClient` (Docker) | NVIDIA Riva, OpenAI Whisper API |
| Storage | `core/storage/base.py::BaseStorage` | `LocalStorage` (filesystem) | S3, GCS, Azure Blob |
| Correction | `core/correction/corrector.py` | Dictionary + LiteLLM pipeline | Any BaseLLM |

---

## Database Schema

All primary keys are `uuid.UUID`. SQLite in development, PostgreSQL in production.

```
meetings
  id            UUID PK
  title         TEXT
  date          DATETIME
  language      TEXT
  created_at    DATETIME

transcripts
  id                UUID PK
  meeting_id        UUID FK → meetings.id
  audio_ref         TEXT (storage key — null if transcript was typed directly)
  raw_ref           TEXT (storage key, set by STT worker or direct input)
  corrected_ref     TEXT (storage key, set by correction worker or direct input)
  language          TEXT
  duration_seconds  FLOAT (null if transcript was typed directly)
  created_at        DATETIME

summaries
  id                 UUID PK
  meeting_id         UUID FK → meetings.id (null for aggregations)
  transcript_id      UUID
  content            TEXT (full summary Markdown)
  content_ref        TEXT (storage key, optional)
  is_aggregated      BOOLEAN
  source_meeting_ids TEXT (JSON array of UUID strings, for aggregations)
  created_at         DATETIME

tasks
  id              UUID PK
  meeting_id      UUID FK → meetings.id
  task_type       ENUM (stt, correction, summary, aggregation)
  status          ENUM (pending, running, done, failed, cancelled)
  celery_task_id  TEXT (Celery result ID, for revoke)
  input_ref       TEXT (storage key)
  output_ref      TEXT (storage key or summary UUID)
  error           TEXT
  created_at      DATETIME

system_prompts
  id             UUID PK
  name           TEXT
  scene          ENUM (weekly_standup, project_review, client_interview, general, custom)
  template       TEXT (system prompt text)
  is_builtin     BOOLEAN
  created_at     DATETIME
```

---

## Storage Layout

Files are stored on the local filesystem at `LOCAL_STORAGE_PATH` (default `./data/storage/`).
In Docker, `./data/` is mounted as a volume so files persist across container restarts and rebuilds.

```
data/storage/
├── meetings/
│   └── {meeting_id}/
│       ├── audio/
│       │   └── {filename}              ← original uploaded audio
│       ├── transcripts/
│       │   ├── raw.txt                 ← STT output or direct input
│       │   └── corrected.txt           ← LLM-corrected or direct input
│       └── summary.md                  ← summary content
└── aggregations/
    └── meetings_{id1}_{id2}_...md      ← cross-meeting aggregation
```

The gateway mounts this directory at `/storage`, so files are accessible directly:
```
GET http://localhost:8000/storage/meetings/{id}/audio/{filename}
```

---

## GPU Acceleration (STT)

The `stt_service` runs faster-whisper on GPU when available.

**Requirements:**
- NVIDIA GPU with CUDA 12.2+ driver
- NVIDIA Container Toolkit installed on the host
- `docker-compose.yml` includes `deploy.resources.reservations.devices` for the `stt_service`

**Configuration (`.env`):**
```env
STT_DEVICE=cuda
STT_COMPUTE_TYPE=float16    # recommended for Ampere+ GPUs (RTX 30xx/40xx)
```

**Base image:** `nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04` — compatible with any CUDA driver ≥ 12.2.

**Model cache:** The HuggingFace model cache (`~/.cache/huggingface`) is mounted into the container via `docker-compose.override.yml` so the model is only downloaded once.

Only the `stt_service` needs GPU access. All other containers (`gateway`, `task_worker`, `redis`) remain unchanged.

---

## Upgrade Paths

### SQLite → PostgreSQL

Change `DATABASE_URL` in `.env`:
```env
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/meeting_assistant
```

Add `asyncpg` to dependencies. No code changes.

### Local Storage → S3 / GCS

Implement `core/storage/base.py::BaseStorage`:

```python
class S3Storage(BaseStorage):
    def upload(self, key, data, content_type): ...
    def download(self, key): ...
    def delete(self, key): ...
    def get_url(self, key, expires_seconds=3600): ...
    def exists(self, key): ...
```

Update `get_storage()` in `core/storage/__init__.py` to return the new backend.

### STT → External API (e.g. NVIDIA Riva)

Implement `core/stt/base.py::BaseSTT` and update `services/gateway/dependencies.py::get_stt()`.

### Docker Compose → Kubernetes

Each service in `docker-compose.yml` maps 1:1 to a Kubernetes `Deployment`:

| Docker service | K8s notes |
|----------------|-----------|
| `gateway` | Standard Deployment |
| `task_worker` | Scale replicas horizontally |
| `stt_service` | 1 replica, GPU node selector required |
| `redis` | Use managed Redis (ElastiCache, Cloud Memorystore) |
| SQLite | Use managed PostgreSQL |
| Local storage | Use S3 / GCS with the new storage backend |

---

## Correction Pipeline Detail

```
Input text
    │
    ▼ Stage 1: CorrectionDictionary.apply()
    │   - Sort all entries by key length (longest first)
    │   - Compile into single regex: pattern1|pattern2|...
    │   - Single-pass substitution (replaced text is never re-scanned)
    │
    ▼ Stage 2: LLM correction
    │   - System prompt includes dictionary as a hint: "- 吉他 → GitHub"
    │   - LLM handles long-tail errors not in the dictionary
    │   - <think>...</think> blocks stripped from response
    │
    ▼ Corrected text
```

The single-pass regex ensures that if "AI模型" is in the dictionary, it won't be broken into "AI" and "模型" by a shorter entry.

---

## Why Celery (not asyncio background tasks)?

FastAPI's `BackgroundTasks` runs in the same process and dies with the server. Celery tasks:
- Persist across server restarts
- Can be cancelled via `revoke`
- Are retryable
- Can be inspected and monitored
- Scale independently (add more task_worker replicas)

The trade-off is operational complexity (Redis required). For a simpler deployment, `BackgroundTasks` or `asyncio.create_task` would be sufficient if durability is not needed.
