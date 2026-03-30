import json
import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Text, Boolean, Uuid, Enum as SAEnum, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class PromptScene(str, enum.Enum):
    WEEKLY_STANDUP = "weekly_standup"
    PROJECT_REVIEW = "project_review"
    CLIENT_INTERVIEW = "client_interview"
    GENERAL = "general"
    CUSTOM = "custom"


class SystemPrompt(Base):
    __tablename__ = "system_prompts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    scene: Mapped[PromptScene] = mapped_column(SAEnum(PromptScene), default=PromptScene.CUSTOM)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    _required_fields: Mapped[Optional[str]] = mapped_column("required_fields", Text, nullable=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    @property
    def required_fields(self) -> list[str]:
        if self._required_fields:
            return json.loads(self._required_fields)
        return ["meeting_type", "date", "participants", "topics"]

    @required_fields.setter
    def required_fields(self, value: list[str]) -> None:
        self._required_fields = json.dumps(value)

    def __repr__(self) -> str:
        return f"<SystemPrompt id={self.id} name={self.name!r} scene={self.scene}>"
