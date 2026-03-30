import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Text, Uuid, Enum as SAEnum, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class TaskType(str, enum.Enum):
    STT = "stt"
    CORRECTION = "correction"
    SUMMARY = "summary"
    AGGREGATION = "aggregation"
    DOCUMENT = "document"


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True)
    task_type: Mapped[TaskType] = mapped_column(SAEnum(TaskType), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(SAEnum(TaskStatus), default=TaskStatus.PENDING)
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    input_ref: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    output_ref: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Task id={self.id} type={self.task_type} status={self.status}>"
