from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class BaseLLM(ABC):
    """Abstract LLM interface. Supports OpenAI format and Ollama via LiteLLM."""

    @abstractmethod
    def complete(self, messages: list[LLMMessage], **kwargs) -> LLMResponse:
        """Send messages to the LLM and return the response."""

    def chat(self, system_prompt: str, user_message: str, **kwargs) -> str:
        """Convenience method for single-turn chat."""
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_message),
        ]
        return self.complete(messages, **kwargs).content
