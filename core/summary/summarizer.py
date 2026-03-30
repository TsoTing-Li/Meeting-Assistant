from core.llm.base import BaseLLM
from core.summary.templates import PromptTemplate, MeetingContext
from core.exceptions import SummaryError

USER_PROMPT_TEMPLATE = """{context_block}

---

以下是會議逐字稿：

{transcript}

---

請根據以上資訊生成會議摘要。"""


class MeetingSummarizer:
    """Generates structured meeting summaries using LLM + prompt templates."""

    def __init__(self, llm: BaseLLM) -> None:
        self.llm = llm

    def summarize(
        self,
        transcript: str,
        template: PromptTemplate,
        context: MeetingContext,
        system_prompt: str | None = None,
    ) -> str:
        """Generate a meeting summary from transcript + template + context.

        Args:
            system_prompt: Override the template's system prompt if provided.
        """
        context.validate()

        user_message = USER_PROMPT_TEMPLATE.format(
            context_block=context.render_context_block(),
            transcript=transcript,
        )

        try:
            return self.llm.chat(
                system_prompt=system_prompt or template.system_prompt,
                user_message=user_message,
                temperature=0.3,
            )
        except Exception as e:
            raise SummaryError(f"Summary generation failed: {e}") from e
