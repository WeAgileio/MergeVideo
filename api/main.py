"""FastAPI 應用程式入口。

啟動方式: uvicorn api.main:create_app --factory
"""

from __future__ import annotations

import shutil

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import api  # noqa: F401  # sys.path bootstrap
from api.config import get_settings
from api.db import init_db
from api.errors import ApiError
from api.routes import files, jobs


_API_DESCRIPTION = """\
影片合併與取幀 API。

## 使用流程

### 方式 A：上傳檔案

1. **上傳影片** — `POST /v1/files`（multipart，欄位 `file`），取得 `file_id`

### 方式 B：從 URL 匯入

1. **建立匯入任務** — `POST /v1/jobs/import-url`（JSON 含 `url`），server 代為下載
2. **輪詢狀態** — `GET /v1/jobs/{job_id}`，`done` 時 `result.file_id` 即為可用檔案 ID

### 處理（兩種方式取得 `file_id` 後相同）

1. **建立任務** — `POST /v1/jobs/merge`（合併，`file_ids` 依陣列順序）或
   `POST /v1/jobs/extract-first-frame` / `extract-last-frame`（取幀）
2. **輪詢狀態** — `GET /v1/jobs/{job_id}`，狀態 `queued → processing → done / failed`
3. **取得結果** — merge/extract 的 `done` 含 `result.download_url`（presigned URL）；
   import-url 的 `done` 含 `result.file_id`（供後續任務引用）

## 認證

所有 `/v1/*` endpoint 皆需 `Authorization: Bearer <api_key>`，
點右上角 **Authorize** 填入 API key 即可在此頁面直接測試。

## 錯誤格式

```json
{ "error": { "code": "FILE_NOT_FOUND", "message": "..." } }
```

| code | 說明 |
|------|------|
| `UNAUTHORIZED` | 缺少或無效的 API key |
| `INVALID_URL` | URL 格式或 scheme 不允許（預設僅 https） |
| `URL_NOT_ALLOWED` | URL 指向內網或禁止位址（SSRF 防護） |
| `DOWNLOAD_FAILED` | URL 下載失敗或逾時 |
| `FILE_NOT_FOUND` | file_id 不存在、已過期或非本人所有 |
| `UNAUTHORIZED_FILE` | 以他人檔案建立任務 |
| `FILE_TOO_LARGE` | 超過單檔大小上限（預設 200 MB） |
| `UNSUPPORTED_FORMAT` | 不支援的影片格式 |
| `INSUFFICIENT_FILES` / `TOO_MANY_FILES` | 合併片段數量不符 |
| `FILE_PINNED` | 檔案正被進行中任務使用，無法刪除 |
| `JOB_NOT_FOUND` | job_id 不存在或非本人所有 |
| `FFMPEG_ERROR` | 影片處理失敗 |
"""

_TAGS_METADATA = [
    {"name": "files", "description": "影片上傳與管理：上傳後取得 `file_id`，同一檔案可重複用於多個任務。檔案有 TTL（預設 24h），被進行中任務引用時不會過期。"},
    {"name": "jobs", "description": "非同步處理任務：合併（copy/encode 自動判斷）、取幀、**從 URL 匯入影片**。建立後輪詢 `GET /v1/jobs/{job_id}`；merge/extract 完成取得 download URL，import-url 完成取得 `file_id`。"},
    {"name": "system", "description": "健康檢查等系統端點。"},
]


def create_app() -> FastAPI:
    settings = get_settings()
    init_db()

    app = FastAPI(
        title="MergeVideo API",
        version="1.0.0",
        description=_API_DESCRIPTION,
        openapi_tags=_TAGS_METADATA,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    app.include_router(files.router)
    app.include_router(jobs.router)

    @app.get(
        "/health",
        tags=["system"],
        summary="健康檢查",
        description="回報服務狀態與 ffmpeg / ffprobe 可用性，無需認證。",
    )
    def health() -> dict:
        ffmpeg_ok = shutil.which("ffmpeg") is not None
        ffprobe_ok = shutil.which("ffprobe") is not None
        return {
            "status": "ok" if ffmpeg_ok and ffprobe_ok else "degraded",
            "ffmpeg": ffmpeg_ok,
            "ffprobe": ffprobe_ok,
        }

    # local storage backend：由 API 直接提供結果下載
    if settings.storage_backend == "local":
        settings.local_storage_dir.mkdir(parents=True, exist_ok=True)
        app.mount(
            "/storage",
            StaticFiles(directory=settings.local_storage_dir),
            name="storage",
        )

    return app
