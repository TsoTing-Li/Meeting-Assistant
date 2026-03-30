from core.storage.base import BaseStorage
from core.storage.local_client import LocalStorage


def get_storage() -> BaseStorage:
    """Return local filesystem storage."""
    from core.config import settings
    return LocalStorage(settings.local_storage_path)


__all__ = ["BaseStorage", "LocalStorage", "get_storage"]
