from functools import lru_cache
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from core.storage import get_storage as _get_storage
from core.llm.litellm_client import LiteLLMClient


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


@lru_cache
def get_storage():
    return _get_storage()


@lru_cache
def get_llm() -> LiteLLMClient:
    return LiteLLMClient.from_settings()


@lru_cache
def get_stt() -> "HTTPSTTClient":
    from core.stt.http_client import HTTPSTTClient
    return HTTPSTTClient.from_settings()
