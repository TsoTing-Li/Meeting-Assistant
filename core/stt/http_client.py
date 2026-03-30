import httpx
from pathlib import Path

from core.stt.base import BaseSTT, STTResult, TranscriptSegment
from core.exceptions import STTError


class HTTPSTTClient(BaseSTT):
    """
    STT client that delegates to a remote stt-service via HTTP.
    Used by gateway and task_worker so they don't need faster-whisper installed.
    """

    def __init__(
        self,
        base_url: str,
        connect_timeout: float = 10.0,
        write_timeout: float = 120.0,
        read_timeout: float = 7200.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(
            connect=connect_timeout,
            write=write_timeout,   # audio upload
            read=read_timeout,     # wait for transcription (CPU can be slow)
            pool=10.0,
        )

    def transcribe(self, audio_path: str, language: str = "zh") -> STTResult:
        path = Path(audio_path)
        if not path.exists():
            raise STTError(f"Audio file not found: {audio_path}")

        try:
            with open(audio_path, "rb") as f:
                audio_bytes = f.read()

            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(
                    f"{self.base_url}/transcribe",
                    files={"audio": (path.name, audio_bytes, "audio/mpeg")},
                    data={"language": language},
                )
                response.raise_for_status()

            data = response.json()
            return STTResult(
                text=data["text"],
                segments=[
                    TranscriptSegment(
                        start=s["start"],
                        end=s["end"],
                        text=s["text"],
                        confidence=s["confidence"],
                    )
                    for s in data.get("segments", [])
                ],
                language=data["language"],
                duration_seconds=data["duration_seconds"],
            )
        except httpx.HTTPStatusError as e:
            raise STTError(f"STT service error: {e.response.status_code} {e.response.text}") from e
        except httpx.RequestError as e:
            raise STTError(f"STT service unreachable: {e}") from e

    @classmethod
    def from_settings(cls) -> "HTTPSTTClient":
        from core.config import settings
        return cls(
            base_url=settings.stt_service_url,
            connect_timeout=settings.stt_connect_timeout,
            write_timeout=settings.stt_write_timeout,
            read_timeout=settings.stt_read_timeout,
        )
