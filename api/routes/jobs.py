"""非同步 job endpoints（merge / extract / import-url / generate-subtitle / burn-subtitle / replace-images）。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.auth import require_api_key
from api.config import get_settings
from api.db import get_session
from api.errors import (
    ApiError,
    empty_replacements,
    invalid_font_size,
    invalid_margin,
    invalid_range,
    invalid_url,
    job_not_found,
    overlapping_ranges,
    script_empty,
    script_required,
    script_too_long,
    too_many_replacements,
    unauthorized_file,
    wrong_file_type,
)
from api.models import FileRecord, JobRecord, JobStatus, utcnow
from api.routes.files import IMAGE_EXTENSIONS, SRT_EXTENSIONS, get_owned_file
from api.services.burn_subtitle import (
    DEFAULT_FONT_SIZE,
    DEFAULT_MARGIN_BOTTOM,
    DEFAULT_MARGIN_UNIT,
    FONT_SIZE_MAX,
    FONT_SIZE_MIN,
)
from api.services.queue import get_queue
from api.services.storage import get_storage
from api.services.url_import import UrlImportError, validate_url_scheme
from scanner import VIDEO_EXTENSIONS

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])

JOB_TYPE_MERGE = "merge"
JOB_TYPE_FIRST_FRAME = "extract_first_frame"
JOB_TYPE_LAST_FRAME = "extract_last_frame"
JOB_TYPE_IMPORT_URL = "import_url"
JOB_TYPE_GENERATE_SUBTITLE = "generate_subtitle"
JOB_TYPE_BURN_SUBTITLE = "burn_subtitle"
JOB_TYPE_REPLACE_IMAGES = "replace_images"

MAX_REPLACEMENTS = 10


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


class GenerateSubtitleRequest(BaseModel):
    file_id: str = Field(description="來源影片的 file_id", examples=["f_aaa111"])
    script: str | None = Field(
        default=None,
        description="一整段文字稿，須與發音對應（必填，不做 ASR、不簡繁轉換）",
        examples=["大家好。歡迎收看本期內容。"],
    )


class BurnSubtitleRequest(BaseModel):
    file_id: str = Field(description="來源影片的 file_id", examples=["f_aaa111"])
    srt_file_id: str = Field(
        description="SRT 字幕的 file_id（generate-subtitle 的 result.file_id，或上傳的 .srt）",
        examples=["f_srt111"],
    )
    font_size: int | None = Field(
        default=None,
        description="字級（像素），省略為 48，允許 1–512",
        examples=[48],
    )
    margin_bottom: float | None = Field(
        default=None,
        description="離底邊距離，省略為 6。percent 時為畫面高度百分比；px 時為像素",
        examples=[6],
    )
    margin_unit: str | None = Field(
        default=None,
        description="`percent`（預設）或 `px`。percent 時實際像素 = round(畫面高度 × margin_bottom / 100)",
        examples=["percent"],
    )


class ReplacementItem(BaseModel):
    image_file_id: str = Field(
        description="已上傳圖片的 file_id（png / jpg / jpeg / webp）",
        examples=["f_img222"],
    )
    start: float = Field(description="起始秒數，`>= 0`（含）", examples=[3.0])
    end: float = Field(description="結束秒數，須 `> start`（含）", examples=[5.0])


class ReplaceImagesRequest(BaseModel):
    file_id: str = Field(description="來源影片的 file_id", examples=["f_aaa111"])
    replacements: list[ReplacementItem] = Field(
        default_factory=list,
        description=f"換圖時段，1–{MAX_REPLACEMENTS} 段，彼此不可重疊（`end` 等於下一段 `start` 可以）",
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

_SUBTITLE_ACCEPTED_RESPONSE = {
    202: {
        "description": "字幕任務已排入佇列",
        "content": {
            "application/json": {
                "example": {
                    "job_id": "j_sub123abc456",
                    "type": "generate_subtitle",
                    "status": "queued",
                    "status_url": "/v1/jobs/j_sub123abc456",
                }
            }
        },
    },
    400: {
        "description": "文字稿無效（SCRIPT_REQUIRED / SCRIPT_EMPTY / SCRIPT_TOO_LONG）",
        "content": {
            "application/json": {
                "example": {
                    "error": {
                        "code": "SCRIPT_EMPTY",
                        "message": "文字稿不可為空白",
                    }
                }
            }
        },
    },
    403: {"description": "引用了他人的檔案（UNAUTHORIZED_FILE）"},
    404: {"description": "檔案不存在或已過期（FILE_NOT_FOUND）"},
}

_BURN_ACCEPTED_RESPONSE = {
    202: {
        "description": "燒字幕任務已排入佇列",
        "content": {
            "application/json": {
                "example": {
                    "job_id": "j_burn123abc45",
                    "type": "burn_subtitle",
                    "status": "queued",
                    "status_url": "/v1/jobs/j_burn123abc45",
                }
            }
        },
    },
    400: {
        "description": "參數或檔案類型無效（WRONG_FILE_TYPE / INVALID_MARGIN / INVALID_FONT_SIZE）",
        "content": {
            "application/json": {
                "example": {
                    "error": {
                        "code": "WRONG_FILE_TYPE",
                        "message": "file_id 必須是影片檔",
                    }
                }
            }
        },
    },
    403: {"description": "引用了他人的檔案（UNAUTHORIZED_FILE）"},
    404: {"description": "檔案不存在或已過期（FILE_NOT_FOUND）"},
}

_REPLACE_IMAGES_ACCEPTED_RESPONSE = {
    202: {
        "description": "換圖任務已排入佇列",
        "content": {
            "application/json": {
                "example": {
                    "job_id": "j_rep123abc456",
                    "type": "replace_images",
                    "status": "queued",
                    "status_url": "/v1/jobs/j_rep123abc456",
                }
            }
        },
    },
    400: {
        "description": (
            "參數或檔案類型無效（EMPTY_REPLACEMENTS / TOO_MANY_REPLACEMENTS / "
            "INVALID_RANGE / OVERLAPPING_RANGES / WRONG_FILE_TYPE）"
        ),
        "content": {
            "application/json": {
                "example": {
                    "error": {
                        "code": "OVERLAPPING_RANGES",
                        "message": "replacements 的時段不可重疊: 1.0–3.0 與 2.0–4.0",
                    }
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


def _suffix(record: FileRecord) -> str:
    return Path(record.filename).suffix.lower()


def _require_video_file(record: FileRecord) -> None:
    if _suffix(record) not in VIDEO_EXTENSIONS:
        raise wrong_file_type("file_id 必須是影片檔")


def _require_srt_file(record: FileRecord) -> None:
    if _suffix(record) not in SRT_EXTENSIONS:
        raise wrong_file_type("srt_file_id 必須是 .srt 檔")


def _require_image_file(record: FileRecord) -> None:
    if _suffix(record) not in IMAGE_EXTENSIONS:
        raise wrong_file_type("image_file_id 必須是圖片檔（png / jpg / jpeg / webp）")


def _validate_replacements(items: list[ReplacementItem]) -> None:
    """時段本身是否合法，以及彼此是否重疊。"""
    if not items:
        raise empty_replacements()
    if len(items) > MAX_REPLACEMENTS:
        raise too_many_replacements(MAX_REPLACEMENTS)

    for item in items:
        if item.start < 0:
            raise invalid_range(f"start 不可為負數: {item.start}")
        if item.end <= item.start:
            raise invalid_range(f"end 須大於 start: {item.start}–{item.end}")

    ordered = sorted(items, key=lambda item: item.start)
    for previous, current in zip(ordered, ordered[1:]):
        if current.start < previous.end:
            raise overlapping_ranges(
                "replacements 的時段不可重疊: "
                f"{previous.start}–{previous.end} 與 {current.start}–{current.end}"
            )


def _video_duration(record: FileRecord) -> float | None:
    if not record.metadata_json:
        return None
    return json.loads(record.metadata_json).get("duration_sec")


def _normalize_burn_style(
    font_size: int | None, margin_bottom: float | None, margin_unit: str | None
) -> dict:
    size = DEFAULT_FONT_SIZE if font_size is None else font_size
    if size < FONT_SIZE_MIN or size > FONT_SIZE_MAX:
        raise invalid_font_size(f"font_size 須介於 {FONT_SIZE_MIN}–{FONT_SIZE_MAX}")

    unit = (margin_unit or DEFAULT_MARGIN_UNIT).strip().lower()
    if unit not in ("px", "percent"):
        raise invalid_margin("margin_unit 須為 px 或 percent")

    margin = DEFAULT_MARGIN_BOTTOM if margin_bottom is None else margin_bottom
    if unit == "percent":
        if margin < 0 or margin > 100:
            raise invalid_margin("percent 的 margin_bottom 須介於 0–100")
    elif margin < 0:
        raise invalid_margin("px 的 margin_bottom 不可為負數")

    return {
        "font_size": size,
        "margin_bottom": margin,
        "margin_unit": unit,
    }


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
        "- 完成後 `result` 含 `file_id`（非 download_url），可接 merge / extract / 字幕 job\n"
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


@router.post(
    "/generate-subtitle",
    status_code=202,
    summary="建立有稿字幕任務",
    description=(
        "對已上傳的影片產生標準 SRT 字幕（非同步 job；兩段式燒字幕的第一段）。\n\n"
        "- 必填 `script`：一整段文字稿，字幕文字以稿為準（不跑 ASR、不簡繁轉換）\n"
        "- Worker 以 FunASR `fa-zh` 強制對齊時間軸，再依 `。！？!?；，` 分句\n"
        "- 完成後 SRT 寫入 file registry：`result.file_id` 可交給 `POST /v1/jobs/burn-subtitle` 的 `srt_file_id`；"
        "同時含 `.srt` 的 `download_url`\n"
        "- 失敗時常見 error code：`SCRIPT_REQUIRED`、`SCRIPT_EMPTY`、`SCRIPT_TOO_LONG`、"
        "`NO_AUDIO_STREAM`、`ALIGN_FAILED`、`FUNASR_UNAVAILABLE`"
    ),
    responses=_SUBTITLE_ACCEPTED_RESPONSE,
)
def create_generate_subtitle_job(
    body: GenerateSubtitleRequest,
    owner_key: str = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> dict:
    settings = get_settings()
    if body.script is None:
        raise script_required()
    if not body.script.strip():
        raise script_empty()
    if len(body.script) > settings.funasr_max_script_chars:
        raise script_too_long(settings.funasr_max_script_chars)
    return _create_job(
        session,
        owner_key=owner_key,
        job_type=JOB_TYPE_GENERATE_SUBTITLE,
        file_ids=[body.file_id],
        extra_input={"script": body.script.strip()},
    )


@router.post(
    "/burn-subtitle",
    status_code=202,
    summary="建立燒字幕任務",
    description=(
        "將 SRT 燒進影片畫面（非同步 job；兩段式的第二段，必定重編碼 H.264）。\n\n"
        "- 必填 `file_id`（影片）與 `srt_file_id`（`.srt`：來自 generate-subtitle 的 `result.file_id`，或上傳的 `.srt`）\n"
        "- 可選 `font_size`（預設 48）、`margin_bottom`（預設 6）、"
        "`margin_unit`（`percent` 或 `px`，預設 `percent`）\n"
        "- 樣式固定：內建台北黑體 Regular、底部水平置中、白字黑描邊；不可自訂字型／對齊／顏色\n"
        "- `percent` 時離底像素 = `round(畫面高度 × margin_bottom / 100)`（例如 1080×1920、6% → 115px）\n"
        "- 完成後 `result` 含 `*_burned.mp4` 的 `download_url`（不含新的 `file_id`）\n"
        "- 失敗時常見 error code：`WRONG_FILE_TYPE`、`INVALID_MARGIN`、"
        "`INVALID_FONT_SIZE`、`INVALID_SRT`、`FONT_UNAVAILABLE`、`FFMPEG_ERROR`"
    ),
    responses=_BURN_ACCEPTED_RESPONSE,
)
def create_burn_subtitle_job(
    body: BurnSubtitleRequest,
    owner_key: str = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> dict:
    style = _normalize_burn_style(body.font_size, body.margin_bottom, body.margin_unit)
    video = _resolve_file(session, body.file_id, owner_key)
    srt = _resolve_file(session, body.srt_file_id, owner_key)
    _require_video_file(video)
    _require_srt_file(srt)
    return _create_job(
        session,
        owner_key=owner_key,
        job_type=JOB_TYPE_BURN_SUBTITLE,
        file_ids=[body.file_id, body.srt_file_id],
        extra_input={
            "srt_file_id": body.srt_file_id,
            **style,
        },
    )


@router.post(
    "/replace-images",
    status_code=202,
    summary="建立換圖任務",
    description=(
        "在指定時段把影片畫面整框換成已上傳的靜態圖（非同步 job；必定重編碼 H.264）。\n\n"
        "- 必填 `file_id`（影片）與 `replacements`（1–10 段）\n"
        "- 每段必填 `image_file_id`（先以 `POST /v1/files` 上傳的圖）、`start`、`end`（秒，含頭含尾）\n"
        "- 時段不可重疊；`end` 剛好等於下一段 `start` 可以。同一張圖可用在多段\n"
        "- 每段為 contain：等比縮放到不超出畫面、置中、多餘處補黑邊，不裁切也不變形\n"
        "- 音訊 stream copy、輸出時長與來源相同\n"
        "- 完成後 `result` 同時含 `file_id`（成片已註冊進檔案庫，可接 burn-subtitle）"
        "與 `*_replaced.mp4` 的 `download_url`\n"
        "- 失敗時常見 error code：`WRONG_FILE_TYPE`、`INVALID_RANGE`、"
        "`OVERLAPPING_RANGES`、`INVALID_IMAGE`、`FFMPEG_ERROR`"
    ),
    responses=_REPLACE_IMAGES_ACCEPTED_RESPONSE,
)
def create_replace_images_job(
    body: ReplaceImagesRequest,
    owner_key: str = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> dict:
    _validate_replacements(body.replacements)

    video = _resolve_file(session, body.file_id, owner_key)
    _require_video_file(video)

    image_ids: list[str] = []
    for item in body.replacements:
        image = _resolve_file(session, item.image_file_id, owner_key)
        _require_image_file(image)
        if item.image_file_id not in image_ids:
            image_ids.append(item.image_file_id)

    duration = _video_duration(video)
    if duration is not None:
        longest_end = max(item.end for item in body.replacements)
        if longest_end > duration:
            raise invalid_range(f"end 超過影片長度 {duration} 秒: {longest_end}")

    return _create_job(
        session,
        owner_key=owner_key,
        job_type=JOB_TYPE_REPLACE_IMAGES,
        file_ids=[body.file_id, *image_ids],
        extra_input={
            "replacements": [item.model_dump() for item in body.replacements]
        },
    )


@router.get(
    "/{job_id}",
    summary="查詢任務狀態",
    description=(
        "輪詢任務狀態。狀態流轉：`queued → processing → done / failed`。\n\n"
        "- `progress`：處理進度 0–100（merge / burn-subtitle / replace-images 依 FFmpeg 時長；"
        "import-url 依下載 bytes；"
        "generate-subtitle 依抽音／對齊階段；取幀任務極快，可能直接從 0 跳到 100）\n"
        "- `done`：merge / extract / burn-subtitle 含 `result.download_url`；"
        "generate-subtitle 含 `file_id`（可接 burn-subtitle）與 `download_url`；"
        "replace-images 含 `file_id`（可接後續任務）與 `download_url`；"
        "import-url 含 `result.file_id`\n"
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
                        "subtitle_done": {
                            "summary": "字幕完成",
                            "value": {
                                "job_id": "j_sub123abc456",
                                "type": "generate_subtitle",
                                "status": "done",
                                "progress": 100,
                                "created_at": "2026-08-26T02:00:00Z",
                                "started_at": "2026-08-26T02:00:01Z",
                                "completed_at": "2026-08-26T02:00:20Z",
                                "result": {
                                    "file_id": "f_srt789abc",
                                    "download_url": "https://storage.example.com/uploads/f_srt789abc/original.srt?sig=...",
                                    "expires_at": "2026-08-27T02:00:20Z",
                                    "filename": "talk.srt",
                                    "content_type": "application/x-subrip",
                                    "size_bytes": 512,
                                },
                            },
                        },
                        "subtitle_failed": {
                            "summary": "字幕失敗",
                            "value": {
                                "job_id": "j_sub123abc456",
                                "type": "generate_subtitle",
                                "status": "failed",
                                "progress": 20,
                                "created_at": "2026-08-26T02:00:00Z",
                                "started_at": "2026-08-26T02:00:01Z",
                                "completed_at": "2026-08-26T02:00:03Z",
                                "error": {
                                    "code": "NO_AUDIO_STREAM",
                                    "message": "輸入檔沒有音訊軌",
                                },
                            },
                        },
                        "burn_done": {
                            "summary": "燒字幕完成",
                            "value": {
                                "job_id": "j_burn123abc45",
                                "type": "burn_subtitle",
                                "status": "done",
                                "progress": 100,
                                "created_at": "2026-08-26T02:00:00Z",
                                "started_at": "2026-08-26T02:00:01Z",
                                "completed_at": "2026-08-26T02:00:40Z",
                                "result": {
                                    "download_url": "https://storage.example.com/results/j_burn123abc45/talk_burned.mp4?sig=...",
                                    "expires_at": "2026-08-27T02:00:40Z",
                                    "filename": "talk_burned.mp4",
                                    "content_type": "video/mp4",
                                    "size_bytes": 2048000,
                                },
                            },
                        },
                        "burn_failed": {
                            "summary": "燒字幕失敗",
                            "value": {
                                "job_id": "j_burn123abc45",
                                "type": "burn_subtitle",
                                "status": "failed",
                                "progress": 15,
                                "created_at": "2026-08-26T02:00:00Z",
                                "started_at": "2026-08-26T02:00:01Z",
                                "completed_at": "2026-08-26T02:00:02Z",
                                "error": {
                                    "code": "INVALID_SRT",
                                    "message": "SRT 沒有可用的字幕 cue",
                                },
                            },
                        },
                        "replace_done": {
                            "summary": "換圖完成",
                            "value": {
                                "job_id": "j_rep123abc456",
                                "type": "replace_images",
                                "status": "done",
                                "progress": 100,
                                "created_at": "2026-08-26T02:00:00Z",
                                "started_at": "2026-08-26T02:00:01Z",
                                "completed_at": "2026-08-26T02:00:35Z",
                                "result": {
                                    "file_id": "f_rep789abc",
                                    "download_url": "https://storage.example.com/uploads/f_rep789abc/original.mp4?sig=...",
                                    "expires_at": "2026-08-27T02:00:35Z",
                                    "filename": "talk_replaced.mp4",
                                    "content_type": "video/mp4",
                                    "size_bytes": 2048000,
                                },
                            },
                        },
                        "replace_failed": {
                            "summary": "換圖失敗",
                            "value": {
                                "job_id": "j_rep123abc456",
                                "type": "replace_images",
                                "status": "failed",
                                "progress": 15,
                                "created_at": "2026-08-26T02:00:00Z",
                                "started_at": "2026-08-26T02:00:01Z",
                                "completed_at": "2026-08-26T02:00:03Z",
                                "error": {
                                    "code": "INVALID_IMAGE",
                                    "message": "無法解讀圖片: slide.png",
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
    payload = {
        "download_url": download_url,
        "expires_at": _iso(utcnow() + timedelta(seconds=ttl_seconds)),
        "filename": result["filename"],
        "content_type": result["content_type"],
        "size_bytes": result["size_bytes"],
    }
    if result.get("file_id"):
        payload["file_id"] = result["file_id"]
    return payload
