import enum
import uuid
from datetime import datetime
from typing import Optional
import json

from sqlalchemy import String, DateTime, Text, Enum as SAEnum, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class MeetingType(str, enum.Enum):
    WEEKLY_STANDUP = "weekly_standup"
    PROJECT_REVIEW = "project_review"
    CLIENT_INTERVIEW = "client_interview"
    GENERAL = "general"


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    meeting_type: Mapped[MeetingType] = mapped_column(
        SAEnum(MeetingType), default=MeetingType.GENERAL
    )
    language: Mapped[str] = mapped_column(String(10), default="zh")
    _participants: Mapped[Optional[str]] = mapped_column("participants", Text, nullable=True)
    _topics: Mapped[Optional[str]] = mapped_column("topics", Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    @property
    def participants(self) -> list[str]:
        if self._participants:
            return json.loads(self._participants)
        return []

    @participants.setter
    def participants(self, value: list[str]) -> None:
        self._participants = json.dumps(value, ensure_ascii=False)

    @property
    def topics(self) -> list[str]:
        if self._topics:
            return json.loads(self._topics)
        return []

    @topics.setter
    def topics(self, value: list[str]) -> None:
        self._topics = json.dumps(value, ensure_ascii=False)

    def __repr__(self) -> str:
        return f"<Meeting id={self.id} title={self.title!r} date={self.date}>"
