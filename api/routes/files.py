"""檔案上傳與管理 endpoints。"""

from __future__ import annotations

import json
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session

from api.auth import require_api_key
from api.config import compute_file_expires_at, expires_at_to_api, get_settings
from api.db import get_session
from api.errors import ApiError, file_not_found
from api.models import FileRecord, utcnow
from api.services.storage import get_storage
from scanner import VIDEO_EXTENSIONS

router = APIRouter(prefix="/v1/files", tags=["files"])

SRT_EXTENSIONS = {".srt"}
SRT_CONTENT_TYPE = "application/x-subrip"
IMAGE_CONTENT_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
IMAGE_EXTENSIONS = set(IMAGE_CONTENT_TYPES)
_UPLOAD_EXTENSIONS = VIDEO_EXTENSIONS | SRT_EXTENSIONS | IMAGE_EXTENSIONS

_CHUNK_SIZE = 1024 * 1024


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds") + "Z"


def _probe_metadata(path: Path) -> str | None:
    """上傳時嘗試取得影片 metadata；失敗不阻擋上傳。"""
    try:
        from probe import probe_video

        info = probe_video(path)
        return json.dumps(
            {
                "width": info.width,
                "height": info.height,
                "fps": round(info.fps_float, 3),
                "codec": info.vcodec,
                "duration_sec": round(info.duration, 3),
                "has_audio": info.has_audio,
            }
        )
    except Exception:
        return None


def _file_response(record: FileRecord) -> dict:
    payload = {
        "file_id": record.file_id,
        "filename": record.filename,
        "size_bytes": record.size_bytes,
        "content_type": record.content_type,
        "created_at": _iso(record.created_at),
        "expires_at": expires_at_to_api(record.expires_at),
    }
    if record.metadata_json:
        payload["metadata"] = json.loads(record.metadata_json)
    return payload


def get_owned_file(session: Session, file_id: str, owner_key: str) -> FileRecord:
    """取得屬於 owner 的有效檔案；不存在 / 非本人 / 已過期一律 404。"""
    record = session.get(FileRecord, file_id)
    if record is None or record.owner_key != owner_key or record.is_expired():
        raise file_not_found(file_id)
    return record


_UPLOAD_RESPONSES = {
    201: {
        "description": "上傳成功",
        "content": {
            "application/json": {
                "examples": {
                    "video": {
                        "summary": "影片",
                        "value": {
                            "file_id": "f_7x9k2m1a3b4c",
                            "filename": "1.mp4",
                            "size_bytes": 52428800,
                            "content_type": "video/mp4",
                            "created_at": "2026-07-29T02:00:00Z",
                            "expires_at": None,
                            "metadata": {
                                "width": 2560,
                                "height": 1440,
                                "fps": 24.0,
                                "codec": "h264",
                                "duration_sec": 12.5,
                                "has_audio": True,
                            },
                        },
                    },
                    "srt": {
                        "summary": "SRT 字幕",
                        "value": {
                            "file_id": "f_srt111",
                            "filename": "talk.srt",
                            "size_bytes": 512,
                            "content_type": "application/x-subrip",
                            "created_at": "2026-08-26T02:00:00Z",
                            "expires_at": None,
                        },
                    },
                    "image": {
                        "summary": "靜態圖",
                        "value": {
                            "file_id": "f_img222",
                            "filename": "slide.png",
                            "size_bytes": 204800,
                            "content_type": "image/png",
                            "created_at": "2026-08-26T02:00:00Z",
                            "expires_at": None,
                        },
                    },
                }
            }
        },
    },
    400: {"description": "格式不支援或檔案為空（UNSUPPORTED_FORMAT / EMPTY_FILE）"},
    413: {"description": "超過大小上限（FILE_TOO_LARGE）"},
}


@router.post(
    "",
    status_code=201,
    summary="上傳影片、SRT 或圖片",
    description=(
        "以 multipart/form-data 上傳單一檔案（欄位名 `file`），回傳 `file_id` 供後續任務引用。\n\n"
        "- 支援影片：mp4 / mov / webm / mkv / avi / m4v\n"
        "- 支援字幕：`.srt`（`content_type: application/x-subrip`，不跑 ffprobe；"
        "可作為 `POST /v1/jobs/burn-subtitle` 的 `srt_file_id`）\n"
        "- 支援圖片：`.png` / `.jpg` / `.jpeg` / `.webp`（`content_type` 為 "
        "`image/png`、`image/jpeg`、`image/webp`，不跑 ffprobe；"
        "可作為 `POST /v1/jobs/replace-images` 的 `image_file_id`）\n"
        "- 單檔大小上限由 `MAX_FILE_SIZE_MB` 控制（預設 200 MB）\n"
        "- `FILE_TTL_HOURS=0`（預設）表示永不過期；> 0 時依小時數邏輯過期，"
        "被進行中任務引用時不會過期"
    ),
    responses=_UPLOAD_RESPONSES,
)
async def upload_file(
    file: UploadFile,
    owner_key: str = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> dict:
    settings = get_settings()

    filename = Path(file.filename or "video.mp4").name
    suffix = Path(filename).suffix.lower()
    if suffix not in _UPLOAD_EXTENSIONS:
        raise ApiError(
            400,
            "UNSUPPORTED_FORMAT",
            f"不支援的檔案格式: {suffix or '(無副檔名)'}，支援: {', '.join(sorted(_UPLOAD_EXTENSIONS))}",
        )

    is_srt = suffix in SRT_EXTENSIONS
    is_image = suffix in IMAGE_EXTENSIONS
    if is_srt:
        content_type = SRT_CONTENT_TYPE
    elif is_image:
        content_type = IMAGE_CONTENT_TYPES[suffix]
    else:
        content_type = "video/mp4"

    size = 0
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp_path = Path(tmp.name)
            while chunk := await file.read(_CHUNK_SIZE):
                size += len(chunk)
                if size > settings.max_file_size_bytes:
                    raise ApiError(
                        413,
                        "FILE_TOO_LARGE",
                        f"檔案超過大小上限 {settings.max_file_size_bytes // (1024 * 1024)} MB",
                    )
                tmp.write(chunk)

        if size == 0:
            raise ApiError(400, "EMPTY_FILE", "上傳的檔案為空")

        file_id = f"f_{uuid.uuid4().hex[:12]}"
        storage_key = f"uploads/{file_id}/original{suffix}"
        get_storage().put(storage_key, tmp_path, content_type)

        now = utcnow()
        record = FileRecord(
            file_id=file_id,
            owner_key=owner_key,
            filename=filename,
            storage_key=storage_key,
            size_bytes=size,
            content_type=content_type,
            metadata_json=None if (is_srt or is_image) else _probe_metadata(tmp_path),
            created_at=now,
            expires_at=compute_file_expires_at(now, settings.file_ttl_hours),
        )
        session.add(record)
        session.commit()
        return _file_response(record)
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


@router.get(
    "/{file_id}",
    summary="查詢檔案",
    description=(
        "回傳檔案 metadata。僅檔案擁有者可查詢。\n\n"
        "- 影片：可能含上傳時 ffprobe 解析的 `metadata`（寬高、fps、codec 等）\n"
        "- `.srt`：`content_type` 為 `application/x-subrip`，無影片 metadata\n"
        "- 圖片：`content_type` 為 `image/png`、`image/jpeg` 或 `image/webp`，無影片 metadata"
    ),
    responses={404: {"description": "檔案不存在、已過期或非本人所有（FILE_NOT_FOUND）"}},
)
def get_file(
    file_id: str,
    owner_key: str = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> dict:
    record = get_owned_file(session, file_id, owner_key)
    return _file_response(record)


@router.delete(
    "/{file_id}",
    status_code=204,
    summary="刪除檔案",
    description="從 storage 與 registry 刪除檔案。檔案正被進行中任務使用時無法刪除。",
    responses={
        404: {"description": "檔案不存在（FILE_NOT_FOUND）"},
        409: {"description": "檔案被進行中任務 pin 住（FILE_PINNED）"},
    },
)
def delete_file(
    file_id: str,
    owner_key: str = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> None:
    record = get_owned_file(session, file_id, owner_key)
    if record.active_jobs > 0:
        raise ApiError(409, "FILE_PINNED", "檔案正被進行中的任務使用，無法刪除")

    get_storage().delete(record.storage_key)
    session.delete(record)
    session.commit()
