"""非同步 job endpoints（merge / extract frame / import url）。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.auth import require_api_key
from api.config import get_settings
from api.db import get_session
from api.errors import ApiError, invalid_url, job_not_found, unauthorized_file
from api.models import FileRecord, JobRecord, JobStatus, utcnow
from api.routes.files import get_owned_file
from api.services.queue import get_queue
from api.services.storage import get_storage
from api.services.url_import import UrlImportError, validate_url_scheme

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])

JOB_TYPE_MERGE = "merge"
JOB_TYPE_FIRST_FRAME = "extract_first_frame"
JOB_TYPE_LAST_FRAME = "extract_last_frame"
JOB_TYPE_IMPORT_URL = "import_url"


class MergeRequest(BaseModel):
    file_ids: list[str] = Field(
        min_length=1,
        description="要合併的 file_id 清單，**依陣列順序**串接（index 0 為第一段）",
        examples=[["f_aaa111", "f_bbb222", "f_ccc333"]],
    )
    crf: int = Field(
        18, description="Encode 模式的影片品質（越小越好，僅重新編碼時生效）"
    )


class ExtractRequest(BaseModel):
    file_id: str = Field(description="來源影片的 file_id", examples=["f_aaa111"])


class ImportUrlRequest(BaseModel):
    url: str = Field(
        description="可公開 GET 的影片 URL（預設僅 https）",
        examples=["https://cdn.example.com/clips/1.mp4"],
    )
    filename: str | None = Field(
        default=None,
        description="可選；省略則從 URL path 推斷",
        examples=["1.mp4"],
    )


_JOB_ACCEPTED_RESPONSE = {
    202: {
        "description": "任務已排入佇列",
        "content": {
            "application/json": {
                "example": {
                    "job_id": "j_9z8y7x6w5v4u",
                    "type": "merge",
                    "status": "queued",
                    "status_url": "/v1/jobs/j_9z8y7x6w5v4u",
                }
            }
        },
    },
    403: {"description": "引用了他人的檔案（UNAUTHORIZED_FILE）"},
    404: {"description": "檔案不存在或已過期（FILE_NOT_FOUND）"},
}

_IMPORT_URL_ACCEPTED_RESPONSE = {
    202: {
        "description": "匯入任務已排入佇列",
        "content": {
            "application/json": {
                "example": {
                    "job_id": "j_import123abc",
                    "type": "import_url",
                    "status": "queued",
                    "status_url": "/v1/jobs/j_import123abc",
                }
            }
        },
    },
    400: {
        "description": "URL 無效（INVALID_URL）",
        "content": {
            "application/json": {
                "example": {
                    "error": {
                        "code": "INVALID_URL",
                        "message": "僅允許 https URL（或設定 IMPORT_URL_ALLOW_HTTP=true）",
                    }
                }
            }
        },
    },
}


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds") + "Z"


def _resolve_file(session: Session, file_id: str, owner_key: str) -> FileRecord:
    """job 建立時解析 file_id：不存在/過期 404，非本人 403。"""
    record = session.get(FileRecord, file_id)
    if record is not None and record.owner_key != owner_key:
        raise unauthorized_file(file_id)
    return get_owned_file(session, file_id, owner_key)


def _create_job(
    session: Session,
    *,
    owner_key: str,
    job_type: str,
    file_ids: list[str],
    extra_input: dict | None = None,
) -> dict:
    records = [_resolve_file(session, fid, owner_key) for fid in file_ids]

    # pin 輸入檔，避免 job 進行中被過期清理或刪除
    for record in {r.file_id: r for r in records}.values():
        record.active_jobs += 1

    payload: dict = {"file_ids": file_ids}
    if extra_input:
        payload.update(extra_input)

    job = JobRecord(
        job_id=f"j_{uuid.uuid4().hex[:12]}",
        owner_key=owner_key,
        type=job_type,
        status=JobStatus.QUEUED,
        input_json=json.dumps(payload),
    )
    session.add(job)
    session.commit()
    get_queue().enqueue(job.job_id)

    return {
        "job_id": job.job_id,
        "type": job_type,
        "status": JobStatus.QUEUED,
        "status_url": f"/v1/jobs/{job.job_id}",
    }


def _create_import_url_job(
    session: Session,
    *,
    owner_key: str,
    url: str,
    filename: str | None,
) -> dict:
    job = JobRecord(
        job_id=f"j_{uuid.uuid4().hex[:12]}",
        owner_key=owner_key,
        type=JOB_TYPE_IMPORT_URL,
        status=JobStatus.QUEUED,
        input_json=json.dumps({"url": url, "filename": filename}),
    )
    session.add(job)
    session.commit()
    get_queue().enqueue(job.job_id)
    return {
        "job_id": job.job_id,
        "type": JOB_TYPE_IMPORT_URL,
        "status": JobStatus.QUEUED,
        "status_url": f"/v1/jobs/{job.job_id}",
    }


@router.post(
    "/merge",
    status_code=202,
    summary="建立合併任務",
    description=(
        "將多段影片合併為一支 MP4。\n\n"
        "- 片段順序 = `file_ids` **陣列順序**（與檔名無關）\n"
        "- 合併模式自動判斷：規格一致走 copy（快、無損），否則 encode"
        "（以最大面積片段為輸出解析度，其餘等比縮放加黑邊，H.264 + AAC）\n"
        "- 需 2–10 個 file_id（上限可由 `MAX_MERGE_FILES` 調整）"
    ),
    responses={
        **_JOB_ACCEPTED_RESPONSE,
        400: {"description": "片段數量不符（INSUFFICIENT_FILES / TOO_MANY_FILES)"},
    },
)
def create_merge_job(
    body: MergeRequest,
    owner_key: str = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> dict:
    settings = get_settings()
    if len(body.file_ids) < 2:
        raise ApiError(400, "INSUFFICIENT_FILES", "合併至少需要 2 個 file_id")
    if len(body.file_ids) > settings.max_merge_files:
        raise ApiError(
            400, "TOO_MANY_FILES", f"合併最多支援 {settings.max_merge_files} 個 file_id"
        )
    return _create_job(
        session,
        owner_key=owner_key,
        job_type=JOB_TYPE_MERGE,
        file_ids=body.file_ids,
        extra_input={"crf": body.crf},
    )


@router.post(
    "/extract-first-frame",
    status_code=202,
    summary="建立取第一幀任務",
    description="擷取影片第一幀為 PNG，結果檔名為 `{原檔名}_FirstFrame.png`。",
    responses=_JOB_ACCEPTED_RESPONSE,
)
def create_extract_first_frame_job(
    body: ExtractRequest,
    owner_key: str = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> dict:
    return _create_job(
        session,
        owner_key=owner_key,
        job_type=JOB_TYPE_FIRST_FRAME,
        file_ids=[body.file_id],
    )


@router.post(
    "/extract-last-frame",
    status_code=202,
    summary="建立取最後一幀任務",
    description="擷取影片最後一幀為 PNG，結果檔名為 `{原檔名}_LastFrame.png`。",
    responses=_JOB_ACCEPTED_RESPONSE,
)
def create_extract_last_frame_job(
    body: ExtractRequest,
    owner_key: str = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> dict:
    return _create_job(
        session,
        owner_key=owner_key,
        job_type=JOB_TYPE_LAST_FRAME,
        file_ids=[body.file_id],
    )


@router.post(
    "/import-url",
    status_code=202,
    summary="從 URL 匯入影片",
    description=(
        "由 server 下載指定 URL 的影片並註冊為 `file_id`（非同步 job）。\n\n"
        "- 預設僅允許 `https://`；`IMPORT_URL_ALLOW_HTTP=true` 可開放 `http://`\n"
        "- 完成後 `result` 含 `file_id`（非 download_url），可接 merge / extract job\n"
        "- 大小上限與 upload 相同（`MAX_FILE_SIZE_MB`）\n"
        "- 失敗時常見 error code：`URL_NOT_ALLOWED`、`DOWNLOAD_FAILED`、"
        "`FILE_TOO_LARGE`、`UNSUPPORTED_FORMAT`"
    ),
    responses=_IMPORT_URL_ACCEPTED_RESPONSE,
)
def create_import_url_job(
    body: ImportUrlRequest,
    owner_key: str = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> dict:
    settings = get_settings()
    try:
        validate_url_scheme(body.url, allow_http=settings.import_url_allow_http)
    except UrlImportError as exc:
        raise invalid_url(exc.message) from exc
    return _create_import_url_job(
        session,
        owner_key=owner_key,
        url=body.url.strip(),
        filename=body.filename,
    )


@router.get(
    "/{job_id}",
    summary="查詢任務狀態",
    description=(
        "輪詢任務狀態。狀態流轉：`queued → processing → done / failed`。\n\n"
        "- `progress`：處理進度 0–100（merge 依 FFmpeg 時長；import-url 依下載 bytes；"
        "取幀任務極快，可能直接從 0 跳到 100）\n"
        "- `done`：merge/extract 含 `result.download_url`；import-url 含 `result.file_id`\n"
        "- `failed`：回應含 `error.code` 與 `error.message`"
    ),
    responses={
        200: {
            "description": "任務狀態",
            "content": {
                "application/json": {
                    "examples": {
                        "processing": {
                            "summary": "處理中",
                            "value": {
                                "job_id": "j_9z8y7x6w5v4u",
                                "type": "merge",
                                "status": "processing",
                                "progress": 45,
                                "created_at": "2026-07-29T02:00:00Z",
                                "started_at": "2026-07-29T02:00:02Z",
                                "completed_at": None,
                            },
                        },
                        "done": {
                            "summary": "完成",
                            "value": {
                                "job_id": "j_9z8y7x6w5v4u",
                                "type": "merge",
                                "status": "done",
                                "progress": 100,
                                "created_at": "2026-07-29T02:00:00Z",
                                "started_at": "2026-07-29T02:00:02Z",
                                "completed_at": "2026-07-29T02:03:15Z",
                                "result": {
                                    "download_url": "https://storage.example.com/results/j_9z8y7x6w5v4u/merged.mp4?sig=...",
                                    "expires_at": "2026-07-30T02:03:15Z",
                                    "filename": "merged.mp4",
                                    "content_type": "video/mp4",
                                    "size_bytes": 156789012,
                                },
                            },
                        },
                        "import_processing": {
                            "summary": "URL 匯入中",
                            "value": {
                                "job_id": "j_import123abc",
                                "type": "import_url",
                                "status": "processing",
                                "progress": 45,
                                "created_at": "2026-07-29T02:00:00Z",
                                "started_at": "2026-07-29T02:00:01Z",
                                "completed_at": None,
                            },
                        },
                        "import_done": {
                            "summary": "URL 匯入完成",
                            "value": {
                                "job_id": "j_import123abc",
                                "type": "import_url",
                                "status": "done",
                                "progress": 100,
                                "created_at": "2026-07-29T02:00:00Z",
                                "started_at": "2026-07-29T02:00:01Z",
                                "completed_at": "2026-07-29T02:00:45Z",
                                "result": {
                                    "file_id": "f_imported456",
                                    "filename": "clip.mp4",
                                    "size_bytes": 52428800,
                                    "expires_at": None,
                                },
                            },
                        },
                        "import_failed": {
                            "summary": "URL 匯入失敗",
                            "value": {
                                "job_id": "j_import123abc",
                                "type": "import_url",
                                "status": "failed",
                                "progress": 0,
                                "created_at": "2026-07-29T02:00:00Z",
                                "started_at": "2026-07-29T02:00:01Z",
                                "completed_at": "2026-07-29T02:00:05Z",
                                "error": {
                                    "code": "URL_NOT_ALLOWED",
                                    "message": "URL 指向不允許的位址: 10.0.0.1",
                                },
                            },
                        },
                        "failed": {
                            "summary": "失敗",
                            "value": {
                                "job_id": "j_9z8y7x6w5v4u",
                                "type": "merge",
                                "status": "failed",
                                "progress": 12,
                                "created_at": "2026-07-29T02:00:00Z",
                                "started_at": "2026-07-29T02:00:02Z",
                                "completed_at": "2026-07-29T02:00:10Z",
                                "error": {
                                    "code": "FFMPEG_ERROR",
                                    "message": "找不到影片串流: 000.mp4",
                                },
                            },
                        },
                    }
                }
            },
        },
        404: {"description": "任務不存在或非本人所有（JOB_NOT_FOUND）"},
    },
)
def get_job(
    job_id: str,
    owner_key: str = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> dict:
    job = session.get(JobRecord, job_id)
    if job is None or job.owner_key != owner_key:
        raise job_not_found(job_id)

    payload: dict = {
        "job_id": job.job_id,
        "type": job.type,
        "status": job.status,
        "progress": job.progress,
        "created_at": _iso(job.created_at),
        "started_at": _iso(job.started_at) if job.started_at else None,
        "completed_at": _iso(job.completed_at) if job.completed_at else None,
    }

    if job.status == JobStatus.DONE:
        payload["result"] = _build_result(job)
    elif job.status == JobStatus.FAILED:
        payload["error"] = {
            "code": job.error_code or "INTERNAL_ERROR",
            "message": job.error_message or "任務失敗",
        }
    return payload


def _build_result(job: JobRecord) -> dict | None:
    if not job.result_json:
        return None  # 結果已過 TTL 被清理
    result = json.loads(job.result_json)

    if job.type == JOB_TYPE_IMPORT_URL:
        return {
            "file_id": result["file_id"],
            "filename": result["filename"],
            "size_bytes": result["size_bytes"],
            "expires_at": result["expires_at"],
        }

    settings = get_settings()
    ttl_seconds = settings.download_url_ttl_hours * 3600
    download_url = get_storage().presigned_url(
        result["storage_key"], ttl_seconds, result["filename"]
    )
    return {
        "download_url": download_url,
        "expires_at": _iso(utcnow() + timedelta(seconds=ttl_seconds)),
        "filename": result["filename"],
        "content_type": result["content_type"],
        "size_bytes": result["size_bytes"],
    }
