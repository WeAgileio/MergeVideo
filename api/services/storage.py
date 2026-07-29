"""Object storage 服務，啟動時以 STORAGE_BACKEND 切換：

- local  : 本機目錄（開發 / 測試）
- s3     : AWS S3 及所有 S3 相容服務（MinIO / R2 / OSS / COS / Wasabi / B2）
- gcs    : Google Cloud Storage
- azure  : Azure Blob Storage
- rclone : 任何 rclone 遠端（Google Drive / OneDrive / Dropbox / Box ...）
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import timedelta
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

from api.config import Settings, get_settings


class Storage(Protocol):
    def put(self, key: str, local_path: Path, content_type: str) -> None: ...

    def fetch(self, key: str, dest_path: Path) -> None: ...

    def delete(self, key: str) -> None: ...

    def delete_prefix(self, prefix: str) -> None: ...

    def presigned_url(self, key: str, expires_seconds: int, filename: str) -> str: ...


class LocalStorage:
    """本機目錄儲存，download URL 由 API 的 /storage 靜態路由提供。

    注意：local backend 的 URL 不會真正過期，僅供開發與測試使用。
    """

    def __init__(self, base_dir: Path, public_base_url: str) -> None:
        self.base_dir = base_dir
        self.public_base_url = public_base_url
        base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.base_dir / key

    def put(self, key: str, local_path: Path, content_type: str) -> None:
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(local_path, dest)

    def fetch(self, key: str, dest_path: Path) -> None:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self._path(key), dest_path)

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def delete_prefix(self, prefix: str) -> None:
        target = self._path(prefix)
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)

    def presigned_url(self, key: str, expires_seconds: int, filename: str) -> str:
        return f"{self.public_base_url}/storage/{quote(key)}"


class S3Storage:
    """S3 相容 object storage（AWS S3 / MinIO / OSS）。

    presigned URL 的簽名綁定 endpoint host：容器內部以 S3_ENDPOINT_URL 傳輸，
    若該位址對外不可達（如 http://minio:9000），須另設 S3_PUBLIC_ENDPOINT_URL
    （如 http://localhost:9000），簽名時改用對外端點。
    """

    def __init__(self, settings: Settings) -> None:
        import boto3

        self.bucket = settings.s3_bucket

        def _make_client(endpoint: str | None):
            return boto3.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id=settings.s3_access_key,
                aws_secret_access_key=settings.s3_secret_key,
                region_name=settings.s3_region,
            )

        self.client = _make_client(settings.s3_endpoint_url)
        if settings.s3_public_endpoint_url:
            self._signing_client = _make_client(settings.s3_public_endpoint_url)
        else:
            self._signing_client = self.client
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception:
            self.client.create_bucket(Bucket=self.bucket)

    def put(self, key: str, local_path: Path, content_type: str) -> None:
        self.client.upload_file(
            str(local_path), self.bucket, key, ExtraArgs={"ContentType": content_type}
        )

    def fetch(self, key: str, dest_path: Path) -> None:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, key, str(dest_path))

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def delete_prefix(self, prefix: str) -> None:
        response = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
        keys = [{"Key": item["Key"]} for item in response.get("Contents", [])]
        if keys:
            self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": keys})

    def presigned_url(self, key: str, expires_seconds: int, filename: str) -> str:
        return self._signing_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ResponseContentDisposition": f'attachment; filename="{filename}"',
            },
            ExpiresIn=expires_seconds,
        )


class GCSStorage:
    """Google Cloud Storage；signed URL 需 service account 認證。"""

    def __init__(self, settings: Settings) -> None:
        from google.cloud import storage as gcs

        if settings.gcs_credentials_json:
            client = gcs.Client.from_service_account_json(settings.gcs_credentials_json)
        else:
            client = gcs.Client()
        self.bucket = client.bucket(settings.gcs_bucket)

    def put(self, key: str, local_path: Path, content_type: str) -> None:
        self.bucket.blob(key).upload_from_filename(str(local_path), content_type=content_type)

    def fetch(self, key: str, dest_path: Path) -> None:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        self.bucket.blob(key).download_to_filename(str(dest_path))

    def delete(self, key: str) -> None:
        try:
            self.bucket.blob(key).delete()
        except Exception:
            pass

    def delete_prefix(self, prefix: str) -> None:
        for blob in self.bucket.client.list_blobs(self.bucket, prefix=prefix):
            blob.delete()

    def presigned_url(self, key: str, expires_seconds: int, filename: str) -> str:
        return self.bucket.blob(key).generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=expires_seconds),
            response_disposition=f'attachment; filename="{filename}"',
        )


class AzureBlobStorage:
    """Azure Blob Storage；download URL 為 SAS URL。"""

    def __init__(self, settings: Settings) -> None:
        from azure.storage.blob import BlobServiceClient

        if not settings.azure_connection_string:
            raise RuntimeError("azure backend 需設定 AZURE_CONNECTION_STRING")
        self.service = BlobServiceClient.from_connection_string(settings.azure_connection_string)
        self.container_name = settings.azure_container
        self.container = self.service.get_container_client(self.container_name)
        if not self.container.exists():
            self.container.create_container()

    def put(self, key: str, local_path: Path, content_type: str) -> None:
        from azure.storage.blob import ContentSettings

        with local_path.open("rb") as handle:
            self.container.upload_blob(
                key,
                handle,
                overwrite=True,
                content_settings=ContentSettings(content_type=content_type),
            )

    def fetch(self, key: str, dest_path: Path) -> None:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with dest_path.open("wb") as handle:
            self.container.download_blob(key).readinto(handle)

    def delete(self, key: str) -> None:
        try:
            self.container.delete_blob(key)
        except Exception:
            pass

    def delete_prefix(self, prefix: str) -> None:
        for blob in self.container.list_blobs(name_starts_with=prefix):
            self.container.delete_blob(blob.name)

    def presigned_url(self, key: str, expires_seconds: int, filename: str) -> str:
        from datetime import datetime, timezone

        from azure.storage.blob import BlobSasPermissions, generate_blob_sas

        sas = generate_blob_sas(
            account_name=self.service.account_name,
            container_name=self.container_name,
            blob_name=key,
            account_key=self.service.credential.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(timezone.utc) + timedelta(seconds=expires_seconds),
            content_disposition=f'attachment; filename="{filename}"',
        )
        return f"{self.container.url}/{quote(key)}?{sas}"


class RcloneStorage:
    """以 rclone 存取任何已設定的遠端（Google Drive / OneDrive / Dropbox ...）。

    需先以 `rclone config` 建立遠端；RCLONE_REMOTE 格式為「遠端名:根資料夾」。
    限制：download URL 由 `rclone link` 產生的公開分享連結，無法控制過期時間。
    """

    def __init__(self, remote: str, rclone_bin: str = "rclone") -> None:
        if shutil.which(rclone_bin) is None:
            raise RuntimeError(f"找不到 rclone 執行檔: {rclone_bin}，請先安裝並設定遠端")
        self.remote = remote.rstrip("/")
        self.bin = rclone_bin

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self.bin, *args], check=True, capture_output=True, text=True
        )

    def _target(self, key: str) -> str:
        return f"{self.remote}/{key}"

    def put(self, key: str, local_path: Path, content_type: str) -> None:
        self._run("copyto", str(local_path), self._target(key))

    def fetch(self, key: str, dest_path: Path) -> None:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        self._run("copyto", self._target(key), str(dest_path))

    def delete(self, key: str) -> None:
        try:
            self._run("deletefile", self._target(key))
        except subprocess.CalledProcessError:
            pass

    def delete_prefix(self, prefix: str) -> None:
        try:
            self._run("purge", self._target(prefix.rstrip("/")))
        except subprocess.CalledProcessError:
            pass

    def presigned_url(self, key: str, expires_seconds: int, filename: str) -> str:
        result = self._run("link", self._target(key))
        return result.stdout.strip()


_storage: Storage | None = None


def _build_storage(settings: Settings) -> Storage:
    backend = settings.storage_backend
    if backend == "local":
        return LocalStorage(settings.local_storage_dir, settings.public_base_url)
    if backend == "s3":
        return S3Storage(settings)
    if backend == "gcs":
        return GCSStorage(settings)
    if backend == "azure":
        return AzureBlobStorage(settings)
    if backend == "rclone":
        if not settings.rclone_remote:
            raise RuntimeError("rclone backend 需設定 RCLONE_REMOTE（例如 gdrive:mergevideo）")
        return RcloneStorage(settings.rclone_remote, settings.rclone_bin)
    raise RuntimeError(
        f"未知的 STORAGE_BACKEND: {backend}（支援 local / s3 / gcs / azure / rclone）"
    )


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = _build_storage(get_settings())
    return _storage


def reset_storage_cache() -> None:
    """測試用。"""
    global _storage
    _storage = None
