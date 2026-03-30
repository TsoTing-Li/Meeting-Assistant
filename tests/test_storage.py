import pytest
from core.storage.base import BaseStorage
from tests.conftest import MockStorage


def test_upload_and_download(mock_storage):
    data = b"hello world"
    key = mock_storage.upload("test/file.txt", data, "text/plain")
    assert key == "test/file.txt"
    assert mock_storage.download("test/file.txt") == data


def test_exists_returns_true_after_upload(mock_storage):
    mock_storage.upload("exists/file.bin", b"data")
    assert mock_storage.exists("exists/file.bin") is True


def test_exists_returns_false_for_missing(mock_storage):
    assert mock_storage.exists("nonexistent/key") is False


def test_delete_removes_file(mock_storage):
    mock_storage.upload("del/file.txt", b"data")
    mock_storage.delete("del/file.txt")
    assert mock_storage.exists("del/file.txt") is False


def test_delete_nonexistent_does_not_raise(mock_storage):
    # Should silently do nothing
    mock_storage.delete("nonexistent/key")


def test_get_url_returns_string(mock_storage):
    mock_storage.upload("url/test.txt", b"data")
    url = mock_storage.get_url("url/test.txt")
    assert isinstance(url, str)
    assert len(url) > 0


def test_upload_returns_key(mock_storage):
    key = mock_storage.upload("path/to/audio.mp3", b"\x00\x01\x02", "audio/mpeg")
    assert key == "path/to/audio.mp3"


def test_download_missing_key_raises(mock_storage):
    with pytest.raises(KeyError):
        mock_storage.download("missing/key")


def test_upload_overwrites_existing(mock_storage):
    mock_storage.upload("file.txt", b"original")
    mock_storage.upload("file.txt", b"updated")
    assert mock_storage.download("file.txt") == b"updated"
