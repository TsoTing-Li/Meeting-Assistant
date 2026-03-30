import pytest
from core.aggregation.aggregator import MeetingAggregator, AggregationResult
from core.exceptions import AggregationError
from tests.conftest import MockLLM


SAMPLE_SUMMARIES = [
    "## 第一場\n決議：採用 React 框架\n待辦：完成 UI 設計",
    "## 第二場\n決議：採用 PostgreSQL\n待辦：設定資料庫",
    "## 第三場\n決議：部署至 AWS\n未解決：成本估算",
]


def test_aggregate_returns_result(mock_llm):
    mock_llm.response = "## 整體進展\n..."
    aggregator = MeetingAggregator(llm=mock_llm)
    result = aggregator.aggregate(SAMPLE_SUMMARIES)
    assert isinstance(result, AggregationResult)
    assert result.content == "## 整體進展\n..."
    assert result.meeting_count == 3


def test_aggregate_with_meeting_ids(mock_llm):
    aggregator = MeetingAggregator(llm=mock_llm)
    result = aggregator.aggregate(SAMPLE_SUMMARIES, meeting_ids=[1, 2, 3])
    assert result.meeting_ids == [1, 2, 3]


def test_aggregate_with_labels(mock_llm):
    received = []

    class CaptureLLM(MockLLM):
        def complete(self, messages, **kwargs):
            received.append(messages)
            return super().complete(messages, **kwargs)

    llm = CaptureLLM()
    aggregator = MeetingAggregator(llm=llm)
    labels = ["2026-01-01 週會", "2026-01-08 週會"]
    aggregator.aggregate(SAMPLE_SUMMARIES[:2], meeting_labels=labels)

    user_content = received[0][-1].content
    assert "2026-01-01 週會" in user_content
    assert "2026-01-08 週會" in user_content


def test_aggregate_empty_raises(mock_llm):
    aggregator = MeetingAggregator(llm=mock_llm)
    with pytest.raises(AggregationError, match="No summaries"):
        aggregator.aggregate([])


def test_aggregate_single_raises(mock_llm):
    aggregator = MeetingAggregator(llm=mock_llm)
    with pytest.raises(AggregationError, match="At least 2"):
        aggregator.aggregate(["only one summary"])


def test_aggregate_llm_error_raises(mock_llm):
    from core.exceptions import LLMError

    class FailingLLM(MockLLM):
        def complete(self, messages, **kwargs):
            raise LLMError("connection error")

    aggregator = MeetingAggregator(llm=FailingLLM())
    with pytest.raises(AggregationError):
        aggregator.aggregate(SAMPLE_SUMMARIES)


def test_aggregate_default_labels(mock_llm):
    received = []

    class CaptureLLM(MockLLM):
        def complete(self, messages, **kwargs):
            received.append(messages)
            return super().complete(messages, **kwargs)

    aggregator = MeetingAggregator(llm=CaptureLLM())
    aggregator.aggregate(SAMPLE_SUMMARIES[:2])
    user_content = received[0][-1].content
    assert "第 1 場會議" in user_content
    assert "第 2 場會議" in user_content
