from pathlib import Path

from core.storage.base import BaseStorage


class LocalStorage(BaseStorage):
    """
    Local filesystem storage. Files are stored under base_path and served
    by the gateway at /storage/{key}.
    """

    def __init__(self, base_path: str | Path) -> None:
        self.base = Path(base_path).resolve()
        self.base.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Guard against path traversal
        target = (self.base / key).resolve()
        if not str(target).startswith(str(self.base)):
            raise ValueError(f"Invalid storage key: {key!r}")
        return target

    def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return key

    def download(self, key: str) -> bytes:
        p = self._path(key)
        if not p.exists():
            raise KeyError(f"Key not found: {key}")
        return p.read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def get_url(self, key: str, expires_seconds: int = 3600) -> str:
        # Gateway mounts local storage at /storage — URL is relative so it works on any host
        return f"/storage/{key}"

    def exists(self, key: str) -> bool:
        return self._path(key).exists()
