import asyncio
import json
import uuid
from typing import Optional, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.task import Task, TaskStatus
from core.database import AsyncSessionLocal
from services.gateway.dependencies import get_db
from services.task_worker.celery_app import celery_app

router = APIRouter()


class TaskResponse(BaseModel):
    id: uuid.UUID
    meeting_id: Optional[uuid.UUID]
    task_type: str
    status: str
    celery_task_id: Optional[str]
    input_ref: Optional[str]
    output_ref: Optional[str]
    error: Optional[str]
    created_at: str
    updated_at: str

    @classmethod
    def from_orm(cls, t: Task) -> "TaskResponse":
        return cls(
            id=t.id,
            meeting_id=t.meeting_id,
            task_type=t.task_type.value,
            status=t.status.value,
            celery_task_id=t.celery_task_id,
            input_ref=t.input_ref,
            output_ref=t.output_ref,
            error=t.error,
            created_at=t.created_at.isoformat(),
            updated_at=t.updated_at.isoformat(),
        )


@router.get("", response_model=list[TaskResponse])
async def list_tasks(meeting_id: Optional[uuid.UUID] = None, db: AsyncSession = Depends(get_db)):
    q = select(Task).order_by(Task.created_at.desc())
    if meeting_id:
        q = q.where(Task.meeting_id == meeting_id)
    result = await db.execute(q)
    return [TaskResponse.from_orm(t) for t in result.scalars().all()]


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.from_orm(task)


_TERMINAL_STATUSES = {TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED}
_POLL_INTERVAL = 2  # seconds


async def _task_event_stream(task_id: uuid.UUID) -> AsyncGenerator[str, None]:
    last_status = None
    while True:
        async with AsyncSessionLocal() as session:
            task = await session.get(Task, task_id)

        if task is None:
            yield f"event: error\ndata: {json.dumps({'detail': 'Task not found'})}\n\n"
            return

        if task.status != last_status:
            last_status = task.status
            payload = TaskResponse.from_orm(task).model_dump(mode="json")
            yield f"data: {json.dumps(payload)}\n\n"

        if task.status in _TERMINAL_STATUSES:
            return

        await asyncio.sleep(_POLL_INTERVAL)


@router.get("/{task_id}/stream")
async def stream_task(task_id: uuid.UUID):
    """SSE endpoint — streams task status until done/failed/cancelled."""
    return StreamingResponse(
        _task_event_stream(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )


@router.post("/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(task_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
        raise HTTPException(status_code=409, detail=f"Cannot cancel a task with status '{task.status.value}'")

    if task.celery_task_id:
        celery_app.control.revoke(task.celery_task_id, terminate=True, signal="SIGTERM")

    task.status = TaskStatus.CANCELLED
    await db.commit()
    await db.refresh(task)
    return TaskResponse.from_orm(task)
