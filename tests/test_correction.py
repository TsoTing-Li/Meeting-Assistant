import csv
import json
import tempfile
from pathlib import Path

import pytest
from core.correction.dictionary import CorrectionDictionary
from core.correction.corrector import TranscriptCorrector
from core.exceptions import CorrectionError
from tests.conftest import MockLLM


# ── Dictionary tests ──────────────────────────────────────────────────────────

def test_add_and_apply(empty_dictionary):
    empty_dictionary.add("吉他", "GitHub")
    result = empty_dictionary.apply("我使用吉他管理程式碼")
    assert "GitHub" in result
    assert "吉他" not in result


def test_apply_multiple_entries(sample_dictionary):
    text = "吉他上有個吉他的project，由阿里巴巴提供"
    result = sample_dictionary.apply(text)
    assert "GitHub" in result
    assert "Alibaba" in result


def test_longest_match_first():
    d = CorrectionDictionary()
    d.add("AI", "人工智慧")
    d.add("AI模型", "AI Model")
    result = d.apply("我們在討論AI模型的問題")
    assert "AI Model" in result


def test_remove_entry(sample_dictionary):
    sample_dictionary.remove("吉他")
    result = sample_dictionary.apply("吉他")
    assert "GitHub" not in result
    assert "吉他" in result


def test_remove_nonexistent_does_not_raise(empty_dictionary):
    empty_dictionary.remove("不存在的詞")  # Should not raise


def test_len(sample_dictionary):
    assert len(sample_dictionary) == 3


def test_contains(sample_dictionary):
    assert "吉他" in sample_dictionary
    assert "不存在" not in sample_dictionary


def test_to_prompt_hint(sample_dictionary):
    hint = sample_dictionary.to_prompt_hint()
    assert "→" in hint
    assert "吉他" in hint


def test_empty_dictionary_prompt_hint(empty_dictionary):
    assert empty_dictionary.to_prompt_hint() == ""


def test_load_csv(tmp_path):
    csv_file = tmp_path / "dict.csv"
    csv_file.write_text("wrong,correct\n錯誤A,正確A\n錯誤B,正確B\n", encoding="utf-8")
    d = CorrectionDictionary()
    d.load_csv(csv_file)
    assert len(d) == 2
    assert d.apply("錯誤A 錯誤B") == "正確A 正確B"


def test_load_csv_with_bom(tmp_path):
    csv_file = tmp_path / "dict_bom.csv"
    # Write with BOM (common in Windows) — utf-8-sig adds the BOM automatically
    csv_file.write_bytes(
        "wrong,correct\n阿里巴巴,Alibaba\n".encode("utf-8-sig")
    )
    d = CorrectionDictionary()
    d.load_csv(csv_file)
    assert "阿里巴巴" in d


def test_load_json(tmp_path):
    json_file = tmp_path / "dict.json"
    json_file.write_text(json.dumps({"錯誤詞": "正確詞", "A": "B"}), encoding="utf-8")
    d = CorrectionDictionary()
    d.load_json(json_file)
    assert len(d) == 2
    assert d.apply("錯誤詞 A") == "正確詞 B"


# ── Corrector tests ───────────────────────────────────────────────────────────

def test_corrector_calls_llm(mock_llm, sample_dictionary):
    mock_llm.response = "校正後的逐字稿"
    corrector = TranscriptCorrector(llm=mock_llm, dictionary=sample_dictionary)
    result = corrector.correct("原始逐字稿 吉他")
    assert result == "校正後的逐字稿"
    assert len(mock_llm.calls) == 1


def test_corrector_applies_dictionary_before_llm(sample_dictionary):
    received_texts = []

    class CaptureLLM(MockLLM):
        def complete(self, messages, **kwargs):
            received_texts.append(messages[-1].content)
            return super().complete(messages, **kwargs)

    llm = CaptureLLM()
    corrector = TranscriptCorrector(llm=llm, dictionary=sample_dictionary)
    corrector.correct("吉他 是個 開源平台")
    # Dictionary should have replaced 吉他 → GitHub before LLM sees it
    assert any("GitHub" in t for t in received_texts)


def test_corrector_empty_transcript_returns_unchanged(mock_llm):
    corrector = TranscriptCorrector(llm=mock_llm)
    result = corrector.correct("")
    assert result == ""
    assert len(mock_llm.calls) == 0


def test_corrector_whitespace_transcript_returns_unchanged(mock_llm):
    corrector = TranscriptCorrector(llm=mock_llm)
    result = corrector.correct("   ")
    assert result == "   "


def test_corrector_llm_error_raises_correction_error(sample_dictionary):
    from core.exceptions import CorrectionError, LLMError

    class FailingLLM(MockLLM):
        def complete(self, messages, **kwargs):
            raise LLMError("connection timeout")

    corrector = TranscriptCorrector(llm=FailingLLM(), dictionary=sample_dictionary)
    with pytest.raises(CorrectionError):
        corrector.correct("some transcript")


def test_corrector_without_dictionary(mock_llm):
    mock_llm.response = "corrected"
    corrector = TranscriptCorrector(llm=mock_llm)
    result = corrector.correct("raw transcript")
    assert result == "corrected"
