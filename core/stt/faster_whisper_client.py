from core.stt.base import BaseSTT, STTResult, TranscriptSegment
from core.exceptions import STTError


class FasterWhisperSTT(BaseSTT):
    """
    STT using faster-whisper. Supports Chinese-English mixed audio.
    Model sizes: tiny, base, small, medium, large-v2, large-v3
    """

    def __init__(self, model_size: str = "large-v3", device: str = "cpu", compute_type: str = "int8") -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None  # Lazy load to avoid slow startup

    def _load_model(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
                self._model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                )
            except Exception as e:
                raise STTError(f"Failed to load Whisper model '{self.model_size}': {e}") from e
        return self._model

    def transcribe(self, audio_path: str, language: str = "zh") -> STTResult:
        model = self._load_model()
        try:
            segments_iter, info = model.transcribe(
                audio_path,
                language=language,
                beam_size=5,
                vad_filter=True,          # Remove silence
                vad_parameters={"min_silence_duration_ms": 500},
            )
            segments = []
            full_text_parts = []
            for seg in segments_iter:
                segments.append(TranscriptSegment(
                    start=seg.start,
                    end=seg.end,
                    text=seg.text.strip(),
                    confidence=seg.avg_logprob,
                ))
                full_text_parts.append(seg.text.strip())

            return STTResult(
                text=" ".join(full_text_parts),
                segments=segments,
                language=info.language,
                duration_seconds=info.duration,
            )
        except Exception as e:
            raise STTError(f"Transcription failed for '{audio_path}': {e}") from e

    @classmethod
    def from_settings(cls) -> "FasterWhisperSTT":
        from core.config import settings
        return cls(
            model_size=settings.stt_model,
            device=settings.stt_device,
            compute_type=settings.stt_compute_type,
        )
