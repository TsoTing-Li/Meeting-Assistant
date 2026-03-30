from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class TranscriptSegment:
    start: float   # seconds
    end: float     # seconds
    text: str
    confidence: float = 0.0


@dataclass
class STTResult:
    text: str                              # Full concatenated transcript
    segments: list[TranscriptSegment] = field(default_factory=list)
    language: str = "zh"
    duration_seconds: float = 0.0


class BaseSTT(ABC):
    """Abstract STT interface. Swap implementations (Whisper, NVIDIA Riva, etc.)."""

    @abstractmethod
    def transcribe(self, audio_path: str, language: str = "zh") -> STTResult:
        """Transcribe audio file at audio_path."""
