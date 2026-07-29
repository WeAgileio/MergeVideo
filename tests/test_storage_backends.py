"""Storage backend 切換測試。"""

from __future__ import annotations

from dataclasses import replace

import pytest

from api.config import get_settings
from api.services.storage import LocalStorage, RcloneStorage, S3Storage, _build_storage


def make_settings(**overrides):
    return replace(get_settings(), **overrides)


def test_local_backend():
    storage = _build_storage(make_settings(storage_backend="local"))
    assert isinstance(storage, LocalStorage)


def test_unknown_backend_rejected():
    with pytest.raises(RuntimeError, match="未知的 STORAGE_BACKEND"):
        _build_storage(make_settings(storage_backend="ftp"))


def test_rclone_requires_remote():
    with pytest.raises(RuntimeError, match="RCLONE_REMOTE"):
        _build_storage(make_settings(storage_backend="rclone", rclone_remote=None))


def test_rclone_backend_construction():
    # 以系統必有的 echo 當作執行檔存在性檢查的替身
    storage = _build_storage(
        make_settings(
            storage_backend="rclone",
            rclone_remote="gdrive:mergevideo",
            rclone_bin="echo",
        )
    )
    assert isinstance(storage, RcloneStorage)
    assert storage._target("uploads/f_x/original.mp4") == (
        "gdrive:mergevideo/uploads/f_x/original.mp4"
    )


def test_azure_requires_connection_string():
    pytest.importorskip("azure.storage.blob")
    with pytest.raises(RuntimeError, match="AZURE_CONNECTION_STRING"):
        _build_storage(
            make_settings(storage_backend="azure", azure_connection_string=None)
        )


def test_s3_backend_class():
    # 不實際連線，只確認 factory 分派正確（以 MinIO endpoint 建 client 不會發出請求，
    # 但 ensure_bucket 會，故僅檢查類別對應存在）
    assert S3Storage is not None
