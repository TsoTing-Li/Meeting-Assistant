import pytest
from core.summary.templates import (
    MeetingContext, PromptTemplate, BUILTIN_TEMPLATES, get_template
)
from core.summary.summarizer import MeetingSummarizer
from core.exceptions import PromptValidationError, SummaryError
from tests.conftest import MockLLM


# ── MeetingContext tests ──────────────────────────────────────────────────────

def test_context_render_block():
    ctx = MeetingContext(
        meeting_type="週會",
        date="2026-03-20",
        participants=["Alice", "Bob"],
        topics=["進度更新", "問題討論"],
    )
    block = ctx.render_context_block()
    assert "Alice" in block
    assert "Bob" in block
    assert "進度更新" in block
    assert "2026-03-20" in block


def test_context_validate_passes_with_all_fields():
    ctx = MeetingContext(
        meeting_type="general",
        date="2026-01-01",
        participants=["Alice"],
        topics=["Topic"],
    )
    ctx.validate()  # Should not raise


def test_context_validate_passes_with_optional_fields_missing():
    # participants and topics are now optional — validate() only requires date
    ctx = MeetingContext(meeting_type="general", date="2026-01-01", participants=[], topics=[])
    ctx.validate()  # Should not raise


def test_context_validate_fails_missing_date():
    ctx = MeetingContext(meeting_type="general", date="", participants=["A"], topics=["T"])
    with pytest.raises(PromptValidationError) as exc_info:
        ctx.validate()
    assert "date" in str(exc_info.value)


def test_context_validate_fails_empty_date_only():
    # Only date is required — missing meeting_type alone does not raise
    ctx = MeetingContext(meeting_type="", date="2026-01-01", participants=[], topics=[])
    ctx.validate()  # Should not raise


def test_context_extra_fields():
    ctx = MeetingContext(
        meeting_type="general",
        date="2026-01-01",
        participants=["A"],
        topics=["T"],
        extra={"location": "Conference Room A"},
    )
    block = ctx.render_context_block()
    assert "Conference Room A" in block


# ── Template tests ────────────────────────────────────────────────────────────

def test_builtin_templates_exist():
    for scene in ["weekly_standup", "project_review", "client_interview", "general"]:
        assert scene in BUILTIN_TEMPLATES


def test_get_template_returns_template():
    t = get_template("general")
    assert isinstance(t, PromptTemplate)
    assert t.scene == "general"


def test_get_template_invalid_scene():
    with pytest.raises(ValueError, match="Unknown scene"):
        get_template("nonexistent_scene")


def test_all_builtin_templates_have_required_sections():
    for scene, template in BUILTIN_TEMPLATES.items():
        assert "決議" in template.system_prompt or "決策" in template.system_prompt or "行動" in template.system_prompt, \
            f"Template '{scene}' should contain action/decision section"


# ── Summarizer tests ──────────────────────────────────────────────────────────

@pytest.fixture
def valid_context():
    return MeetingContext(
        meeting_type="weekly_standup",
        date="2026-03-20",
        participants=["Alice", "Bob", "Charlie"],
        topics=["Sprint 進度", "Blocker 討論"],
    )


def test_summarizer_calls_llm(mock_llm, valid_context):
    mock_llm.response = "## 會議摘要\n本次會議..."
    summarizer = MeetingSummarizer(llm=mock_llm)
    template = get_template("weekly_standup")
    result = summarizer.summarize("逐字稿內容", template, valid_context)
    assert result == "## 會議摘要\n本次會議..."
    assert len(mock_llm.calls) == 1


def test_summarizer_includes_context_in_prompt(valid_context):
    received = []

    class CaptureLLM(MockLLM):
        def complete(self, messages, **kwargs):
            received.append(messages)
            return super().complete(messages, **kwargs)

    llm = CaptureLLM()
    summarizer = MeetingSummarizer(llm=llm)
    summarizer.summarize("transcript", get_template("general"), valid_context)

    user_msg = received[0][-1].content
    assert "Alice" in user_msg
    assert "Sprint 進度" in user_msg
    assert "2026-03-20" in user_msg


def test_summarizer_validates_context(mock_llm):
    invalid_ctx = MeetingContext(meeting_type="", date="", participants=[], topics=[])
    summarizer = MeetingSummarizer(llm=mock_llm)
    with pytest.raises(PromptValidationError):
        summarizer.summarize("transcript", get_template("general"), invalid_ctx)


def test_summarizer_llm_error_raises_summary_error(valid_context):
    from core.exceptions import SummaryError, LLMError

    class FailingLLM(MockLLM):
        def complete(self, messages, **kwargs):
            raise LLMError("timeout")

    summarizer = MeetingSummarizer(llm=FailingLLM())
    with pytest.raises(SummaryError):
        summarizer.summarize("transcript", get_template("general"), valid_context)
