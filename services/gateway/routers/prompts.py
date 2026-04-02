import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.prompt import SystemPrompt, PromptScene
from core.summary.templates import BUILTIN_TEMPLATES
from core.aggregation.aggregator import AGGREGATION_SYSTEM_PROMPT
from services.gateway.dependencies import get_db

router = APIRouter()


# ── Pydantic models ────────────────────────────────────────────────────────

class PromptTemplateResponse(BaseModel):
    id: Optional[uuid.UUID]
    scene: str
    name: str
    system_prompt: str
    is_builtin: bool


class PromptCreate(BaseModel):
    name: str
    system_prompt: str


class PromptUpdate(BaseModel):
    name: Optional[str] = None
    system_prompt: Optional[str] = None


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("", response_model=list[PromptTemplateResponse])
async def list_prompts(db: AsyncSession = Depends(get_db)):
    """List all prompt templates: built-in + user-defined."""
    builtin = [
        PromptTemplateResponse(
            id=None,
            scene=t.scene,
            name=t.name,
            system_prompt=t.system_prompt,
            is_builtin=True,
        )
        for t in BUILTIN_TEMPLATES.values()
    ] + [
        PromptTemplateResponse(
            id=None,
            scene="aggregation",
            name="跨會議聚合",
            system_prompt=AGGREGATION_SYSTEM_PROMPT,
            is_builtin=True,
        )
    ]

    result = await db.execute(select(SystemPrompt).order_by(SystemPrompt.created_at.asc()))
    custom = [
        PromptTemplateResponse(
            id=p.id,
            scene=p.scene.value,
            name=p.name,
            system_prompt=p.template,
            is_builtin=False,
        )
        for p in result.scalars().all()
    ]

    return builtin + custom


@router.post("", response_model=PromptTemplateResponse, status_code=201)
async def create_prompt(payload: PromptCreate, db: AsyncSession = Depends(get_db)):
    """Create a custom prompt template."""
    prompt = SystemPrompt(
        name=payload.name,
        scene=PromptScene.CUSTOM,
        template=payload.system_prompt,
        is_builtin=False,
    )
    db.add(prompt)
    await db.commit()
    await db.refresh(prompt)
    return PromptTemplateResponse(
        id=prompt.id,
        scene=prompt.scene.value,
        name=prompt.name,
        system_prompt=prompt.template,
        is_builtin=False,
    )


@router.get("/{prompt_id}", response_model=PromptTemplateResponse)
async def get_prompt(prompt_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    prompt = await db.get(SystemPrompt, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return PromptTemplateResponse(
        id=prompt.id,
        scene=prompt.scene.value,
        name=prompt.name,
        system_prompt=prompt.template,
        is_builtin=False,
    )


@router.put("/{prompt_id}", response_model=PromptTemplateResponse)
async def update_prompt(prompt_id: uuid.UUID, payload: PromptUpdate, db: AsyncSession = Depends(get_db)):
    prompt = await db.get(SystemPrompt, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    if prompt.is_builtin:
        raise HTTPException(status_code=403, detail="Cannot modify built-in prompts")
    if payload.name is not None:
        prompt.name = payload.name
    if payload.system_prompt is not None:
        prompt.template = payload.system_prompt
    await db.commit()
    await db.refresh(prompt)
    return PromptTemplateResponse(
        id=prompt.id,
        scene=prompt.scene.value,
        name=prompt.name,
        system_prompt=prompt.template,
        is_builtin=False,
    )


@router.delete("/{prompt_id}", status_code=204)
async def delete_prompt(prompt_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    prompt = await db.get(SystemPrompt, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    if prompt.is_builtin:
        raise HTTPException(status_code=403, detail="Cannot delete built-in prompts")
    await db.delete(prompt)
    await db.commit()
