import uuid
import tempfile
import os
from typing import Optional

from core.config import settings
from core.database import get_session
from core.models.task import Task, TaskStatus
from core.models.transcript import Transcript
from core.stt.http_client import HTTPSTTClient
from core.storage import get_storage
from services.task_worker.celery_app import celery_app


@celery_app.task(name="services.task_worker.tasks.stt.run_stt", bind=True)
def run_stt(
    self,
    task_id: str,
    transcript_id: str,
    audio_key: str,
    language: str = "zh",
    stt_url: Optional[str] = None,
):
    """Download audio from storage, run STT, store raw transcript."""
    _task_id = uuid.UUID(task_id)
    _transcript_id = uuid.UUID(transcript_id)

    storage = get_storage()
    _stt_url = stt_url or settings.stt_service_url
    stt = HTTPSTTClient(base_url=_stt_url)

    with get_session() as session:
        task = session.get(Task, _task_id)
        task.status = TaskStatus.RUNNING

    try:
        audio_data = storage.download(audio_key)

        suffix = os.path.splitext(audio_key)[1] or ".audio"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name

        try:
            result = stt.transcribe(tmp_path, language=language)
        finally:
            os.unlink(tmp_path)

        # Extract meeting_id from audio_key: meetings/{uuid}/audio/filename
        parts = audio_key.split("/")
        meeting_id = parts[1] if len(parts) > 1 else "unknown"
        raw_key = f"meetings/{meeting_id}/transcripts/raw.txt"
        storage.upload(raw_key, result.text.encode("utf-8"), "text/plain")

        with get_session() as session:
            transcript = session.get(Transcript, _transcript_id)
            transcript.raw_ref = raw_key
            transcript.language = result.language
            transcript.duration_seconds = result.duration_seconds

            task = session.get(Task, _task_id)
            task.status = TaskStatus.DONE
            task.output_ref = raw_key

    except Exception as e:
        with get_session() as session:
            task = session.get(Task, _task_id)
            task.status = TaskStatus.FAILED
            task.error = str(e)
        raise
