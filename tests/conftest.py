import uuid
import pytest
import anyio
from unittest.mock import MagicMock, AsyncMock, patch

from core.llm.base import BaseLLM, LLMMessage, LLMResponse
from core.storage.base import BaseStorage
from core.stt.base import BaseSTT, STTResult, TranscriptSegment
from core.correction.dictionary import CorrectionDictionary


class MockLLM(BaseLLM):
    """Test double for LLM — returns configurable responses."""

    def __init__(self, response: str = "mock LLM response") -> None:
        self.response = response
        self.calls: list[list[LLMMessage]] = []

    def complete(self, messages: list[LLMMessage], **kwargs) -> LLMResponse:
        self.calls.append(messages)
        return LLMResponse(content=self.response, model="mock-model")


class MockStorage(BaseStorage):
    """In-memory storage for tests."""

    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}

    def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self._data[key] = data
        return key

    def download(self, key: str) -> bytes:
        if key not in self._data:
            raise KeyError(f"Key not found: {key}")
        return self._data[key]

    def delete(self, key: str) -> None:
        self._data.pop(key, None)

    def get_url(self, key: str, expires_seconds: int = 3600) -> str:
        return f"http://mock-storage/{key}"

    def exists(self, key: str) -> bool:
        return key in self._data


class MockSTT(BaseSTT):
    """Test double for STT."""

    def __init__(self, result: STTResult | None = None) -> None:
        self._result = result or STTResult(
            text="這是一個測試的逐字稿 This is a test transcript",
            segments=[
                TranscriptSegment(start=0.0, end=3.0, text="這是一個測試的逐字稿", confidence=-0.5),
                TranscriptSegment(start=3.0, end=6.0, text="This is a test transcript", confidence=-0.3),
            ],
            language="zh",
            duration_seconds=6.0,
        )

    def transcribe(self, audio_path: str, language: str = "zh") -> STTResult:
        return self._result


@pytest.fixture
def mock_llm():
    return MockLLM()

@pytest.fixture
def mock_storage():
    return MockStorage()

@pytest.fixture
def mock_stt():
    return MockSTT()

@pytest.fixture
def empty_dictionary():
    return CorrectionDictionary()

@pytest.fixture
def sample_dictionary():
    d = CorrectionDictionary()
    d.add("阿里巴巴", "Alibaba")
    d.add("吉他", "GitHub")
    d.add("開鍵", "Open Key")
    return d


# ── API / Gateway test fixtures ───────────────────────────────────────────────

@pytest.fixture
def api_client(mock_storage):
    """
    FastAPI TestClient backed by:
    - in-memory SQLite (aiosqlite)
    - MockStorage (no MinIO needed)
    - Mocked Celery send_task (no Redis needed)

    No external services required.
    """
    from fastapi.testclient import TestClient
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from core.database import Base
    from services.gateway.main import app
    from services.gateway.dependencies import get_db, get_storage

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    Session = async_sessionmaker(engine, expire_on_commit=False)

    # Create tables before TestClient opens (sequential, no loop conflict)
    async def _create_tables():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    anyio.run(_create_tables)

    async def override_get_db():
        async with Session() as session:
            yield session

    fake_celery_result = MagicMock()
    fake_celery_result.id = str(uuid.uuid4())

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage] = lambda: mock_storage

    with patch("services.gateway.main.init_db_async", new_callable=AsyncMock), \
         patch("services.gateway.routers.meetings.celery_app") as mk_meetings, \
         patch("services.gateway.routers.tasks.celery_app") as mk_tasks, \
         patch("services.gateway.routers.documents.celery_app") as mk_docs:

        mk_meetings.send_task.return_value = fake_celery_result
        mk_docs.send_task.return_value = fake_celery_result

        with TestClient(app) as client:
            client._celery = mk_meetings   # expose for call assertions
            client._celery_tasks = mk_tasks
            yield client

    app.dependency_overrides.clear()
    anyio.run(engine.dispose)
