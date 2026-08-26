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
影片合併、取幀與字幕 API。

## 使用流程

### 方式 A：上傳檔案

1. **上傳影片或 SRT** — `POST /v1/files`（multipart，欄位 `file`），取得 `file_id`

### 方式 B：從 URL 匯入

1. **建立匯入任務** — `POST /v1/jobs/import-url`（JSON 含 `url`），server 代為下載
2. **輪詢狀態** — `GET /v1/jobs/{job_id}`，`done` 時 `result.file_id` 即為可用檔案 ID

### 處理（兩種方式取得 `file_id` 後相同）

1. **建立任務** — `POST /v1/jobs/merge`（合併，`file_ids` 依陣列順序）、
   `POST /v1/jobs/extract-first-frame` / `extract-last-frame`（取幀）、
   或下方字幕任務
2. **輪詢狀態** — `GET /v1/jobs/{job_id}`，狀態 `queued → processing → done / failed`
3. **取得結果** — merge / extract / burn-subtitle 的 `done` 含 `result.download_url`（presigned URL，每次查詢重新簽發）；
   generate-subtitle 的 `done` 含 `file_id` 與 `download_url`；
   import-url 的 `done` 含 `result.file_id`（供後續任務引用）

### 字幕（兩段式）

燒字幕不從稿直接出片，須先有 SRT `file_id`：

1. **取得 SRT** — `POST /v1/jobs/generate-subtitle`（必填 `script`，有稿對齊；`done` 回 `result.file_id`），
   或 `POST /v1/files` 上傳既有 `.srt`
2. **燒進畫面** — `POST /v1/jobs/burn-subtitle`（影片 `file_id` + SRT `srt_file_id`）
3. **下載成片** — 輪詢至 `done`，`result.download_url` 為 `*_burned.mp4`

預設樣式：內建台北黑體 Regular、字級 48、離底 6%（`margin_unit=percent`）、底部水平置中、白字黑描邊。
不可自訂字型、對齊或顏色。燒字幕必定重編碼 H.264（音訊有軌則 copy）。

### 指定時段換成靜態圖

1. **上傳圖片** — `POST /v1/files` 上傳 `.png` / `.jpg` / `.jpeg` / `.webp`，取得 `image_file_id`
2. **建立換圖任務** — `POST /v1/jobs/replace-images`（影片 `file_id` + 1–10 段 `replacements`）
3. **取得成片** — 輪詢至 `done`，`result` 同時含 `file_id`（已註冊進檔案庫，可接 burn-subtitle 等後續任務）
   與 `*_replaced.mp4` 的 `download_url`

每段整框只剩該圖：等比縮放到不超出畫面（contain），置中，多餘區域補黑邊，不裁切也不變形。
音訊 stream copy、輸出時長與來源相同；畫面必定重編碼 H.264。
換圖與燒字幕的先後由呼叫端自行決定（先換圖再燒字＝圖上也有字幕）。

## 保留與清理（預設：永久保留）

- `FILE_TTL_HOURS=0`（預設）：上傳 / import / generate-subtitle 註冊的 `file_id` **永不過期**，`expires_at` 為 `null`
- `RESULT_TTL_HOURS=0`（預設）：merge / extract / burn-subtitle 的 job 結果 **永久保留**
- `AUTO_CLEANUP_ENABLED=false`（預設）：Worker **不**背景刪除檔案
- 恢復舊的自動清理行為：設 `AUTO_CLEANUP_ENABLED=true`、`FILE_TTL_HOURS=24`、`RESULT_TTL_HOURS=72`
- 手動刪除：`DELETE /v1/files/{file_id}`
- `DOWNLOAD_URL_TTL_HOURS`：單次 presigned URL 有效期（預設 24h），與結果是否保留無關

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
| `UNSUPPORTED_FORMAT` | 不支援的影片或字幕格式 |
| `EMPTY_FILE` | 上傳檔案為空 |
| `INSUFFICIENT_FILES` / `TOO_MANY_FILES` | 合併片段數量不符 |
| `FILE_PINNED` | 檔案正被進行中任務使用，無法刪除 |
| `JOB_NOT_FOUND` | job_id 不存在或非本人所有 |
| `SCRIPT_REQUIRED` | 未提供文字稿 |
| `SCRIPT_EMPTY` | 文字稿為空白 |
| `SCRIPT_TOO_LONG` | 文字稿超過 `FUNASR_MAX_SCRIPT_CHARS` |
| `NO_AUDIO_STREAM` | 影片沒有音訊軌 |
| `ALIGN_FAILED` | 強制對齊未產生可用時間戳 |
| `FUNASR_UNAVAILABLE` | Worker 無法載入 FunASR fa-zh |
| `WRONG_FILE_TYPE` | 影片／SRT／圖片的檔案類型不符 |
| `INVALID_MARGIN` | margin_bottom / margin_unit 無效 |
| `INVALID_FONT_SIZE` | font_size 超出 1–512 |
| `INVALID_SRT` | SRT 無法解析或沒有 cue |
| `FONT_UNAVAILABLE` | 找不到內建字幕字型 |
| `EMPTY_REPLACEMENTS` | replace-images 的 `replacements` 為空或未提供 |
| `TOO_MANY_REPLACEMENTS` | replace-images 的段數超過 10 |
| `INVALID_RANGE` | `start` / `end` 無效，或 `end` 超過影片長度 |
| `OVERLAPPING_RANGES` | replace-images 的時段互相重疊 |
| `INVALID_IMAGE` | 圖片無法解碼 |
| `FFMPEG_ERROR` | 影片處理失敗 |
"""

_TAGS_METADATA = [
    {"name": "files", "description": "檔案上傳與管理：影片、`.srt` 或圖片上傳後取得 `file_id`。預設永不過期（`FILE_TTL_HOURS=0`）；被進行中任務引用時不會過期。"},
    {"name": "jobs", "description": "非同步處理任務：合併（copy/encode 自動判斷）、取幀、從 URL 匯入、有稿產生 SRT、燒字幕（兩段式：先 SRT 再燒進畫面）、指定時段換成靜態圖。建立後輪詢 `GET /v1/jobs/{job_id}`。"},
    {"name": "system", "description": "健康檢查等系統端點。"},
]


def create_app() -> FastAPI:
    settings = get_settings()
    init_db()

    app = FastAPI(
        title="MergeVideo API",
        version="2.2.0",
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
