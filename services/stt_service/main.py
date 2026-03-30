import tempfile
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

from core.stt.faster_whisper_client import FasterWhisperSTT
from core.stt.base import STTResult, TranscriptSegment
from core.exceptions import STTError


_stt: FasterWhisperSTT | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _stt
    _stt = FasterWhisperSTT.from_settings()
    # Eagerly load model at startup
    _stt._load_model()
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
def health():
    return {"status": "ok", "model_loaded": _stt is not None and _stt._model is not None}


@app.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(
    audio: UploadFile = File(...),
    language: str = Form(default="zh"),
):
    if _stt is None:
        raise HTTPException(status_code=503, detail="STT model not loaded")

    data = await audio.read()
    suffix = os.path.splitext(audio.filename or "audio.mp3")[1] or ".audio"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        result = _stt.transcribe(tmp_path, language=language)
    except STTError as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
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
