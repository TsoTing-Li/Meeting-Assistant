# Usage Guide

Two ways to use Meeting Assistant: the **CLI** (file-based, standalone) and the **Web UI / REST API** (Docker, async pipeline).

---

## CLI

The CLI requires no database. Each command reads input files and writes output to stdout or a file. STT and LLM endpoints are provided at runtime.

### Installation

```bash
pip install -e ".[cli]"
```

### `transcribe` — Audio → Transcript

```bash
meeting-assistant transcribe <audio-file> --stt-url <url> [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--stt-url` | required | STT service URL, e.g. `http://localhost:8080` |
| `--language`, `-l` | `zh` | Audio language (`zh` / `en`) |
| `--output`, `-o` | stdout | Save transcript to file |

**Examples:**

```bash
# Print to stdout
meeting-assistant transcribe recording.mp3 --stt-url http://localhost:8080

# Save to file, English audio
meeting-assistant transcribe interview.m4a \
  --stt-url http://localhost:8080 \
  --language en \
  --output transcript.txt
```

---

### `correct` — Transcript Correction

Applies a correction dictionary (deterministic) then LLM contextual repair.

```bash
meeting-assistant correct <transcript-file> --llm-url <url> --model <model> [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--llm-url` | required | LLM base URL, e.g. `http://localhost:8002/v1` |
| `--model` | required | Model name, e.g. `openai/Qwen/Qwen3-4B` |
| `--api-key` | `no-key` | LLM API key (use `no-key` for local servers) |
| `--terms` | — | Inline substitutions: `wrong=correct,foo=bar` |
| `--dict`, `-d` | — | CSV or JSON dictionary file |
| `--output`, `-o` | stdout | Save corrected transcript to file |

**Examples:**

```bash
# Inline substitutions
meeting-assistant correct transcript.txt \
  --llm-url http://localhost:8002/v1 \
  --model openai/Qwen/Qwen3-4B \
  --terms "阿里巴巴=Alibaba,吉他=GitHub,開鍵=Open Key"

# From a CSV dictionary file
meeting-assistant correct transcript.txt \
  --llm-url http://localhost:8002/v1 \
  --model openai/Qwen/Qwen3-4B \
  --dict ./dict.csv \
  --output corrected.txt
```

**Dictionary formats:**

CSV (`dict.csv`):
```csv
wrong,correct
吉他,GitHub
阿里巴巴,Alibaba
克勞德,Claude
```

JSON (`dict.json`):
```json
{
  "吉他": "GitHub",
  "阿里巴巴": "Alibaba"
}
```

---

### `summarize` — Generate Summary

```bash
meeting-assistant summarize <transcript-file> --llm-url <url> --model <model> [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--llm-url` | required | LLM base URL |
| `--model` | required | Model name |
| `--api-key` | `no-key` | LLM API key |
| `--scene`, `-s` | `general` | Built-in scene: `general` / `weekly_standup` / `project_review` / `client_interview` |
| `--prompt-file`, `-p` | — | Path to a `.txt` file with a custom system prompt |
| `--date` | today | Meeting date `YYYY-MM-DD` |
| `--participants` | — | Comma-separated names |
| `--topics` | — | Comma-separated topics |
| `--output`, `-o` | stdout | Save summary to file |

**Built-in scenes:**

| Scene | Contents |
|-------|----------|
| `general` | Summary, discussion points, decisions, action items, open issues |
| `weekly_standup` | Weekly progress, decisions, action items, blockers |
| `project_review` | Project status, risks, decisions, action items |
| `client_interview` | Client needs, pain points, discussion points, next steps |

**Example:**

```bash
meeting-assistant summarize corrected.txt \
  --llm-url http://localhost:8002/v1 \
  --model openai/Qwen/Qwen3-4B \
  --scene weekly_standup \
  --date 2026-03-20 \
  --participants "Alice,Bob,Charlie" \
  --topics "Sprint 進度,Blocker,下週計畫" \
  --output summary.md
```

---

### `aggregate` — Cross-Meeting Report

```bash
meeting-assistant aggregate <summary1> <summary2> [...] --llm-url <url> --model <model> [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--llm-url` | required | LLM base URL |
| `--model` | required | Model name |
| `--api-key` | `no-key` | LLM API key |
| `--labels` | file stems | Comma-separated labels for each summary |
| `--output`, `-o` | stdout | Save report to file |

---

### Full CLI Pipeline

```bash
STT_URL=http://localhost:8080
LLM_URL=http://localhost:8002/v1
MODEL=openai/Qwen/Qwen3-4B

meeting-assistant transcribe recording.mp3 --stt-url $STT_URL --output transcript.txt
meeting-assistant correct transcript.txt --llm-url $LLM_URL --model $MODEL --dict dict.csv --output corrected.txt
meeting-assistant summarize corrected.txt --llm-url $LLM_URL --model $MODEL --scene weekly_standup --output summary.md
```

---

## Web UI

Open **http://localhost:8000** after starting Docker Compose.

The UI has four tabs:

**Meetings**
- Create a meeting (title and date are optional — defaults to today)
- **Upload audio** → STT task queued, status shown in real time (SSE)
- **Or input transcript directly** → skips STT, goes straight to summarize
- Run correction with optional inline terms
- Run summarize with scene selection and custom system prompt
- Download any summary as `.md` file (filename: `{title}_{date}.md`)
- View all summaries for a meeting; delete individual summaries
- Delete meeting (cascades to transcript, summaries, tasks, storage)

**Prompts**
- View all built-in prompt scenes
- Create, edit, and delete custom prompt templates
- Custom prompts appear in the summarize scene selector

**Aggregations**
- Select two or more meetings to aggregate their summaries
- Download aggregation result as `.md` file
- View all past aggregation reports

**Settings**
- Shows current effective config (server defaults + any localStorage overrides) from `GET /info`
- Optional per-request overrides stored in `localStorage`:
  - STT service URL (e.g. point to a remote GPU machine) — test with built-in probe
  - LLM Base URL, Model, API Key — probe fetches available models from `GET /v1/models` and populates autocomplete
- Overrides are shown with a "覆蓋中" badge; leave blank to use server defaults
- Settings are validated (probe) before saving; connection must succeed to persist

---

## REST API

Full interactive docs at **http://localhost:8000/docs**.

### Server Info

```bash
# Get server-side config (STT model, LLM model, etc.)
curl http://localhost:8000/info
# → {"stt_model": "large-v3", "stt_service_url": "http://stt_service:8080", "llm_model": "...", "llm_base_url": "..."}
```

### Meetings

```bash
# Create
curl -X POST http://localhost:8000/meetings \
  -H "Content-Type: application/json" \
  -d '{"title": "Sprint Review", "date": "2026-03-20", "language": "zh"}'

# List
curl http://localhost:8000/meetings

# Get / Update / Delete
curl http://localhost:8000/meetings/<uuid>
curl -X PUT http://localhost:8000/meetings/<uuid> -H "Content-Type: application/json" -d '{"title": "New Title"}'
curl -X DELETE http://localhost:8000/meetings/<uuid>
```

### Audio Upload & STT

```bash
# Upload audio — queues STT task
# Optional: stt_url query param overrides server-default STT endpoint
curl -X POST "http://localhost:8000/meetings/<uuid>/audio?language=zh&stt_url=http://gpu-machine:8080" \
  -F "audio=@./recording.mp3"
# → {"task_id": "uuid", "transcript_id": "uuid", "status": "pending"}

# Poll or stream task status
curl http://localhost:8000/tasks/<task_id>
curl -N http://localhost:8000/tasks/<task_id>/stream
```

### Transcript

```bash
# Create transcript from text directly (skip STT)
curl -X POST http://localhost:8000/meetings/<uuid>/transcript \
  -H "Content-Type: application/json" \
  -d '{"text": "逐字稿內容...", "language": "zh"}'
# → TranscriptResponse (raw and corrected both set to the provided text)

# Get latest transcript
curl http://localhost:8000/meetings/<uuid>/transcript

# Manual edit (override corrected text)
curl -X PUT http://localhost:8000/meetings/<uuid>/transcript \
  -H "Content-Type: application/json" \
  -d '{"corrected": "手動修正後的逐字稿..."}'
```

### Correction

```bash
# Queue correction task
# Optional: llm_base_url / llm_model / llm_api_key override server defaults
curl -X POST http://localhost:8000/meetings/<uuid>/correct \
  -H "Content-Type: application/json" \
  -d '{
    "terms": {"吉他": "GitHub", "阿里巴巴": "Alibaba"},
    "llm_base_url": "http://gpu-machine:8002/v1",
    "llm_model": "openai/Qwen3-4B"
  }'
```

### Summary

```bash
# Queue summary task
# Optional: llm_base_url / llm_model / llm_api_key override server defaults
curl -X POST http://localhost:8000/meetings/<uuid>/summarize \
  -H "Content-Type: application/json" \
  -d '{
    "scene": "weekly_standup",
    "participants": ["Alice", "Bob"],
    "topics": ["進度", "Blocker"]
  }'

# Get latest summary / list all summaries / delete
curl http://localhost:8000/meetings/<uuid>/summary
curl http://localhost:8000/meetings/<uuid>/summaries
curl -X DELETE http://localhost:8000/meetings/<uuid>/summaries/<summary_uuid>
```

### Aggregation

```bash
# Queue cross-meeting aggregation
# Optional: llm_base_url / llm_model / llm_api_key override server defaults
curl -X POST http://localhost:8000/documents/aggregate \
  -H "Content-Type: application/json" \
  -d '{
    "meeting_ids": ["uuid1", "uuid2", "uuid3"],
    "labels": ["Week1", "Week2", "Week3"]
  }'

# List / get aggregations
curl http://localhost:8000/documents/aggregations
curl http://localhost:8000/documents/aggregations/<summary_uuid>
```

### Document Generation

```bash
# Generate Markdown document (sync, returns text/plain)
curl -X POST "http://localhost:8000/documents/generate/<summary_uuid>?title=My+Report" \
  -F "assets=@./architecture.png" \
  > report.md
```

### Tasks

```bash
# List / get / cancel / stream
curl "http://localhost:8000/tasks?meeting_id=<uuid>"
curl http://localhost:8000/tasks/<task_id>
curl -X POST http://localhost:8000/tasks/<task_id>/cancel
curl -N http://localhost:8000/tasks/<task_id>/stream
```

### Custom Prompts

```bash
# List / create / update / delete
curl http://localhost:8000/prompts
curl -X POST http://localhost:8000/prompts \
  -H "Content-Type: application/json" \
  -d '{"name": "技術回顧", "system_prompt": "你是一位技術審查助手..."}'
curl -X PUT http://localhost:8000/prompts/<uuid> -H "Content-Type: application/json" -d '{"name": "新名稱"}'
curl -X DELETE http://localhost:8000/prompts/<uuid>
```
