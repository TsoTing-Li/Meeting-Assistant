import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Uuid, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("meetings.id"), nullable=False)
    audio_ref: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    raw_ref: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    corrected_ref: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="zh")
    duration_seconds: Mapped[Optional[float]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"<Transcript id={self.id} meeting_id={self.meeting_id}>"
