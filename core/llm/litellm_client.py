import re
import litellm
from litellm import completion

from core.llm.base import BaseLLM, LLMMessage, LLMResponse
from core.exceptions import LLMError

_THINK_TAG_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_think_tags(text: str) -> str:
    return _THINK_TAG_RE.sub("", text).strip()


# Known LiteLLM provider prefixes — anything else with an api_base gets openai/ prepended
_KNOWN_PROVIDERS = {
    "openai", "ollama", "anthropic", "azure", "huggingface", "cohere",
    "replicate", "together_ai", "openrouter", "vertex_ai", "palm",
    "ai21", "baseten", "vllm", "hosted_vllm", "deepinfra", "perplexity",
    "anyscale", "mistral", "groq", "bedrock", "sagemaker", "petals",
}


def _resolve_model(model: str, api_base: str) -> str:
    """
    If api_base is set and the model has no recognized provider prefix,
    prepend 'openai/' so LiteLLM routes to the OpenAI-compatible endpoint.
    """
    if not api_base:
        return model
    prefix = model.split("/")[0]
    if prefix not in _KNOWN_PROVIDERS:
        return f"openai/{model}"
    return model


class LiteLLMClient(BaseLLM):
    """
    LLM client using LiteLLM. Supports:
    - OpenAI: model="gpt-4o", api_key=...
    - Ollama: model="ollama/llama3.2", api_base="http://localhost:11434"
    - vLLM / any OpenAI-compatible: model="openai/Qwen/Qwen3-4B", api_base="http://host/v1"
    - Anthropic: model="anthropic/claude-sonnet-4-6", api_key=...

    If api_base is set and model has no recognized provider prefix,
    'openai/' is prepended automatically.
    """

    def __init__(
        self,
        model: str,
        api_key: str = "",
        api_base: str = "",
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> None:
        self.model = _resolve_model(model, api_base)
        self.api_key = api_key or None
        self.api_base = api_base or None
        self.temperature = temperature
        self.max_tokens = max_tokens
        litellm.drop_params = True

    def complete(self, messages: list[LLMMessage], **kwargs) -> LLMResponse:
        try:
            call_kwargs: dict = {
                "model": self.model,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "temperature": kwargs.get("temperature", self.temperature),
                "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            }
            if self.api_key:
                call_kwargs["api_key"] = self.api_key
            if self.api_base:
                call_kwargs["api_base"] = self.api_base
            response = completion(**call_kwargs)
            raw_content = response.choices[0].message.content or ""
            return LLMResponse(
                content=_strip_think_tags(raw_content),
                model=response.model or self.model,
                input_tokens=response.usage.prompt_tokens if response.usage else 0,
                output_tokens=response.usage.completion_tokens if response.usage else 0,
            )
        except Exception as e:
            raise LLMError(f"LLM call failed: {e}") from e

    @classmethod
    def from_settings(cls) -> "LiteLLMClient":
        from core.config import settings
        return cls(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            api_base=settings.llm_base_url,
        )
