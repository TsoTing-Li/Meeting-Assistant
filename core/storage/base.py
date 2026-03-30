from abc import ABC, abstractmethod


class BaseStorage(ABC):
    """Abstract interface for file storage. Swap implementations without changing callers."""

    @abstractmethod
    def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Upload data and return the storage key."""

    @abstractmethod
    def download(self, key: str) -> bytes:
        """Download data by key."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete file by key."""

    @abstractmethod
    def get_url(self, key: str, expires_seconds: int = 3600) -> str:
        """Get a presigned URL for the given key."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if a key exists in storage."""
