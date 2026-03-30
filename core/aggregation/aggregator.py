from dataclasses import dataclass

from core.llm.base import BaseLLM
from core.exceptions import AggregationError

AGGREGATION_SYSTEM_PROMPT = """你是一位專業的專案管理助手，負責彙整多場會議的摘要，呈現整體進展。

請根據提供的多場會議摘要，生成跨會議彙整報告，包含以下區塊：

## 整體進展
（專案或議題的整體進展概述）

## 累積決策
（所有會議中達成的重要決策，按重要性排列）

## 持續待辦
（尚未完成的待辦事項，標示來源會議）

## 跨會議未解決問題
（多場會議都出現或尚未解決的問題）

## 趨勢與觀察
（從多場會議中觀察到的模式或趨勢）"""

AGGREGATION_USER_PROMPT = """以下是 {count} 場會議的摘要，請進行跨會議彙整分析：

{summaries_block}"""


@dataclass
class AggregationResult:
    content: str
    meeting_count: int
    meeting_ids: list


class MeetingAggregator:
    """Aggregates multiple meeting summaries into a cross-meeting report."""

    def __init__(self, llm: BaseLLM) -> None:
        self.llm = llm

    def aggregate(
        self,
        summaries: list[str],
        meeting_ids: list | None = None,
        meeting_labels: list[str] | None = None,
    ) -> AggregationResult:
        """
        Aggregate multiple meeting summaries.

        Args:
            summaries: List of meeting summary texts
            meeting_ids: Optional list of meeting IDs for tracking
            meeting_labels: Optional labels for each meeting (e.g. dates or titles)
        """
        if not summaries:
            raise AggregationError("No summaries provided for aggregation.")
        if len(summaries) < 2:
            raise AggregationError("At least 2 summaries are required for aggregation.")

        labels = meeting_labels or [f"第 {i+1} 場會議" for i in range(len(summaries))]
        summaries_block = "\n\n".join(
            f"### {label}\n{summary}"
            for label, summary in zip(labels, summaries)
        )

        try:
            content = self.llm.chat(
                system_prompt=AGGREGATION_SYSTEM_PROMPT,
                user_message=AGGREGATION_USER_PROMPT.format(
                    count=len(summaries),
                    summaries_block=summaries_block,
                ),
                temperature=0.3,
            )
            return AggregationResult(
                content=content,
                meeting_count=len(summaries),
                meeting_ids=meeting_ids or [],
            )
        except Exception as e:
            raise AggregationError(f"Aggregation failed: {e}") from e
