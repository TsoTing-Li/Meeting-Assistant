import pytest
from core.stt.base import STTResult, TranscriptSegment
from tests.conftest import MockSTT


def test_transcribe_returns_result(mock_stt):
    result = mock_stt.transcribe("audio.mp3")
    assert isinstance(result, STTResult)
    assert isinstance(result.text, str)
    assert len(result.text) > 0


def test_transcribe_has_segments(mock_stt):
    result = mock_stt.transcribe("audio.mp3")
    assert isinstance(result.segments, list)
    assert len(result.segments) > 0


def test_segments_have_timestamps(mock_stt):
    result = mock_stt.transcribe("audio.mp3")
    for seg in result.segments:
        assert isinstance(seg, TranscriptSegment)
        assert seg.end >= seg.start
        assert isinstance(seg.text, str)


def test_transcribe_detects_language(mock_stt):
    result = mock_stt.transcribe("audio.mp3", language="zh")
    assert result.language in ("zh", "en", "ja", "ko")


def test_custom_stt_result():
    custom_result = STTResult(
        text="自訂逐字稿",
        segments=[TranscriptSegment(start=0, end=2, text="自訂逐字稿")],
        language="zh",
        duration_seconds=2.0,
    )
    stt = MockSTT(result=custom_result)
    result = stt.transcribe("audio.mp3")
    assert result.text == "自訂逐字稿"
    assert result.duration_seconds == 2.0
