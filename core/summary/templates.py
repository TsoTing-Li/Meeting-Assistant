from dataclasses import dataclass, field
from datetime import date

from core.exceptions import PromptValidationError


@dataclass
class MeetingContext:
    """Context for generating a meeting summary. Only date is required."""
    date: str                                        # ISO format: YYYY-MM-DD
    meeting_type: str = "general"
    participants: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    def validate(self) -> None:
        if not self.date:
            raise PromptValidationError("Missing required field: date")

    def render_context_block(self) -> str:
        lines = [f"日期：{self.date}"]
        if self.meeting_type:
            lines.append(f"會議類型：{self.meeting_type}")
        if self.participants:
            lines.append(f"與會者：{'、'.join(self.participants)}")
        if self.topics:
            topics_str = "\n".join(f"- {t}" for t in self.topics)
            lines.append(f"議題：\n{topics_str}")
        if self.extra:
            extra_str = "\n".join(f"- {k}: {v}" for k, v in self.extra.items())
            lines.append(f"其他資訊：\n{extra_str}")
        return "\n".join(lines)


@dataclass
class PromptTemplate:
    name: str
    scene: str
    system_prompt: str
    is_builtin: bool = True


_WEEKLY_STANDUP_PROMPT = """你是一位專業的會議記錄助手，負責整理每週例會的摘要。請使用繁體中文回覆。

請根據提供的會議資訊與逐字稿，生成結構化的會議摘要，包含以下區塊：

## 會議摘要
（2-3 句話的整體概述）

## 本週進度
（各成員/項目的進度更新）

## 決議事項
（本次會議達成的決定，條列式）

## 待辦事項
（格式：- [ ] 負責人：任務內容）

## 未解決問題
（尚待討論或解決的事項）"""

_PROJECT_REVIEW_PROMPT = """你是一位專業的會議記錄助手，負責整理專案審查會議的摘要。請使用繁體中文回覆。

請根據提供的會議資訊與逐字稿，生成結構化的會議摘要，包含以下區塊：

## 會議摘要
（2-3 句話的整體概述）

## 專案現況
（進度、風險、問題）

## 討論重點
（重要討論事項與結論）

## 決議事項
（本次會議達成的決定，條列式）

## 行動項目
（格式：- [ ] 負責人：任務內容，截止日期）

## 風險與注意事項"""

_CLIENT_INTERVIEW_PROMPT = """你是一位專業的會議記錄助手，負責整理客戶訪談的摘要。請使用繁體中文回覆。

請根據提供的會議資訊與逐字稿，生成結構化的摘要，包含以下區塊：

## 訪談摘要
（2-3 句話的整體概述）

## 客戶需求
（客戶提出的需求與期望）

## 痛點與挑戰
（客戶面臨的問題）

## 討論要點
（重要討論內容）

## 後續行動
（格式：- [ ] 負責人：任務內容）

## 備註"""

_GENERAL_PROMPT = """你是一位專業的會議記錄助手。請使用繁體中文回覆。

請根據提供的會議資訊與逐字稿，生成結構化的會議摘要，包含以下區塊：

## 會議摘要
（2-3 句話的整體概述）

## 討論要點

## 決議事項

## 待辦事項
（格式：- [ ] 負責人：任務內容）

## 未解決問題"""


BUILTIN_TEMPLATES: dict[str, PromptTemplate] = {
    "weekly_standup": PromptTemplate(
        name="每週例會",
        scene="weekly_standup",
        system_prompt=_WEEKLY_STANDUP_PROMPT,
    ),
    "project_review": PromptTemplate(
        name="專案審查",
        scene="project_review",
        system_prompt=_PROJECT_REVIEW_PROMPT,
    ),
    "client_interview": PromptTemplate(
        name="客戶訪談",
        scene="client_interview",
        system_prompt=_CLIENT_INTERVIEW_PROMPT,
    ),
    "general": PromptTemplate(
        name="通用會議",
        scene="general",
        system_prompt=_GENERAL_PROMPT,
    ),
}


def get_template(scene: str) -> PromptTemplate:
    if scene not in BUILTIN_TEMPLATES:
        raise ValueError(f"Unknown scene '{scene}'. Available: {list(BUILTIN_TEMPLATES.keys())}")
    return BUILTIN_TEMPLATES[scene]
