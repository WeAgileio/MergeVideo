"""API 設定（由環境變數載入）。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    database_url: str
    redis_url: str | None
    storage_backend: str  # "local" | "s3" | "gcs" | "azure" | "rclone"
    local_storage_dir: Path
    s3_endpoint_url: str | None
    s3_public_endpoint_url: str | None
    s3_bucket: str
    s3_access_key: str | None
    s3_secret_key: str | None
    s3_region: str
    gcs_bucket: str
    gcs_credentials_json: str | None
    azure_connection_string: str | None
    azure_container: str
    rclone_remote: str | None
    rclone_bin: str
    public_base_url: str
    api_keys: tuple[str, ...]
    max_file_size_bytes: int
    max_merge_files: int
    file_ttl_hours: int
    result_ttl_hours: int
    download_url_ttl_hours: int
    cors_origins: tuple[str, ...]
    import_url_allow_http: bool
    import_url_connect_timeout_sec: float
    import_url_total_timeout_sec: float
    import_url_max_redirects: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite:///./api_data/api.db"),
        redis_url=os.getenv("REDIS_URL") or None,
        storage_backend=os.getenv("STORAGE_BACKEND", "local"),
        local_storage_dir=Path(os.getenv("LOCAL_STORAGE_DIR", "./api_data/storage")),
        s3_endpoint_url=os.getenv("S3_ENDPOINT_URL") or None,
        s3_public_endpoint_url=os.getenv("S3_PUBLIC_ENDPOINT_URL") or None,
        s3_bucket=os.getenv("S3_BUCKET", "mergevideo"),
        s3_access_key=os.getenv("S3_ACCESS_KEY") or None,
        s3_secret_key=os.getenv("S3_SECRET_KEY") or None,
        s3_region=os.getenv("S3_REGION", "us-east-1"),
        gcs_bucket=os.getenv("GCS_BUCKET", "mergevideo"),
        gcs_credentials_json=os.getenv("GCS_CREDENTIALS_JSON") or None,
        azure_connection_string=os.getenv("AZURE_CONNECTION_STRING") or None,
        azure_container=os.getenv("AZURE_CONTAINER", "mergevideo"),
        rclone_remote=os.getenv("RCLONE_REMOTE") or None,
        rclone_bin=os.getenv("RCLONE_BIN", "rclone"),
        public_base_url=os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/"),
        api_keys=_split_csv(os.getenv("API_KEYS", "")),
        max_file_size_bytes=int(os.getenv("MAX_FILE_SIZE_MB", "200")) * 1024 * 1024,
        max_merge_files=int(os.getenv("MAX_MERGE_FILES", "10")),
        file_ttl_hours=int(os.getenv("FILE_TTL_HOURS", "24")),
        result_ttl_hours=int(os.getenv("RESULT_TTL_HOURS", "72")),
        download_url_ttl_hours=int(os.getenv("DOWNLOAD_URL_TTL_HOURS", "24")),
        cors_origins=_split_csv(os.getenv("CORS_ORIGINS", "*")) or ("*",),
        import_url_allow_http=os.getenv("IMPORT_URL_ALLOW_HTTP", "false").lower()
        in ("1", "true", "yes"),
        import_url_connect_timeout_sec=float(os.getenv("IMPORT_URL_CONNECT_TIMEOUT_SEC", "10")),
        import_url_total_timeout_sec=float(os.getenv("IMPORT_URL_TOTAL_TIMEOUT_SEC", "600")),
        import_url_max_redirects=int(os.getenv("IMPORT_URL_MAX_REDIRECTS", "3")),
    )


def reset_settings_cache() -> None:
    """測試用：環境變數變更後重載設定。"""
    get_settings.cache_clear()
