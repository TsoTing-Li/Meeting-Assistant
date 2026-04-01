from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    llm_api_key: str = ""
    llm_base_url: str = ""

    # STT
    stt_model: str = "large-v3"
    stt_device: str = "cpu"
    stt_compute_type: str = "int8"
    stt_workers: int = 1  # number of concurrent model instances

    # Service URLs (used when running in Docker; services call each other)
    stt_service_url: str = "http://localhost:8080"
    llm_proxy_url: str = "http://localhost:8001"

    # STT HTTP timeout (seconds): read timeout should be long for CPU transcription
    stt_connect_timeout: float = 10.0
    stt_write_timeout: float = 120.0   # audio upload
    stt_read_timeout: float = 7200.0   # transcription result (up to 2hr)

    # Storage
    local_storage_path: str = "./data/storage"

    # Database
    database_url: str = "sqlite:///./data/meeting_assistant.db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"


settings = Settings()
