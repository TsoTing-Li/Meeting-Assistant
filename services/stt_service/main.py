import asyncio
import tempfile
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

from core.stt.faster_whisper_client import FasterWhisperSTT
from core.stt.base import STTResult, TranscriptSegment
from core.exceptions import STTError


# Pool of model instances — each handles one transcription at a time
_pool: asyncio.Queue = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool
    from core.config import settings
    _pool = asyncio.Queue()
    for _ in range(settings.stt_workers):
        instance = FasterWhisperSTT.from_settings()
        instance._load_model()
        await _pool.put(instance)
    yield


app = FastAPI(title="STT Service", version="0.1.0", lifespan=lifespan)


class SegmentResponse(BaseModel):
    start: float
    end: float
    text: str
    confidence: float


class TranscribeResponse(BaseModel):
    text: str
    segments: list[SegmentResponse]
    language: str
    duration_seconds: float


@app.get("/health")
async def health():
    loaded = _pool is not None and not _pool.empty()
    return {"status": "ok", "model_loaded": loaded}


@app.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(
    audio: UploadFile = File(...),
    language: str = Form(default="zh"),
):
    if _pool is None:
        raise HTTPException(status_code=503, detail="STT model not loaded")

    data = await audio.read()
    suffix = os.path.splitext(audio.filename or "audio.mp3")[1] or ".audio"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    # Acquire a model instance from the pool (waits if all are busy)
    stt = await _pool.get()
    try:
        result: STTResult = await asyncio.to_thread(stt.transcribe, tmp_path, language)
    except STTError as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await _pool.put(stt)  # always return instance to pool
        os.unlink(tmp_path)

    return TranscribeResponse(
        text=result.text,
        segments=[
            SegmentResponse(
                start=s.start, end=s.end, text=s.text, confidence=s.confidence
            )
            for s in result.segments
        ],
        language=result.language,
        duration_seconds=result.duration_seconds,
    )
