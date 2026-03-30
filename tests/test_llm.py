import pytest
from core.llm.base import LLMMessage, LLMResponse
from core.exceptions import LLMError
from tests.conftest import MockLLM


def test_complete_returns_response(mock_llm):
    messages = [
        LLMMessage(role="system", content="You are a helper."),
        LLMMessage(role="user", content="Hello"),
    ]
    response = mock_llm.complete(messages)
    assert isinstance(response, LLMResponse)
    assert response.content == "mock LLM response"


def test_complete_records_calls(mock_llm):
    messages = [LLMMessage(role="user", content="test")]
    mock_llm.complete(messages)
    assert len(mock_llm.calls) == 1
    assert mock_llm.calls[0] == messages


def test_chat_convenience_method(mock_llm):
    result = mock_llm.chat("system prompt", "user message")
    assert result == "mock LLM response"
    assert len(mock_llm.calls) == 1
    # Verify chat builds correct message structure
    assert mock_llm.calls[0][0].role == "system"
    assert mock_llm.calls[0][1].role == "user"


def test_custom_response(mock_llm):
    mock_llm.response = "custom response"
    result = mock_llm.chat("system", "user")
    assert result == "custom response"


def test_multiple_calls_recorded(mock_llm):
    mock_llm.complete([LLMMessage(role="user", content="first")])
    mock_llm.complete([LLMMessage(role="user", content="second")])
    assert len(mock_llm.calls) == 2
